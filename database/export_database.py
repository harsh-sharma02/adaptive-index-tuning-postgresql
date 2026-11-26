import os
import sys
import subprocess
import shutil
from pathlib import Path

import psycopg2

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import (
    DB_HOST,
    DB_PORT,
    DB_NAME,
    DB_USER,
    DB_PASSWORD,
)

DATABASE_DIR = Path(__file__).resolve().parent


def export_schema():
    """Export actual PostgreSQL schema without exporting table data."""

    pg_dump = shutil.which("pg_dump")

    if not pg_dump:
        pg_dump = (
            r"C:\Program Files\PostgreSQL\18\bin\pg_dump.exe"
        )

    if not Path(pg_dump).exists():
        raise FileNotFoundError(
            "pg_dump not found. Check your PostgreSQL installation."
        )

    schema_file = DATABASE_DIR / "schema.sql"

    environment = os.environ.copy()
    environment["PGPASSWORD"] = DB_PASSWORD

    command = [
        pg_dump,
        "-h", DB_HOST,
        "-p", str(DB_PORT),
        "-U", DB_USER,
        "-d", DB_NAME,
        "--schema-only",
        "--no-owner",
        "--no-privileges",
        "-f", str(schema_file),
    ]

    subprocess.run(
        command,
        env=environment,
        check=True,
    )

    print(f"Schema exported: {schema_file}")


def export_documentation():
    """Export actual tables, columns, row counts and relationships."""

    connection = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )

    try:
        with connection.cursor() as cursor:

            cursor.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_type = 'BASE TABLE'
                ORDER BY table_name;
            """)

            tables = [row[0] for row in cursor.fetchall()]

            cursor.execute("""
                SELECT
                    tc.table_name,
                    kcu.column_name,
                    ccu.table_name AS foreign_table,
                    ccu.column_name AS foreign_column
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                 AND tc.constraint_schema = kcu.constraint_schema
                JOIN information_schema.constraint_column_usage ccu
                  ON ccu.constraint_name = tc.constraint_name
                 AND ccu.constraint_schema = tc.constraint_schema
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_schema = 'public'
                ORDER BY tc.table_name, kcu.column_name;
            """)

            relationships = cursor.fetchall()

            lines = [
                f"# Database Overview: {DB_NAME}",
                "",
                f"Database: PostgreSQL",
                f"Schema: public",
                f"Number of tables: {len(tables)}",
                "",
            ]

            for table in tables:

                cursor.execute("""
                    SELECT
                        column_name,
                        data_type,
                        is_nullable,
                        column_default
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = %s
                    ORDER BY ordinal_position;
                """, (table,))

                columns = cursor.fetchall()

                cursor.execute(
                    f'SELECT COUNT(*) FROM public."{table}"'
                )
                row_count = cursor.fetchone()[0]

                lines.extend([
                    f"## {table}",
                    "",
                    f"**Rows:** {row_count:,}",
                    "",
                    "| Column | Data Type | Nullable | Default |",
                    "|---|---|---|---|",
                ])

                for column in columns:
                    name, data_type, nullable, default = column

                    lines.append(
                        f"| {name} | {data_type} | "
                        f"{nullable} | {default or '-'} |"
                    )

                lines.append("")

            lines.extend([
                "## Foreign Key Relationships",
                "",
                "| Table | Column | References | Referenced Column |",
                "|---|---|---|---|",
            ])

            for relation in relationships:
                lines.append(
                    f"| {relation[0]} | {relation[1]} | "
                    f"{relation[2]} | {relation[3]} |"
                )

            lines.extend([
                "",
                "## ER Diagram",
                "",
                "```mermaid",
                "erDiagram",
            ])

            for relation in relationships:
                source, source_column, target, target_column = relation

                lines.append(
                    f'    {target.upper()} ||--o{{ {source.upper()} '
                    f': "{source_column}"'
                )

            lines.append("```")

            overview_file = (
                DATABASE_DIR / "database_overview.md"
            )

            overview_file.write_text(
                "\n".join(lines),
                encoding="utf-8",
            )

            print(f"Documentation exported: {overview_file}")

            diagram_file = DATABASE_DIR / "ER_diagram.md"

            diagram_lines = [
                "# Database ER Diagram",
                "",
                "```mermaid",
                "erDiagram",
            ]

            for relation in relationships:
                source, source_column, target, target_column = relation

                diagram_lines.append(
                    f'    {target.upper()} ||--o{{ {source.upper()} '
                    f': "{source_column}"'
                )

            diagram_lines.append("```")

            diagram_file.write_text(
                "\n".join(diagram_lines),
                encoding="utf-8",
            )

            print(f"ER diagram exported: {diagram_file}")

    finally:
        connection.close()


def main():
    try:
        DATABASE_DIR.mkdir(parents=True, exist_ok=True)

        print("Exporting existing PostgreSQL database...")
        print(f"Database: {DB_NAME}")

        export_schema()
        export_documentation()

        print("\nDatabase export completed successfully.")

    except Exception as error:
        print("\nDatabase export failed:")
        print(error)


if __name__ == "__main__":
    main()
