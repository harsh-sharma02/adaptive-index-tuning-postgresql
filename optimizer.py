import itertools
import math
from collections import defaultdict, Counter

from ortools.sat.python import cp_model

from config import (
    STORAGE_BUDGET_MB, MAX_INDEX_COLUMNS, READ_COST_WEIGHT,
    WRITE_COST_WEIGHT, STORAGE_COST_WEIGHT, RECONFIGURATION_COST_WEIGHT,
    SOLVER_TIME_LIMIT,
)
from db_manager import (
    connect_db, explain_query, reset_hypothetical_indexes,
    create_hypothetical_index,
)
from workload import read_workload


MAX_SURROGATE_CANDIDATES = 20
OBJECTIVE_SCALE = 1000
STORAGE_SCALE = 1000

CATEGORY_WEIGHTS = {
    "where_columns": 4.0,
    "join_columns": 3.5,
    "order_columns": 2.5,
    "group_columns": 2.0,
}

HYSTERESIS_RELATIVE_THRESHOLD = 0.01
HYSTERESIS_ABSOLUTE_THRESHOLD = 1.0
MIN_DRIFT_THRESHOLD_MULTIPLIER = 0.25


def normalize_identifier(value):
    return str(value).strip().strip('"').lower()


def candidate_key(candidate):
    return (
        normalize_identifier(candidate["table"]),
        tuple(normalize_identifier(c) for c in candidate["columns"]),
    )


def unique_candidates(candidates):
    result, seen = [], set()
    for candidate in candidates:
        key = candidate_key(candidate)
        if key not in seen:
            seen.add(key)
            result.append(candidate)
    return result


def get_query_columns(query):
    result = defaultdict(list)
    for category in CATEGORY_WEIGHTS:
        for item in query.get(category, []):
            table, column = item.get("table"), item.get("column")
            if table and column:
                entry = (normalize_identifier(table),
                         normalize_identifier(column))
                if entry not in result[category]:
                    result[category].append(entry)
    return result


def query_structure_signature(query):
    """Literal-independent representation of a query's access structure."""
    tables = tuple(sorted(
        normalize_identifier(t) for t in query.get("tables", [])
    ))
    columns = get_query_columns(query)
    categories = tuple(
        (category, tuple(sorted(columns[category])))
        for category in CATEGORY_WEIGHTS
    )
    return (
        str(query.get("query_type", "OTHER")).upper(),
        tables,
        categories,
    )


def calculate_structural_drift(old_queries, new_queries):
    """
    Frequency-aware Jaccard distance over table/column access structures.
    Different constants on the same columns are treated as the same pattern.
    """
    old = Counter(query_structure_signature(q) for q in old_queries)
    new = Counter(query_structure_signature(q) for q in new_queries)
    keys = set(old) | set(new)
    if not keys:
        return 0.0
    intersection = sum(min(old[k], new[k]) for k in keys)
    union = sum(max(old[k], new[k]) for k in keys)
    return 0.0 if union == 0 else 1.0 - intersection / union


def generate_candidates(queries):
    records = {}

    for query_id, query in enumerate(queries):
        if query.get("query_type") != "SELECT":
            continue

        by_table = defaultdict(list)
        for category, entries in get_query_columns(query).items():
            for table, column in entries:
                by_table[table].append((category, column))

        for table, entries in by_table.items():
            unique_entries = list(dict.fromkeys(entries))

            for category, column in unique_entries:
                key = (table, (column,))
                record = records.setdefault(key, {
                    "table": table, "columns": (column,), "score": 0.0,
                    "support": set(), "categories": set(),
                })
                record["score"] += CATEGORY_WEIGHTS[category]
                record["support"].add(query_id)
                record["categories"].add(category)

            ordered_columns = []
            for category in CATEGORY_WEIGHTS:
                for entry_category, column in unique_entries:
                    if entry_category == category and column not in ordered_columns:
                        ordered_columns.append(column)

            max_width = min(MAX_INDEX_COLUMNS, len(ordered_columns))
            for width in range(2, max_width + 1):
                for combination in itertools.combinations(ordered_columns, width):
                    key = (table, tuple(combination))
                    record = records.setdefault(key, {
                        "table": table, "columns": tuple(combination),
                        "score": 0.0, "support": set(), "categories": set(),
                    })
                    record["score"] += sum(CATEGORY_WEIGHTS.values()) / width
                    record["support"].add(query_id)
                    record["categories"].update(
                        category for category, column in unique_entries
                        if column in combination
                    )

    candidates = []
    for record in records.values():
        support_count = len(record["support"])
        record["score"] *= 1.0 + math.log1p(support_count)
        record["support_count"] = support_count
        record["support"] = sorted(record["support"])
        record["categories"] = sorted(record["categories"])
        candidates.append(record)

    candidates.sort(
        key=lambda item: (
            item["score"] / (len(item["columns"]) ** 0.65),
            item["support_count"], -len(item["columns"]),
        ),
        reverse=True,
    )
    return prune_candidates(candidates)


def prune_candidates(candidates):
    candidates = unique_candidates(candidates)
    if len(candidates) <= MAX_SURROGATE_CANDIDATES:
        return candidates

    selected, selected_keys = [], set()
    table_counts = defaultdict(int)

    for candidate in candidates:
        table = candidate["table"]
        if table_counts[table] >= 6:
            continue
        key = candidate_key(candidate)
        selected.append(candidate)
        selected_keys.add(key)
        table_counts[table] += 1
        if len(selected) >= MAX_SURROGATE_CANDIDATES:
            break

    if len(selected) < MAX_SURROGATE_CANDIDATES:
        for candidate in candidates:
            key = candidate_key(candidate)
            if key not in selected_keys:
                selected.append(candidate)
                selected_keys.add(key)
            if len(selected) >= MAX_SURROGATE_CANDIDATES:
                break
    return selected


def index_definition(candidate):
    columns = ", ".join(f'"{c}"' for c in candidate["columns"])
    return f'CREATE INDEX ON "{candidate["table"]}" ({columns})'


def calculate_read_cost(connection, queries):
    total = 0.0
    for query in queries:
        if query.get("query_type") == "SELECT":
            total += float(explain_query(connection, query["sql"])["total_cost"])
    return total


def calculate_write_penalty(queries, configuration):
    write_frequency = defaultdict(float)
    weights = {"INSERT": 1.0, "UPDATE": 1.5, "DELETE": 1.0}

    for query in queries:
        query_type = query.get("query_type")
        if query_type in weights:
            for table in query.get("tables", []):
                write_frequency[normalize_identifier(table)] += weights[query_type]

    penalty = 0.0
    for candidate in configuration:
        width = len(candidate["columns"])
        penalty += (
            write_frequency[normalize_identifier(candidate["table"])]
            * (1.0 + 0.25 * (width - 1))
        )
    return penalty


def index_transition_cost(candidate):
    """Transition cost for one create/drop operation."""
    return 1.0 + 0.25 * (len(candidate["columns"]) - 1)


def calculate_reconfiguration_penalty(configuration, previous_indexes):
    current = {candidate_key(x): x for x in unique_candidates(configuration)}
    previous = {
        candidate_key(x): x for x in unique_candidates(previous_indexes or [])
    }
    added = set(current) - set(previous)
    removed = set(previous) - set(current)
    return (
        sum(index_transition_cost(current[k]) for k in added)
        + sum(index_transition_cost(previous[k]) for k in removed)
    )


def evaluate_configuration(connection, queries, configuration,
                           previous_indexes=None):
    previous_indexes = unique_candidates(previous_indexes or [])
    configuration = unique_candidates(configuration)
    reset_hypothetical_indexes(connection)
    total_storage_bytes = 0

    try:
        for candidate in configuration:
            result = create_hypothetical_index(
                connection, index_definition(candidate)
            )
            if not result:
                return None

            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT hypopg_relation_size(%s)", (result[0],)
                )
                total_storage_bytes += int(cursor.fetchone()[0] or 0)

        read_cost = calculate_read_cost(connection, queries)
        write_penalty = calculate_write_penalty(queries, configuration)
        storage_mb = total_storage_bytes / (1024 * 1024)
        reconfiguration = calculate_reconfiguration_penalty(
            configuration, previous_indexes
        )
        objective = (
            READ_COST_WEIGHT * read_cost
            + WRITE_COST_WEIGHT * write_penalty
            + STORAGE_COST_WEIGHT * storage_mb
            + RECONFIGURATION_COST_WEIGHT * reconfiguration
        )
        return {
            "read_cost": read_cost,
            "write_penalty": write_penalty,
            "storage_penalty": storage_mb,
            "reconfiguration_penalty": reconfiguration,
            "objective": objective,
            "storage_mb": storage_mb,
            "indexes": configuration.copy(),
        }
    finally:
        reset_hypothetical_indexes(connection)


def profile_candidates(connection, queries, candidates):
    print("\nProfiling candidate indexes with HypoPG...")
    baseline = calculate_read_cost(connection, queries)
    single_costs, storage_costs = {}, {}

    for i, candidate in enumerate(candidates):
        result = evaluate_configuration(connection, queries, [candidate])
        if result is None:
            single_costs[i], storage_costs[i] = baseline, 0.0
        else:
            single_costs[i] = result["read_cost"]
            storage_costs[i] = result["storage_mb"]
        print(f"Single profile {i + 1}/{len(candidates)} completed")

    pair_interactions = {}
    pairs = list(itertools.combinations(range(len(candidates)), 2))
    for pair_number, (i, j) in enumerate(pairs, start=1):
        result = evaluate_configuration(
            connection, queries, [candidates[i], candidates[j]]
        )
        pair_cost = (
            single_costs[i] + single_costs[j] - baseline
            if result is None else result["read_cost"]
        )
        pair_interactions[(i, j)] = (
            pair_cost - single_costs[i] - single_costs[j] + baseline
        )
        if pair_number % 25 == 0 or pair_number == len(pairs):
            print(f"Pair profiles {pair_number}/{len(pairs)} completed")

    return {
        "baseline": baseline,
        "single_costs": single_costs,
        "storage_costs": storage_costs,
        "pair_interactions": pair_interactions,
    }


def solve_with_cp_sat(queries, candidates, profile, previous_indexes=None):
    """
    CP-SAT surrogate model.

    Correct transition formulation:
    - all old indexes contribute a drop-cost constant;
    - selecting an old index cancels its drop cost;
    - selecting a new index adds its creation cost.
    """
    previous = {
        candidate_key(x): x
        for x in unique_candidates(previous_indexes or [])
    }
    model = cp_model.CpModel()
    n = len(candidates)
    x = [model.NewBoolVar(f"index_{i}") for i in range(n)]
    y = {}

    for i, j in profile["pair_interactions"]:
        y[i, j] = model.NewBoolVar(f"pair_{i}_{j}")
        model.Add(y[i, j] <= x[i])
        model.Add(y[i, j] <= x[j])
        model.Add(y[i, j] >= x[i] + x[j] - 1)

    storage_terms = [
        int(round(profile["storage_costs"][i] * STORAGE_SCALE)) * x[i]
        for i in range(n)
    ]
    model.Add(
        sum(storage_terms)
        <= int(round(STORAGE_BUDGET_MB * STORAGE_SCALE))
    )

    baseline = profile["baseline"]
    constant_cost = READ_COST_WEIGHT * baseline

    # Pay the drop cost for every old index unless it is retained.
    for old_index in previous.values():
        constant_cost += (
            RECONFIGURATION_COST_WEIGHT * index_transition_cost(old_index)
        )

    objective_terms = []
    for i, candidate in enumerate(candidates):
        read_delta = profile["single_costs"][i] - baseline
        write_penalty = calculate_write_penalty(queries, [candidate])
        storage_penalty = profile["storage_costs"][i]
        key = candidate_key(candidate)

        if key in previous:
            transition_coefficient = -index_transition_cost(previous[key])
        else:
            transition_coefficient = index_transition_cost(candidate)

        coefficient = (
            READ_COST_WEIGHT * read_delta
            + WRITE_COST_WEIGHT * write_penalty
            + STORAGE_COST_WEIGHT * storage_penalty
            + RECONFIGURATION_COST_WEIGHT * transition_coefficient
        )
        objective_terms.append(
            int(round(coefficient * OBJECTIVE_SCALE)) * x[i]
        )

    for (i, j), interaction in profile["pair_interactions"].items():
        objective_terms.append(
            int(round(READ_COST_WEIGHT * interaction * OBJECTIVE_SCALE))
            * y[i, j]
        )

    model.Minimize(
        int(round(constant_cost * OBJECTIVE_SCALE))
        + sum(objective_terms)
    )

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = SOLVER_TIME_LIMIT
    solver.parameters.num_search_workers = 8
    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError(
            "CP-SAT could not find a feasible index configuration. "
            f"Solver status: {solver.StatusName(status)}"
        )

    selected = [
        candidates[i] for i in range(n) if solver.Value(x[i]) == 1
    ]
    return selected, solver.StatusName(status), solver.ObjectiveValue()


def apply_hysteresis(proposed, previous, structural_drift):
    """Retain the old configuration unless the full objective improves enough."""
    if previous is None:
        proposed["adaptation_decision"] = "INITIAL_CONFIGURATION"
        proposed["hysteresis_threshold"] = 0.0
        proposed["objective_improvement"] = 0.0
        return proposed

    old_objective = float(previous["objective"])
    new_objective = float(proposed["objective"])
    drift = min(max(float(structural_drift), 0.0), 1.0)
    drift_multiplier = max(
        MIN_DRIFT_THRESHOLD_MULTIPLIER, 1.0 - drift
    )
    threshold = max(
        HYSTERESIS_ABSOLUTE_THRESHOLD,
        abs(old_objective) * HYSTERESIS_RELATIVE_THRESHOLD,
    ) * drift_multiplier
    improvement = old_objective - new_objective

    if improvement < threshold:
        previous["adaptation_decision"] = "RETAINED_PREVIOUS_CONFIGURATION"
        previous["hysteresis_threshold"] = threshold
        previous["objective_improvement"] = improvement
        previous["proposed_objective"] = new_objective
        previous["structural_drift"] = drift
        return previous

    proposed["adaptation_decision"] = "ADAPTED_CONFIGURATION"
    proposed["hysteresis_threshold"] = threshold
    proposed["objective_improvement"] = improvement
    proposed["proposed_objective"] = new_objective
    proposed["structural_drift"] = drift
    return proposed


def optimize_configuration(connection, queries, candidates,
                           previous_indexes=None, previous_queries=None):
    previous_indexes = unique_candidates(previous_indexes or [])
    candidates = unique_candidates(candidates)
    structural_drift = (
        calculate_structural_drift(previous_queries, queries)
        if previous_queries is not None else 0.0
    )

    if not candidates:
        proposed = evaluate_configuration(
            connection, queries, [], previous_indexes
        )
        if proposed is None:
            raise RuntimeError("Could not evaluate empty configuration.")
        proposed.update({
            "baseline_cost": proposed["read_cost"],
            "cost_reduction": 0.0,
            "solver_status": "NO_CANDIDATES",
            "candidate_count": 0,
            "profiled_pairs": 0,
        })
        previous_result = None
        if previous_indexes:
            previous_result = evaluate_configuration(
                connection, queries, previous_indexes, previous_indexes
            )
            if previous_result and previous_result["storage_mb"] > STORAGE_BUDGET_MB:
                previous_result = None
        selected = apply_hysteresis(
            proposed, previous_result, structural_drift
        )
        selected["structural_drift"] = structural_drift
        return selected

    print("\nCandidate count after pruning:", len(candidates))
    print(f"Structural workload drift: {structural_drift * 100:.2f}%")
    profile = profile_candidates(connection, queries, candidates)

    selected, solver_status, solver_objective = solve_with_cp_sat(
        queries, candidates, profile, previous_indexes
    )
    print("\nCP-SAT status:", solver_status)
    print("CP-SAT objective:", solver_objective)

    proposed = evaluate_configuration(
        connection, queries, selected, previous_indexes
    )
    if proposed is None:
        raise RuntimeError(
            "HypoPG validation failed for the selected configuration."
        )

    previous_result = None
    if previous_indexes:
        previous_result = evaluate_configuration(
            connection, queries, previous_indexes, previous_indexes
        )
        if (
            previous_result is not None
            and previous_result["storage_mb"] > STORAGE_BUDGET_MB
        ):
            previous_result = None

    validated = apply_hysteresis(
        proposed, previous_result, structural_drift
    )
    validated.update({
        "baseline_cost": profile["baseline"],
        "cost_reduction": profile["baseline"] - validated["read_cost"],
        "solver_status": solver_status,
        "candidate_count": len(candidates),
        "profiled_pairs": len(profile["pair_interactions"]),
        "surrogate_objective": solver_objective,
        "structural_drift": structural_drift,
    })

    print("Adaptation decision:", validated["adaptation_decision"])
    print(f"Hysteresis threshold: {validated['hysteresis_threshold']:.4f}")
    return validated


def main():
    from config import INITIAL_WORKLOAD, WORKLOAD_DIR

    reads = read_workload(INITIAL_WORKLOAD)
    writes = read_workload(WORKLOAD_DIR / "workload_3.sql")
    queries = reads + writes
    connection = connect_db()

    try:
        print("Read queries:", len(reads))
        print("Write queries:", len(writes))
        candidates = generate_candidates(queries)
        print("Candidates after pruning:", len(candidates))
        result = optimize_configuration(connection, queries, candidates)

        print("\nOPTIMIZATION RESULTS")
        print("====================")
        print("Solver status:", result["solver_status"])
        print("Candidate count:", result["candidate_count"])
        print("Pairwise profiles:", result["profiled_pairs"])
        print(f"Baseline read cost: {result['baseline_cost']:.2f}")
        print(f"Optimized read cost: {result['read_cost']:.2f}")
        print(f"Write penalty: {result['write_penalty']:.2f}")
        print(f"Storage used: {result['storage_mb']:.2f} MB")
        print("Reconfiguration penalty:", result["reconfiguration_penalty"])
        print(f"Total objective: {result['objective']:.2f}")
        print("Adaptation decision:", result["adaptation_decision"])
        print("\nSELECTED INDEXES")
        for candidate in result["indexes"]:
            print(index_definition(candidate))
        print("Total selected indexes:", len(result["indexes"]))
    finally:
        reset_hypothetical_indexes(connection)
        connection.close()


if __name__ == "__main__":
    main()
