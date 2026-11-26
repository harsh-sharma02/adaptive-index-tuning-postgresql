import csv
import hashlib
import io
import json
import os
import re
import statistics
from contextlib import redirect_stdout

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from config import INITIAL_WORKLOAD, NEW_WORKLOAD, WORKLOAD_DIR, RESULTS_DIR
from workload import read_workload
from db_manager import connect_db, reset_hypothetical_indexes
from optimizer import generate_candidates, optimize_configuration

from adaptive import (
    unique_indexes,
    print_index_changes,
    calculate_workload_drift,
)


REPETITIONS = 3


# ============================================================
# TERMINAL DISPLAY HELPERS
# ============================================================

def print_header(title):
    print("\n" + "=" * 72)
    print(f" {title}")
    print("=" * 72)


def print_metric(label, value, width=34):
    print(f"  {label:<{width}} {value}")


def print_configuration_summary(result, label):
    print_header(f"{label} — PERFORMANCE SUMMARY")

    print(
        f"  {'Metric':<34}"
        f"{'Before indexes':>16}"
        f"{'After indexes':>18}"
    )
    print("  " + "-" * 70)

    print(
        f"  {'Execution time (ms)':<34}"
        f"{result['baseline_time']:>16.2f}"
        f"{result['optimized_time']:>18.2f}"
    )

    print(
        f"  {'Index storage (MB)':<34}"
        f"{result['baseline'].get('storage_mb', 0.0):>16.2f}"
        f"{result['optimized'].get('storage_mb', 0.0):>18.2f}"
    )

    print(
        f"  {'Number of indexes':<34}"
        f"{result['baseline'].get('index_count', 0):>16}"
        f"{result['optimized'].get('index_count', 0):>18}"
    )

    print("  " + "-" * 70)

    print_metric(
        "Execution-time improvement:",
        f"{result['improvement']:.2f}%"
    )


# ============================================================
# REAL INDEX MANAGEMENT
# ============================================================

def create_real_indexes(connection, indexes):
    """Create temporary real indexes and return their PostgreSQL names."""

    indexes = unique_indexes(indexes)
    names = []

    try:
        with connection.cursor() as cursor:

            for candidate in indexes:

                table = str(candidate["table"]).strip().strip('"')

                columns = [
                    str(column).strip().strip('"')
                    for column in candidate["columns"]
                ]

                identity = f"{table}_{'_'.join(columns)}".lower()

                readable_name = re.sub(
                    r"[^a-zA-Z0-9_]", "_", identity
                )[:36]

                suffix = hashlib.sha1(
                    identity.encode("utf-8")
                ).hexdigest()[:10]

                index_name = f"abt_{readable_name}_{suffix}"[:60]

                column_sql = ", ".join(
                    f'"{column}"' for column in columns
                )

                cursor.execute(
                    f'CREATE INDEX "{index_name}" '
                    f'ON "{table}" ({column_sql})'
                )

                names.append(index_name)

        connection.commit()
        return names

    except Exception:
        connection.rollback()
        drop_real_indexes(connection, names)
        raise


def drop_real_indexes(connection, names):
    """Drop only temporary indexes created by this benchmark."""

    if not names:
        return

    with connection.cursor() as cursor:

        for name in names:
            cursor.execute(
                f'DROP INDEX IF EXISTS "{name}"'
            )

    connection.commit()


def analyze_database(connection):

    with connection.cursor() as cursor:
        cursor.execute("ANALYZE")

    connection.commit()


# ============================================================
# QUERY PERFORMANCE MEASUREMENT
# ============================================================

def measure_query(connection, sql):
    """Return median execution time and planner cost."""

    times = []
    costs = []

    with connection.cursor() as cursor:

        # Warm-up execution
        cursor.execute(
            "EXPLAIN (ANALYZE, FORMAT JSON, BUFFERS) " + sql
        )
        cursor.fetchone()

        # Repeated measurements
        for _ in range(REPETITIONS):

            cursor.execute(
                "EXPLAIN (ANALYZE, FORMAT JSON, BUFFERS) " + sql
            )

            result = cursor.fetchone()[0]

            if isinstance(result, str):
                result = json.loads(result)

            plan = result[0]["Plan"]

            times.append(
                float(plan["Actual Total Time"])
            )

            costs.append(
                float(plan["Total Cost"])
            )

    return (
        statistics.median(times),
        statistics.median(costs)
    )


def measure_workload(connection, queries):
    """Measure every SELECT query occurrence."""

    total_time = 0.0
    total_cost = 0.0
    measured_queries = 0

    for query in queries:

        if query.get("query_type") != "SELECT":
            continue

        execution_time, plan_cost = measure_query(
            connection,
            query["sql"]
        )

        total_time += execution_time
        total_cost += plan_cost

        measured_queries += 1

    return {
        "execution_time": total_time,
        "plan_cost": total_cost,
        "query_count": measured_queries,
    }


def measure_index_storage(connection, index_names):
    """Calculate total storage occupied by temporary indexes."""

    if not index_names:
        return 0.0

    with connection.cursor() as cursor:

        cursor.execute(
            """
            SELECT COALESCE(SUM(pg_relation_size(indexrelid)), 0)
            FROM pg_index
            WHERE indexrelid = ANY(%s::regclass[])
            """,
            (index_names,),
        )

        size_bytes = cursor.fetchone()[0]

    return float(size_bytes) / (1024 * 1024)


# ============================================================
# CONFIGURATION BENCHMARK
# ============================================================

def benchmark_configuration(connection, reads, label, indexes):
    """
    Benchmark one configuration.

    Temporary real indexes are always dropped after measurement.
    """

    print(
        f"  • Measuring: {label.lower()} ...",
        flush=True
    )

    created_names = []

    try:

        if indexes:
            created_names = create_real_indexes(
                connection,
                indexes
            )

        analyze_database(connection)

        measurements = measure_workload(
            connection,
            reads
        )

        storage_mb = measure_index_storage(
            connection,
            created_names
        )

        measurements["index_count"] = len(
            unique_indexes(indexes)
        )

        measurements["storage_mb"] = storage_mb

        return measurements

    finally:

        drop_real_indexes(
            connection,
            created_names
        )

        analyze_database(connection)


def calculate_improvement(reference_time, measured_time):

    if reference_time <= 0:
        return 0.0

    return (
        (reference_time - measured_time)
        / reference_time
    ) * 100.0


# ============================================================
# COMPLETE WORKLOAD BENCHMARK
# ============================================================

def benchmark(
    connection,
    reads,
    writes,
    label,
    previous_indexes=None,
    previous_reads=None
):

    print_header(f"{label} — INDEX TUNING")

    queries = reads + writes

    candidates = generate_candidates(queries)

    print_metric("Read queries:", len(reads))
    print_metric("Write queries (cost model):", len(writes))
    print_metric("Candidates after pruning:", len(candidates))

    previous_queries = (
        previous_reads + writes
        if previous_reads is not None
        else None
    )

    print("\n  Optimizing index configuration ...", flush=True)

    # Hide detailed optimizer logs from the main terminal.
    optimizer_log = io.StringIO()

    with redirect_stdout(optimizer_log):

        result = optimize_configuration(
            connection,
            queries,
            candidates,
            previous_indexes=previous_indexes,
            previous_queries=previous_queries,
        )

    selected_indexes = unique_indexes(
        result["indexes"]
    )

    print_metric(
        "Solver status:",
        result.get("solver_status", "Completed")
    )

    print_metric(
        "Selected indexes:",
        len(selected_indexes)
    )

    print_metric(
        "Adaptation decision:",
        result.get("adaptation_decision", "N/A")
    )

    print_metric(
        "Structural workload drift:",
        f"{result.get('structural_drift', 0.0) * 100:.2f}%"
    )

    print_metric(
        "Reconfiguration penalty:",
        f"{result.get('reconfiguration_penalty', 0.0):.2f}"
    )

    reset_hypothetical_indexes(connection)
    analyze_database(connection)

    print("\n  Running controlled before/after benchmark:")

    # BEFORE INDEXES
    baseline = benchmark_configuration(
        connection,
        reads,
        "Before indexes",
        []
    )

    # AFTER RECOMMENDED INDEXES
    optimized = benchmark_configuration(
        connection,
        reads,
        "After recommended indexes",
        selected_indexes
    )

    improvement = calculate_improvement(
        baseline["execution_time"],
        optimized["execution_time"]
    )

    benchmark_result = {
        "indexes": selected_indexes,

        "baseline": baseline,
        "optimized": optimized,

        "baseline_time": baseline["execution_time"],
        "optimized_time": optimized["execution_time"],

        "baseline_cost": baseline["plan_cost"],
        "optimized_cost": optimized["plan_cost"],

        "improvement": improvement,

        "storage_mb": optimized["storage_mb"],

        "optimizer_result": result,
    }

    print_configuration_summary(
        benchmark_result,
        label
    )

    print("\n  Temporary benchmark indexes removed.")

    if previous_indexes is not None:

        print_header("INDEX ADAPTATION")

        print_index_changes(
            previous_indexes,
            selected_indexes
        )

    return benchmark_result


# ============================================================
# GRAPH GENERATION
# ============================================================

def save_workload_plot(
    result,
    workload_label,
    output_dir,
    filename
):
    """
    Plot before/after execution time for one unchanged workload.
    Index storage is shown on a secondary y-axis.
    """

    labels = [
        "Before indexes",
        "After recommended indexes"
    ]

    execution_times = [
        result["baseline_time"],
        result["optimized_time"],
    ]

    storage_values = [
        result["baseline"].get("storage_mb", 0.0),
        result["optimized"].get("storage_mb", 0.0),
    ]

    positions = [0, 1]

    fig, time_axis = plt.subplots(
        figsize=(9, 6)
    )

    bars = time_axis.bar(
        positions,
        execution_times,
        width=0.48,
        label="Execution time",
    )

    time_axis.set_ylabel(
        "Total workload execution time (ms)"
    )

    time_axis.set_xticks(
        positions,
        labels
    )

    time_axis.set_title(
        f"{workload_label}: Before and After Index Optimization",
        fontsize=14,
        pad=14,
    )

    time_axis.grid(
        axis="y",
        alpha=0.25
    )

    time_axis.set_axisbelow(True)

    time_axis.bar_label(
        bars,
        labels=[
            f"{value:.1f} ms"
            for value in execution_times
        ],
        padding=4,
        fontsize=10,
    )

    storage_axis = time_axis.twinx()

    storage_axis.plot(
        positions,
        storage_values,
        marker="o",
        linewidth=2,
        markersize=8,
        label="Index storage",
    )

    storage_axis.set_ylabel(
        "Recommended index storage (MB)"
    )

    storage_axis.set_ylim(
        0,
        max(storage_values + [1.0]) * 1.35
    )

    for position, storage in zip(
        positions,
        storage_values
    ):

        storage_axis.annotate(
            f"{storage:.2f} MB",
            (position, storage),
            xytext=(0, 11),
            textcoords="offset points",
            ha="center",
            fontsize=10,
        )

    improvement = calculate_improvement(
        result["baseline_time"],
        result["optimized_time"]
    )

    time_axis.text(
        0.5,
        0.96,
        f"Execution-time improvement: {improvement:.2f}%",
        transform=time_axis.transAxes,
        ha="center",
        va="top",
        fontsize=11,
        fontweight="bold",
    )

    time_handles, time_labels = (
        time_axis.get_legend_handles_labels()
    )

    storage_handles, storage_labels = (
        storage_axis.get_legend_handles_labels()
    )

    time_axis.legend(
        time_handles + storage_handles,
        time_labels + storage_labels,
        loc="upper right",
    )

    fig.tight_layout()

    path = output_dir / filename

    # Save to the same filename: previous graph is overwritten.
    fig.savefig(
        path,
        dpi=300,
        bbox_inches="tight"
    )

    plt.close(fig)

    return path


# ============================================================
# CSV REPORT
# ============================================================

def save_results_csv(
    initial_result,
    adapted_result,
    workload_drift,
    output_dir
):

    rows = []

    experiments = [
        ("Initial workload", initial_result, 0.0),
        (
            "Adapted workload",
            adapted_result,
            workload_drift * 100
        ),
    ]

    for experiment_name, result, drift_percent in experiments:

        rows.append({
            "experiment": experiment_name,
            "configuration": "Before indexes",
            **result["baseline"],
            "improvement_percent": 0.0,
            "workload_drift_percent": drift_percent,
        })

        rows.append({
            "experiment": experiment_name,
            "configuration": "After recommended indexes",
            **result["optimized"],
            "improvement_percent": result["improvement"],
            "workload_drift_percent": drift_percent,
        })

    path = output_dir / "index_tuning_results.csv"

    fieldnames = [
        "experiment",
        "configuration",
        "query_count",
        "index_count",
        "storage_mb",
        "execution_time",
        "plan_cost",
        "improvement_percent",
        "workload_drift_percent",
    ]

    # Opening in write mode overwrites the previous CSV.
    with path.open(
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames
        )

        writer.writeheader()

        for row in rows:

            writer.writerow({
                key: row.get(key, "")
                for key in fieldnames
            })

    return path


# ============================================================
# MAIN PROGRAM
# ============================================================

def main():

    # Clear terminal on Windows.
    if os.name == "nt":
        os.system("cls")

    print_header(
        "ADAPTIVE WORKLOAD-AWARE INDEX TUNING"
    )

    print("  Loading workload files ...")

    initial_reads = read_workload(
        INITIAL_WORKLOAD
    )

    new_reads = read_workload(
        NEW_WORKLOAD
    )

    write_queries = read_workload(
        WORKLOAD_DIR / "workload_3.sql"
    )

    drift = calculate_workload_drift(
        initial_reads,
        new_reads
    )

    print_header("WORKLOAD OVERVIEW")

    print_metric(
        "Initial workload SELECT queries:",
        len(initial_reads)
    )

    print_metric(
        "New workload SELECT queries:",
        len(new_reads)
    )

    print_metric(
        "Write queries used for cost model:",
        len(write_queries)
    )

    print_metric(
        "Structural workload drift:",
        f"{drift * 100:.2f}%"
    )

    connection = connect_db()

    try:

        # ----------------------------------------------------
        # INITIAL WORKLOAD
        # ----------------------------------------------------

        initial_result = benchmark(
            connection,
            initial_reads,
            write_queries,
            "INITIAL WORKLOAD"
        )

        # ----------------------------------------------------
        # ADAPTED WORKLOAD
        # ----------------------------------------------------

        adapted_result = benchmark(
            connection,
            new_reads,
            write_queries,
            "ADAPTED WORKLOAD",
            previous_indexes=initial_result["indexes"],
            previous_reads=initial_reads,
        )

        # ----------------------------------------------------
        # FINAL SUMMARY
        # ----------------------------------------------------

        print_header("FINAL EXPERIMENT SUMMARY")

        print(
            f"  {'Result':<38}"
            f"{'Initial':>12}"
            f"{'Adapted':>12}"
        )

        print("  " + "-" * 64)

        print(
            f"  {'Execution-time improvement':<38}"
            f"{initial_result['improvement']:>11.2f}%"
            f"{adapted_result['improvement']:>11.2f}%"
        )

        print(
            f"  {'Recommended index count':<38}"
            f"{len(initial_result['indexes']):>12}"
            f"{len(adapted_result['indexes']):>12}"
        )

        print(
            f"  {'Index storage (MB)':<38}"
            f"{initial_result['storage_mb']:>12.2f}"
            f"{adapted_result['storage_mb']:>12.2f}"
        )

        print("  " + "-" * 64)

        # ----------------------------------------------------
        # SAVE GRAPHS AND CSV
        # ----------------------------------------------------

        RESULTS_DIR.mkdir(
            parents=True,
            exist_ok=True
        )

        print(
            "\n  Updating report files "
            "(existing files will be overwritten) ..."
        )

        initial_plot = save_workload_plot(
            initial_result,
            "Initial Workload",
            RESULTS_DIR,
            "initial_workload_index_impact.png",
        )

        adapted_plot = save_workload_plot(
            adapted_result,
            "New Workload After Adaptation",
            RESULTS_DIR,
            "adapted_workload_index_impact.png",
        )

        results_csv = save_results_csv(
            initial_result,
            adapted_result,
            drift,
            RESULTS_DIR
        )

        # ----------------------------------------------------
        # COMPLETION MESSAGE
        # ----------------------------------------------------

        print_header("REPORTS UPDATED")

        print(
            f"  Initial workload graph : {initial_plot.name}"
        )

        print(
            f"  Adapted workload graph : {adapted_plot.name}"
        )

        print(
            f"  Results spreadsheet   : {results_csv.name}"
        )

        print(
            f"  Output folder         : {RESULTS_DIR}"
        )

        print(
            "\n  Existing report files were replaced "
            "with this run's results."
        )

        print(
            "  Temporary real indexes were dropped."
        )

        print(
            "  Database cleanup completed."
        )

    finally:

        reset_hypothetical_indexes(connection)
        connection.close()


if __name__ == "__main__":
    main()
