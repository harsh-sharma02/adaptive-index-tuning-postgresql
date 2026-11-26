import psycopg2
from psycopg2.extras import RealDictCursor

from config import (
    DB_HOST,
    DB_PORT,
    DB_NAME,
    DB_USER,
    DB_PASSWORD
)


def connect_db():

    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )


def get_table_statistics(connection):

    query = """
        SELECT
            schemaname,
            relname AS table_name,
            n_live_tup AS estimated_rows,
            pg_total_relation_size(
                schemaname || '.' || relname
            ) AS total_size_bytes
        FROM pg_stat_user_tables
        ORDER BY relname;
    """

    with connection.cursor(
        cursor_factory=RealDictCursor
    ) as cursor:

        cursor.execute(query)
        return [dict(row) for row in cursor.fetchall()]


def get_column_statistics(connection, table_name):

    query = """
        SELECT
            tablename,
            attname AS column_name,
            null_frac,
            n_distinct,
            most_common_vals,
            most_common_freqs,
            correlation
        FROM pg_stats
        WHERE schemaname = 'public'
          AND tablename = %s
        ORDER BY attname;
    """

    with connection.cursor(
        cursor_factory=RealDictCursor
    ) as cursor:

        cursor.execute(query, (table_name,))
        return [dict(row) for row in cursor.fetchall()]


def explain_query(connection, sql_query):

    with connection.cursor() as cursor:

        cursor.execute(
            "EXPLAIN (FORMAT JSON) " + sql_query
        )

        plan = cursor.fetchone()[0][0]["Plan"]

        return {
            "total_cost": plan["Total Cost"],
            "startup_cost": plan["Startup Cost"],
            "plan_rows": plan["Plan Rows"],
            "plan_width": plan["Plan Width"],
            "plan": plan
        }


def check_hypopg(connection):

    with connection.cursor() as cursor:

        cursor.execute("""
            SELECT extname
            FROM pg_extension
            WHERE extname = 'hypopg';
        """)

        return cursor.fetchone() is not None


def create_hypothetical_index(connection, index_definition):

    with connection.cursor() as cursor:

        cursor.execute(
            "SELECT * FROM hypopg_create_index(%s);",
            (index_definition,)
        )

        return cursor.fetchone()


def reset_hypothetical_indexes(connection):

    with connection.cursor() as cursor:
        cursor.execute("SELECT hypopg_reset();")


def main():

    connection = None

    try:
        connection = connect_db()

        print("Database connection: PASSED")

        print(
            "HypoPG:",
            "PASSED" if check_hypopg(connection) else "NOT PASSED"
        )

        # Refresh PostgreSQL statistics
        with connection.cursor() as cursor:
            cursor.execute("ANALYZE;")

        connection.commit()

        print("Database statistics refreshed: PASSED")

        tables = get_table_statistics(connection)

        print("\nTABLE STATISTICS")

        for table in tables:
            print(
                f"{table['table_name']}: "
                f"{table['estimated_rows']} estimated rows"
            )

    except Exception as error:
        print("Database test: FAILED")
        print(error)

    finally:
        if connection:
            connection.close()


if __name__ == "__main__":
    main()
