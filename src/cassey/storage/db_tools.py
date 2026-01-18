"""Database tools for tabular data operations (workspace/thread-scoped)."""

from contextvars import ContextVar
from pathlib import Path
from typing import Any, Literal

from langchain_core.tools import tool

from cassey.config import settings
from cassey.storage.db_storage import validate_identifier
from cassey.storage.file_sandbox import get_thread_id
from cassey.storage.meta_registry import (
    record_db_path,
    record_db_table_added,
    record_db_table_removed,
)
from cassey.storage.sqlite_db_storage import SQLiteDatabase, get_sqlite_db
from cassey.storage.group_storage import require_permission


# Context variable for thread_id - shared with file_sandbox
# We import get_thread_id from file_sandbox to maintain single source of truth


def _get_current_thread_id() -> str:
    """Get the current thread_id from context.

    Raises:
        ValueError: If thread_id is not available (called outside channel context).
    """
    thread_id = get_thread_id()
    if thread_id is None:
        raise ValueError(
            "No thread_id in context. Database tools must be called from within a channel message handler. "
            "If you're calling this tool directly, make sure to set thread_id context first using "
            "set_thread_id() from cassey.storage.file_sandbox."
        )
    return thread_id


def _get_db() -> SQLiteDatabase:
    """Get the current thread's SQLite database."""
    thread_id = _get_current_thread_id()
    return get_sqlite_db(thread_id)


@tool
@require_permission("write")
def create_db_table(
    table_name: str,
    data: str,
    columns: str = "",
) -> str:
    """
    Create a table in the thread's DB.

    The DB is for temporary working data specific to this conversation.
    For persistent knowledge base storage, use kb_create_table instead.

    The data should be provided as a JSON array of objects or JSON array of arrays.

    Args:
        table_name: Name for the new table (must be a valid SQL identifier).
        data: JSON array of objects (e.g., '[{"a": 1, "b": 2}, {"a": 3, "b": 4}]')
               or JSON array of arrays with columns parameter.
        columns: Comma-separated column names (required if data is array of arrays).
               Example: "name,age,city"

    Returns:
        Success message with row count.

    Examples:
        >>> create_db_table("users", '[{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]')
        "Table 'users' created with 2 rows"

        >>> create_db_table("products", '[["Apple", 1.99], ["Banana", 0.99]]', columns="name,price")
        "Table 'products' created with 2 rows"
    """
    import json

    try:
        parsed_data = json.loads(data)
    except json.JSONDecodeError as e:
        return f"Error: Invalid JSON data - {str(e)}"

    # Determine column names
    column_list = None
    if columns:
        column_list = [col.strip() for col in columns.split(",")]
    elif isinstance(parsed_data, list) and len(parsed_data) > 0 and isinstance(parsed_data[0], dict):
        column_list = list(parsed_data[0].keys())
    else:
        return "Error: columns parameter required for array data"

    try:
        thread_id = _get_current_thread_id()
        db = _get_db()
        db.create_table_from_data(table_name, parsed_data, column_list)
        record_db_path(thread_id, settings.get_thread_db_path(thread_id))
        record_db_table_added(thread_id, table_name)
        return f"Table '{table_name}' created with {len(parsed_data)} rows"
    except Exception as e:
        return f"Error creating table: {str(e)}"


@tool
@require_permission("write")
def insert_db_table(
    table_name: str,
    data: str,
) -> str:
    """
    Insert data into an existing table in the DB.

    The data should be provided as a JSON array of objects with keys matching table columns.

    Args:
        table_name: Name of the table to insert into.
        data: JSON array of objects (e.g., '[{"a": 1, "b": 2}, {"a": 3, "b": 4}]').

    Returns:
        Success message with row count.

    Examples:
        >>> insert_db_table("users", '[{"name": "Charlie", "age": 35}]')
        "Inserted 1 row into 'users'"
    """
    import json

    try:
        parsed_data = json.loads(data)
    except json.JSONDecodeError as e:
        return f"Error: Invalid JSON data - {str(e)}"

    if not isinstance(parsed_data, list):
        return "Error: data must be a JSON array"

    try:
        db = _get_db()

        if not db.table_exists(table_name):
            return f"Error: Table '{table_name}' does not exist"

        db.append_to_table(table_name, parsed_data)
        return f"Inserted {len(parsed_data)} row(s) into '{table_name}'"
    except Exception as e:
        return f"Error inserting data: {str(e)}"


@tool
@require_permission("read")
def query_db(
    sql: str,
) -> str:
    """
    Execute a SQL query on the thread's DB (SQLite).

    IMPORTANT: This database uses SQLite (not DuckDB). Use SQLite-compatible syntax.

    Supported:
    - Standard SQL: SELECT, INSERT, UPDATE, DELETE, CREATE TABLE, DROP TABLE
    - JSON for arrays: json_array(), json_extract(), json_each()
    - Dates: date('now'), datetime('now'), strftime('%Y-%m-%d', col)
    - Auto-increment: INTEGER PRIMARY KEY (automatic)

    Not Supported (DuckDB-specific):
    - Array literals [1,2,3] -> Use json_array(1,2,3)
    - read_csv_auto() -> Use import_db_table tool instead
    - DuckDB-specific functions -> Use SQLite equivalents

    Examples:
    - CREATE TABLE timesheets (id INTEGER PRIMARY KEY, date TEXT, hours REAL, project)
    - INSERT INTO timesheets (date, hours, project) VALUES ('2025-01-17', 4.5, 'Cassey')
    - SELECT * FROM timesheets WHERE date >= date('now', '-7 days')
    - SELECT * FROM timesheets WHERE EXISTS (SELECT 1 FROM json_each(tags) WHERE value = 'billing')

    For help with SQLite syntax, use the sqlite_guide tool.

    Args:
        sql: SQL query to execute (can be SELECT, PRAGMA, etc.).

    Returns:
        Query results formatted as text table.
    """
    try:
        db = _get_db()
        cursor = db.execute(sql)

        # Handle different query types
        sql_upper = sql.strip().upper()

        if sql_upper.startswith(("SELECT", "PRAGMA", "EXPLAIN")):
            # Return results
            rows = cursor.fetchall()
            if not rows:
                return "Query returned 0 rows"

            # Get column names
            columns = [desc[0] for desc in cursor.description] if cursor.description else []

            # Format as text table
            return _format_query_results(columns, rows)
        else:
            # Write operation
            db.conn.commit()
            rows_affected = cursor.rowcount
            return f"Query executed successfully. Rows affected: {rows_affected}"

    except Exception as e:
        return f"Error executing SQL: {str(e)}"


def _format_query_results(columns: list[str], rows: list[tuple]) -> str:
    """Format query results as readable string."""
    if not rows:
        return "Query returned 0 rows"

    # Calculate column widths
    col_widths = {col: len(col) for col in columns}
    for row in rows:
        for i, val in enumerate(row):
            val_str = str(val) if val is not None else "NULL"
            col_widths[columns[i]] = max(col_widths[columns[i]], len(val_str))

    # Build output
    output = []
    output.append(" | ".join(col.ljust(col_widths[col]) for col in columns))
    output.append("-+-".join("-" * col_widths[col] for col in columns))

    for row in rows:
        vals = [str(row[i]) if row[i] is not None else "NULL" for i in range(len(columns))]
        output.append(" | ".join(val.ljust(col_widths[columns[i]]) for i, val in enumerate(vals)))

    return "\n".join(output)


@tool
@require_permission("read")
def list_db_tables() -> str:
    """
    List all tables in the thread's DB.

    Returns:
        List of table names.

    Examples:
        >>> list_db_tables()
        "Tables in DB:\\n- users\\n- products"
    """
    try:
        db = _get_db()
        tables = db.list_tables()

        if not tables:
            return "No tables found in DB"

        return "Tables in DB:\n" + "\n".join(f"- {table}" for table in tables)

    except Exception as e:
        return f"Error listing tables: {str(e)}"


@tool
@require_permission("read")
def describe_db_table(table_name: str) -> str:
    """
    Get schema information for a table.

    Args:
        table_name: Name of the table to describe.

    Returns:
        Table schema with column names and types.

    Examples:
        >>> describe_db_table("users")
        "Table 'users' schema:\\n- name: TEXT\\n- age: INTEGER"
    """
    try:
        validate_identifier(table_name)
        db = _get_db()

        if not db.table_exists(table_name):
            return f"Error: Table '{table_name}' does not exist"

        columns = db.get_table_info(table_name)

        lines = [f"Table '{table_name}' schema:"]
        for col in columns:
            nullable = "NULL" if not col["notnull"] else "NOT NULL"
            pk = " PRIMARY KEY" if col["pk"] > 0 else ""
            lines.append(f"- {col['name']}: {col['type']} {nullable}{pk}")

        return "\n".join(lines)

    except Exception as e:
        return f"Error describing table: {str(e)}"


@tool
@require_permission("write")
def delete_db_table(table_name: str) -> str:
    """
    Drop a table from the DB.

    Args:
        table_name: Name of the table to drop.

    Returns:
        Success message or error.

    Examples:
        >>> delete_db_table("old_table")
        "Table 'old_table' dropped"
    """
    try:
        validate_identifier(table_name)
        thread_id = _get_current_thread_id()
        db = _get_db()

        if not db.table_exists(table_name):
            return f"Error: Table '{table_name}' does not exist"

        db.drop_table(table_name)
        record_db_table_removed(thread_id, table_name)
        return f"Table '{table_name}' dropped"

    except Exception as e:
        return f"Error dropping table: {str(e)}"


@tool
@require_permission("write")
def export_db_table(
    table_name: str,
    filename: str,
    format: Literal["csv"] = "csv",
) -> str:
    """
    Export a group table to a file in the context's file directory.

    Args:
        table_name: Name of the table to export.
        filename: Name for the exported file (extension added automatically).
        format: Export format - only "csv" is supported.

    Returns:
        Success message with file path.

    Examples:
        >>> export_db_table("users", "my_data", "csv")
        "Exported 'users' to files/.../my_data.csv (2 rows)"
    """
    try:
        validate_identifier(table_name)
        db = _get_db()

        if not db.table_exists(table_name):
            return f"Error: Table '{table_name}' does not exist"

        # Get file path for current context
        files_dir = settings.get_context_files_path()
        files_dir.mkdir(parents=True, exist_ok=True)

        # Add extension if not present
        if not filename.endswith(f".{format}"):
            filename = f"{filename}.{format}"

        output_path = files_dir / filename

        # Get row count
        count_result = db.execute(f"SELECT COUNT(*) FROM {table_name}")
        row = count_result.fetchone()
        row_count = row[0] if row else 0

        # Export
        db.export_table(table_name, output_path, format)

        return f"Exported '{table_name}' to {filename} ({row_count} rows)"

    except Exception as e:
        return f"Error exporting table: {str(e)}"


@tool
@require_permission("write")
def import_db_table(
    table_name: str,
    filename: str,
) -> str:
    """
    Import a CSV file into a new DB table.

    The file must exist in the context's file directory.

    Args:
        table_name: Name for the new table.
        filename: Name of the CSV file to import (must exist in files directory).

    Returns:
        Success message with row count.

    Examples:
        >>> import_db_table("sales", "sales_data.csv")
        "Imported 'sales_data.csv' into table 'sales' (150 rows)"
    """
    try:
        validate_identifier(table_name)

        # Get file path for current context
        files_dir = settings.get_context_files_path()
        input_path = files_dir / filename

        if not input_path.exists():
            return f"Error: File '{filename}' not found in files directory"

        # Import using SQLite's CSV import
        db = _get_db()
        row_count = db.import_csv(table_name, input_path)

        record_db_path(thread_id, settings.get_thread_db_path(thread_id))
        record_db_table_added(thread_id, table_name)
        return f"Imported '{filename}' into table '{table_name}' ({row_count} rows)"

    except Exception as e:
        return f"Error importing file: {str(e)}"


# Export list of tools for use in agent
async def get_db_tools() -> list:
    """Get all DB tools for use in the agent."""
    return [
        create_db_table,
        insert_db_table,
        query_db,
        list_db_tables,
        describe_db_table,
        delete_db_table,
        export_db_table,
        import_db_table,
    ]
