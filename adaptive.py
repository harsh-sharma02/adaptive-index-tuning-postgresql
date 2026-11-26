import re
from collections import Counter


def normalize_sql(sql):
    """Normalize SQL text for exact-pattern workload comparison."""
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    sql = re.sub(r"--.*?$", " ", sql, flags=re.MULTILINE)
    sql = re.sub(r"\s+", " ", sql)
    return sql.strip().rstrip(";").lower()


def compare_workloads(old_queries, new_queries):
    """
    Compare old and new SQL workloads while preserving occurrence counts.
    """
    old_counter = Counter(
        normalize_sql(query["sql"]) for query in old_queries
    )
    new_counter = Counter(
        normalize_sql(query["sql"]) for query in new_queries
    )

    return {
        "added": new_counter - old_counter,
        "removed": old_counter - new_counter,
        "old_count": sum(old_counter.values()),
        "new_count": sum(new_counter.values()),
        "old_unique": len(old_counter),
        "new_unique": len(new_counter),
    }


def _normalize_index(index):
    table = str(index["table"]).strip().strip('"').lower()
    columns = tuple(
        str(column).strip().strip('"').lower()
        for column in index["columns"]
    )
    return table, columns


def unique_indexes(indexes):
    """Remove duplicate index definitions using normalized identities."""
    result = []
    seen = set()

    for index in indexes:
        key = _normalize_index(index)
        if key not in seen:
            seen.add(key)
            result.append(index)

    return result


def compare_indexes(previous, current):
    """Return consistent added, removed and retained index sets."""
    previous_map = {
        _normalize_index(item): item
        for item in unique_indexes(previous)
    }
    current_map = {
        _normalize_index(item): item
        for item in unique_indexes(current)
    }

    previous_keys = set(previous_map)
    current_keys = set(current_map)

    return {
        "added": [
            current_map[key]
            for key in sorted(current_keys - previous_keys)
        ],
        "removed": [
            previous_map[key]
            for key in sorted(previous_keys - current_keys)
        ],
        "retained": [
            current_map[key]
            for key in sorted(previous_keys & current_keys)
        ],
    }


def print_index_changes(previous, current):
    changes = compare_indexes(previous, current)

    for label in ("added", "removed", "retained"):
        print(f"\n{label.capitalize()} indexes:")

        if not changes[label]:
            print("  None")
            continue

        for index in changes[label]:
            table, columns = _normalize_index(index)
            print(f"  {table}({', '.join(columns)})")

    return changes


def _query_structure_signature(query):
    """
    Build a literal-independent query signature from workload parser fields.
    Constants are ignored, but query type, tables and accessed columns remain.
    """
    categories = (
        "where_columns",
        "join_columns",
        "order_columns",
        "group_columns",
    )

    table_names = tuple(sorted(
        str(table).strip().strip('"').lower()
        for table in query.get("tables", [])
    ))

    column_groups = []
    for category in categories:
        entries = set()

        for item in query.get(category, []):
            table = item.get("table")
            column = item.get("column")

            if table and column:
                entries.add((
                    str(table).strip().strip('"').lower(),
                    str(column).strip().strip('"').lower(),
                ))

        column_groups.append((category, tuple(sorted(entries))))

    return (
        str(query.get("query_type", "OTHER")).upper(),
        table_names,
        tuple(column_groups),
    )


def calculate_workload_drift(old_queries, new_queries):
    """
    Frequency-aware structural Jaccard distance.

    0% means identical structural query distributions.
    100% means no structural overlap.
    """
    old_counter = Counter(
        _query_structure_signature(query)
        for query in old_queries
    )
    new_counter = Counter(
        _query_structure_signature(query)
        for query in new_queries
    )

    all_signatures = set(old_counter) | set(new_counter)
    if not all_signatures:
        return 0.0

    intersection = sum(
        min(old_counter[key], new_counter[key])
        for key in all_signatures
    )
    union = sum(
        max(old_counter[key], new_counter[key])
        for key in all_signatures
    )

    if union == 0:
        return 0.0

    return 1.0 - intersection / union


def print_workload_changes(changes):
    print("\nWORKLOAD CHANGES")
    print("================")
    print("Old query count:", changes["old_count"])
    print("New query count:", changes["new_count"])
    print("Old unique queries:", changes["old_unique"])
    print("New unique queries:", changes["new_unique"])

    print("\nAdded query occurrences:", sum(changes["added"].values()))
    print("Removed query occurrences:", sum(changes["removed"].values()))

    if changes["added"]:
        print("\nNew query patterns:")
        for query, count in changes["added"].items():
            print(f"  [{count} occurrence(s)] {query}")

    if changes["removed"]:
        print("\nRemoved query patterns:")
        for query, count in changes["removed"].items():
            print(f"  [{count} occurrence(s)] {query}")
