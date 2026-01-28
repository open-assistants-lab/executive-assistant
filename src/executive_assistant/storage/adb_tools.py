"""DuckDB adb tools (context-scoped)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from langchain_core.tools import tool

from executive_assistant.config.settings import settings
from executive_assistant.storage.adb_storage import get_adb
from executive_assistant.storage.thread_storage import require_permission
from executive_assistant.storage.file_sandbox import get_sandbox


Scope = Literal["context"]


def _split_sql_statements(sql: str) -> list[str]:
    """Split SQL string into statements, respecting quotes."""
    statements: list[str] = []
    current: list[str] = []
    in_single_quote = False
    in_double_quote = False

    for ch in sql:
        if ch == "'" and not in_double_quote:
            in_single_quote = not in_single_quote
        elif ch == '"' and not in_single_quote:
            in_double_quote = not in_double_quote

        if ch == ";" and not in_single_quote and not in_double_quote:
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
            continue

        current.append(ch)

    tail = "".join(current).strip()
    if tail:
        statements.append(tail)

    return statements


def _format_query_results(columns: list[str], rows: list[tuple]) -> str:
    if not rows:
        return "Query returned 0 rows"

    col_widths = {col: len(col) for col in columns}
    for row in rows:
        for i, val in enumerate(row):
            val_str = str(val) if val is not None else "NULL"
            col_widths[columns[i]] = max(col_widths[columns[i]], len(val_str))

    output: list[str] = []
    output.append(" | ".join(col.ljust(col_widths[col]) for col in columns))
    output.append("-+-".join("-" * col_widths[col] for col in columns))

    for row in rows:
        vals = [str(row[i]) if row[i] is not None else "NULL" for i in range(len(columns))]
        output.append(" | ".join(val.ljust(col_widths[columns[i]]) for i, val in enumerate(vals)))

    return "\n".join(output)


@tool("list_adb_tables", description="List tables in the analytics DuckDB (ADB).")
@require_permission("read")
def list_adb_tables(scope: Scope = "context") -> str:
    """List tables in the DuckDB ADB (context-scoped). [ADB]

    USE THIS WHEN: You want to see available tables in the analytics DB.

    Args:
        scope: "context" (default) for thread-scoped ADB.

    Returns:
        List of table names.
    """
    try:
        conn = get_adb(scope)
        rows = conn.execute("SHOW TABLES").fetchall()
        if not rows:
            return "No tables found"
        return "Tables:\n" + "\n".join(f"- {r[0]}" for r in rows)
    except Exception as e:
        return f"Error listing ADB tables: {str(e)}"


@tool("describe_adb_table", description="Get schema/info for an ADB table.")
@require_permission("read")
def describe_adb_table(table_name: str, scope: Scope = "context") -> str:
    """Describe the schema of an ADB table. [ADB]

    USE THIS WHEN: You need to see column names, types, or table structure.

    Args:
        table_name: Name of the table to describe.
        scope: "context" (default) for thread-scoped ADB.

    Returns:
        Table schema with column names and types.
    """
    try:
        conn = get_adb(scope)
        
        # Get column info
        rows = conn.execute(f"DESCRIBE {table_name}").fetchall()
        if not rows:
            return f"Table '{table_name}' not found or has no columns"
        
        # Get row count
        count_result = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
        row_count = count_result[0] if count_result else 0
        
        output = [f"Table: {table_name}", f"Rows: {row_count}", ""]
        output.append("Columns:")
        output.append(f"{'Column':<30} {'Type':<20} {'Nullable':<10}")
        output.append("-" * 60)
        
        for row in rows:
            col_name = row[0]
            col_type = row[1] if len(row) > 1 else "UNKNOWN"
            nullable = row[2] if len(row) > 2 else "YES"
            output.append(f"{col_name:<30} {col_type:<20} {nullable:<10}")
        
        return "\n".join(output)
    except Exception as e:
        return f"Error describing table '{table_name}': {str(e)}"


@tool("create_adb_table", description="Create a table in ADB from JSON data or CSV.")
@require_permission("write")
def create_adb_table(
    table_name: str,
    data: str | None = None,
    csv_file: str | None = None,
    json_file: str | None = None,
    scope: Scope = "context"
) -> str:
    """Create a table in ADB from data or file. [ADB]

    USE THIS WHEN: You need to create a new table for analytics.

    Args:
        table_name: Name for the new table.
        data: JSON string with array of objects (optional).
        csv_file: Path to CSV file to import (optional).
        json_file: Path to JSON file to import (optional).
        scope: "context" (default) for thread-scoped ADB.

    Returns:
        Success message with row count.
    """
    try:
        conn = get_adb(scope)
        
        if csv_file:
            # Import from CSV
            sandbox = get_sandbox()
            csv_path = sandbox._validate_path(csv_file)
            conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM read_csv_auto('{csv_path}')")
            count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            return f"Created table '{table_name}' from CSV with {count} rows"
        
        elif json_file:
            # Import from JSON
            sandbox = get_sandbox()
            json_path = sandbox._validate_path(json_file)
            conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM read_json_auto('{json_path}')")
            count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            return f"Created table '{table_name}' from JSON with {count} rows"
        
        elif data:
            # Import from JSON string
            records = json.loads(data)
            if not records:
                return "Error: No data provided"
            
            # Create table from first record schema
            if isinstance(records, list) and len(records) > 0:
                first_record = records[0]
            else:
                return "Error: Data must be a non-empty array of objects"
            
            # Build CREATE TABLE
            columns = []
            for col, val in first_record.items():
                col_type = "VARCHAR"
                if isinstance(val, int):
                    col_type = "INTEGER"
                elif isinstance(val, float):
                    col_type = "DOUBLE"
                elif isinstance(val, bool):
                    col_type = "BOOLEAN"
                columns.append(f"{col} {col_type}")
            
            create_sql = f"CREATE TABLE {table_name} ({', '.join(columns)})"
            conn.execute(create_sql)
            
            # Insert data
            for record in records:
                cols = list(record.keys())
                placeholders = ["?"] * len(cols)
                values = [record.get(col) for col in cols]
                insert_sql = f"INSERT INTO {table_name} ({', '.join(cols)}) VALUES ({', '.join(placeholders)})"
                conn.execute(insert_sql, values)
            
            return f"Created table '{table_name}' with {len(records)} rows"
        
        else:
            return "Error: Must provide data, csv_file, or json_file"
            
    except json.JSONDecodeError as e:
        return f"Error: Invalid JSON data - {str(e)}"
    except Exception as e:
        return f"Error creating table '{table_name}': {str(e)}"


@tool("import_adb_csv", description="Import CSV file into ADB table.")
@require_permission("write")
def import_adb_csv(
    csv_file: str,
    table_name: str | None = None,
    header: bool = True,
    delimiter: str = ",",
    scope: Scope = "context"
) -> str:
    """Import a CSV file into an ADB table. [ADB]

    USE THIS WHEN: You have a CSV file to analyze with SQL.

    Args:
        csv_file: Path to the CSV file.
        table_name: Name for the table (defaults to filename without extension).
        header: Whether CSV has header row (default: True).
        delimiter: Field delimiter (default: comma).
        scope: "context" (default) for thread-scoped ADB.

    Returns:
        Success message with row count.
    """
    try:
        conn = get_adb(scope)
        sandbox = get_sandbox()
        
        # Validate CSV path
        csv_path = sandbox._validate_path(csv_file)
        
        # Determine table name
        if not table_name:
            table_name = Path(csv_file).stem
        
        # Import CSV
        header_option = "true" if header else "false"
        conn.execute(f"""
            CREATE TABLE {table_name} AS 
            SELECT * FROM read_csv_auto('{csv_path}', 
                header={header_option}, 
                delim='{delimiter}'
            )
        """)
        
        count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        columns = conn.execute(f"DESCRIBE {table_name}").fetchall()
        
        return f"Imported '{csv_file}' into table '{table_name}': {count} rows, {len(columns)} columns"
    
    except Exception as e:
        return f"Error importing CSV: {str(e)}"


@tool("export_adb_table", description="Export ADB table to CSV, JSON, or Parquet.")
@require_permission("read")
def export_adb_table(
    table_name: str,
    output_file: str,
    format: Literal["csv", "json", "parquet"] = "csv",
    scope: Scope = "context"
) -> str:
    """Export an ADB table to a file. [ADB]

    USE THIS WHEN: You need to save query results or share data.

    Args:
        table_name: Table to export (or SQL query).
        output_file: Path for the output file.
        format: Export format - csv, json, or parquet (default: csv).
        scope: "context" (default) for thread-scoped ADB.

    Returns:
        Success message with file path.
    """
    try:
        conn = get_adb(scope)
        sandbox = get_sandbox()
        
        # Validate output path
        output_path = sandbox._validate_path(output_file)
        
        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Export based on format
        if format == "csv":
            conn.execute(f"COPY (SELECT * FROM {table_name}) TO '{output_path}' (HEADER, DELIMITER ',')")
        elif format == "json":
            conn.execute(f"COPY (SELECT * FROM {table_name}) TO '{output_path}' (ARRAY)")
        elif format == "parquet":
            conn.execute(f"COPY (SELECT * FROM {table_name}) TO '{output_path}' (FORMAT PARQUET)")
        else:
            return f"Error: Unsupported format '{format}'"
        
        # Get file size
        size_bytes = output_path.stat().st_size
        size_kb = size_bytes / 1024
        
        return f"Exported '{table_name}' to '{output_file}' ({format}, {size_kb:.1f} KB)"
    
    except Exception as e:
        return f"Error exporting table: {str(e)}"


@tool("drop_adb_table", description="Delete an ADB table.")
@require_permission("write")
def drop_adb_table(table_name: str, if_exists: bool = True, scope: Scope = "context") -> str:
    """Drop (delete) a table from ADB. [ADB]

    USE THIS WHEN: You need to remove a table or replace it.

    Args:
        table_name: Name of the table to drop.
        if_exists: Only drop if table exists (default: True).
        scope: "context" (default) for thread-scoped ADB.

    Returns:
        Success message.
    """
    try:
        conn = get_adb(scope)
        
        if_exists_clause = "IF EXISTS" if if_exists else ""
        conn.execute(f"DROP TABLE {if_exists_clause} {table_name}")
        
        return f"Dropped table '{table_name}'"
    
    except Exception as e:
        return f"Error dropping table '{table_name}': {str(e)}"


@tool("show_adb_schema", description="Show complete database schema overview.")
@require_permission("read")
def show_adb_schema(scope: Scope = "context") -> str:
    """Show schema overview of all tables in ADB. [ADB]

    USE THIS WHEN: You need to understand the database structure.

    Args:
        scope: "context" (default) for thread-scoped ADB.

    Returns:
        Schema overview with all tables and columns.
    """
    try:
        conn = get_adb(scope)
        
        # Get all tables
        tables = conn.execute("SHOW TABLES").fetchall()
        if not tables:
            return "No tables in database"
        
        output = [f"Database Schema: {len(tables)} table(s)", ""]
        
        for table_row in tables:
            table_name = table_row[0]
            
            # Get row count
            count_result = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
            row_count = count_result[0] if count_result else 0
            
            output.append(f"Table: {table_name} ({row_count} rows)")
            
            # Get columns
            cols = conn.execute(f"DESCRIBE {table_name}").fetchall()
            for col in cols:
                col_name = col[0]
                col_type = col[1] if len(col) > 1 else "?"
                output.append(f"  - {col_name}: {col_type}")
            
            output.append("")
        
        return "\n".join(output)
    
    except Exception as e:
        return f"Error showing schema: {str(e)}"


@tool("optimize_adb", description="Optimize ADB database (VACUUM, ANALYZE).")
@require_permission("write")
def optimize_adb(scope: Scope = "context") -> str:
    """Optimize the ADB database for better performance. [ADB]

    USE THIS WHEN: Queries are slow or after large data changes.

    Args:
        scope: "context" (default) for thread-scoped ADB.

    Returns:
        Optimization results.
    """
    try:
        conn = get_adb(scope)
        
        # Run optimization
        conn.execute("ANALYZE")
        conn.execute("CHECKPOINT")
        
        # Get database size
        db_path = settings.get_thread_root(get_adb._thread_id if hasattr(get_adb, '_thread_id') else "unknown") / "adb" / "duckdb.db"
        size_mb = 0
        if db_path.exists():
            size_mb = db_path.stat().st_size / (1024 * 1024)
        
        return f"Database optimized. Size: {size_mb:.1f} MB"
    
    except Exception as e:
        return f"Error optimizing database: {str(e)}"


@tool("query_adb", description="Run a SQL query against the analytics DuckDB (ADB).")
@require_permission("read")
def query_adb(sql: str, scope: Scope = "context") -> str:
    """Run DuckDB SQL for adb (context-scoped). [ADB]

    USE THIS WHEN: You need fast adb, joins, or large-file analysis.

    Args:
        sql: DuckDB SQL query to execute.
        scope: "context" (default) for thread-scoped adb DB.

    Returns:
        Query results as formatted text.
    """
    try:
        conn = get_adb(scope)
        statements = _split_sql_statements(sql)
        if not statements:
            return "No SQL provided"

        last_cursor = None
        for statement in statements:
            last_cursor = conn.execute(statement)

        if last_cursor is None:
            return "No statements executed"

        if last_cursor.description is None:
            return "Query executed successfully"

        columns = [col[0] for col in last_cursor.description]
        rows = last_cursor.fetchall()
        return _format_query_results(columns, rows)

    except Exception as e:
        return f"Error executing adb query: {str(e)}"


async def get_adb_tools() -> list:
    return [
        list_adb_tables,
        describe_adb_table,
        create_adb_table,
        import_adb_csv,
        export_adb_table,
        drop_adb_table,
        show_adb_schema,
        optimize_adb,
        query_adb,
    ]
