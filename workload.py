from pathlib import Path
from collections import Counter

import sqlglot
from sqlglot import exp

from config import INITIAL_WORKLOAD


# ==================================================
# HELPER FUNCTIONS
# ==================================================

def normalize_name(name):
    """Convert database identifiers to lowercase."""

    if not name:
        return None

    return name.lower()


def get_table_aliases(statement):
    """Map table names and aliases to actual table names."""

    aliases = {}

    for table in statement.find_all(exp.Table):
        table_name = normalize_name(table.name)
        alias = normalize_name(table.alias)

        if table_name:
            aliases[table_name] = table_name

            if alias:
                aliases[alias] = table_name

    return aliases


def get_column_details(column, aliases, default_table=None):
    """Identify the table and column associated with a SQL column."""

    column_name = normalize_name(column.name)
    table_alias = normalize_name(column.table)

    if table_alias:
        table_name = aliases.get(table_alias, table_alias)
    else:
        table_name = default_table

    return {
        "table": table_name,
        "column": column_name
    }


def extract_columns(expression, aliases, default_table=None):
    """Extract unique columns from a SQL expression."""

    if expression is None:
        return []

    columns = {}

    for column in expression.find_all(exp.Column):
        details = get_column_details(
            column,
            aliases,
            default_table
        )

        if details["column"]:
            key = (
                details["table"],
                details["column"]
            )

            columns[key] = details

    return list(columns.values())


# ==================================================
# QUERY CLASSIFICATION
# ==================================================

def get_query_type(statement):

    if isinstance(statement, exp.Select):
        return "SELECT"

    if isinstance(statement, exp.Insert):
        return "INSERT"

    if isinstance(statement, exp.Update):
        return "UPDATE"

    if isinstance(statement, exp.Delete):
        return "DELETE"

    return "OTHER"


# ==================================================
# QUERY ANALYSIS
# ==================================================

def analyze_query(statement, query_number):

    query_type = get_query_type(statement)

    aliases = get_table_aliases(statement)

    tables = sorted(set(aliases.values()))

    # If only one table is involved, unqualified columns
    # can safely be assigned to that table.
    default_table = tables[0] if len(tables) == 1 else None

    # WHERE columns
    where_columns = extract_columns(
        statement.args.get("where"),
        aliases,
        default_table
    )

    # JOIN columns
    join_columns = []

    for join in statement.find_all(exp.Join):
        join_columns.extend(
            extract_columns(
                join.args.get("on"),
                aliases,
                default_table
            )
        )

    join_columns = list({
        (item["table"], item["column"]): item
        for item in join_columns
    }.values())

    # ORDER BY columns
    order_columns = extract_columns(
        statement.args.get("order"),
        aliases,
        default_table
    )

    # GROUP BY columns
    group_columns = extract_columns(
        statement.args.get("group"),
        aliases,
        default_table
    )

    # Identify target table for write operations
    if query_type in ("INSERT", "UPDATE", "DELETE"):

        target_table = statement.this

        if isinstance(target_table, exp.Schema):
            target_table = target_table.this

        if isinstance(target_table, exp.Table):
            target_name = normalize_name(target_table.name)

            if target_name:
                tables = [target_name]

    return {
        "query_id": query_number,
        "query_type": query_type,
        "sql": statement.sql(dialect="postgres"),
        "tables": tables,
        "where_columns": where_columns,
        "join_columns": join_columns,
        "order_columns": order_columns,
        "group_columns": group_columns
    }


# ==================================================
# WORKLOAD READING
# ==================================================

def read_workload(file_path=None):

    if file_path is None:
        file_path = INITIAL_WORKLOAD

    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(
            f"Workload file not found: {file_path}"
        )

    with open(file_path, "r", encoding="utf-8") as file:
        sql_content = file.read()

    statements = sqlglot.parse(
        sql_content,
        read="postgres"
    )

    queries = []

    for statement in statements:

        if statement is None:
            continue

        queries.append(
            analyze_query(
                statement,
                len(queries) + 1
            )
        )

    return queries


# ==================================================
# WORKLOAD SUMMARY
# ==================================================

def summarize_workload(queries):

    query_types = Counter()
    table_frequency = Counter()
    column_frequency = Counter()

    for query in queries:

        query_types[query["query_type"]] += 1

        for table in query["tables"]:
            table_frequency[table] += 1

        for category in (
            "where_columns",
            "join_columns",
            "order_columns",
            "group_columns"
        ):

            for item in query[category]:

                key = (
                    item["table"],
                    item["column"]
                )

                column_frequency[key] += 1

    return {
        "total_queries": len(queries),
        "query_types": dict(query_types),
        "table_frequency": dict(table_frequency),
        "column_frequency": dict(column_frequency)
    }


# ==================================================
# DISPLAY RESULTS
# ==================================================

def display_workload(queries):

    summary = summarize_workload(queries)

    print("\nWORKLOAD ANALYSIS")
    print("=================")

    print("Total Queries:", summary["total_queries"])

    print("\nQuery Types:")

    for query_type, count in summary["query_types"].items():
        print(f"{query_type}: {count}")

    print("\nTable Usage:")

    for table, count in summary["table_frequency"].items():
        print(f"{table}: {count}")

    print("\nColumn Usage:")

    for (table, column), count in summary["column_frequency"].items():
        print(f"{table}.{column}: {count}")

    print("\nINDIVIDUAL QUERY ANALYSIS")
    print("=========================")

    for query in queries:

        print(
            f"\nQuery {query['query_id']}: "
            f"{query['query_type']}"
        )

        print("Tables:", query["tables"])
        print("WHERE:", query["where_columns"])
        print("JOIN:", query["join_columns"])
        print("ORDER BY:", query["order_columns"])
        print("GROUP BY:", query["group_columns"])


# ==================================================
# MAIN
# ==================================================

def main():

    queries = read_workload()

    display_workload(queries)


if __name__ == "__main__":
    main()
