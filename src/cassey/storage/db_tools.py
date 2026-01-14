"""Database tools for tabular data operations."""

from contextvars import ContextVar
from pathlib import Path
from typing import Any, Literal

from langchain_core.tools import tool

from cassey.config import settings
from cassey.storage.db_storage import DBStorage
from cassey.storage.file_sandbox import get_thread_id
from cassey.storage.user_registry import sanitize_thread_id


# Global database storage instance
_db_storage = DBStorage()


# Context variable for thread_id - shared with file_sandbox
# We import get_thread_id from file_sandbox to maintain single source of truth


def _get_current_thread_id() -> str:
    """Get the current thread_id from context."""
    thread_id = get_thread_id()
    if thread_id is None:
        raise ValueError(
            "No thread_id in context. "
            "Database tools must be called from within a channel message handler."
        )
    return thread_id


@tool
def create_table(
    table_name: str,
    data: str,
    columns: str = "",
) -> str:
    """
    Create a database table from tabular data.

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
        >>> create_table("users", '[{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]')
        "Table 'users' created with 2 rows"

        >>> create_table("products", '[["Apple", 1.99], ["Banana", 0.99]]', columns="name,price")
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
        _db_storage.create_table_from_data(table_name, parsed_data, column_list, thread_id)
        return f"Table '{table_name}' created with {len(parsed_data)} rows"
    except Exception as e:
        return f"Error creating table: {str(e)}"


@tool
def insert_table(
    table_name: str,
    data: str,
) -> str:
    """
    Insert data into an existing database table.

    The data should be provided as a JSON array of objects with keys matching table columns.

    Args:
        table_name: Name of the table to insert into.
        data: JSON array of objects (e.g., '[{"a": 1, "b": 2}, {"a": 3, "b": 4}]').

    Returns:
        Success message with row count.

    Examples:
        >>> insert_table("users", '[{"name": "Charlie", "age": 35}]')
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
        thread_id = _get_current_thread_id()
        if not _db_storage.table_exists(table_name, thread_id):
            return f"Error: Table '{table_name}' does not exist"

        _db_storage.append_to_table(table_name, parsed_data, thread_id)
        return f"Inserted {len(parsed_data)} row(s) into '{table_name}'"
    except Exception as e:
        return f"Error inserting data: {str(e)}"


@tool
def query_table(
    sql: str,
) -> str:
    """
    Execute a SQL query on the thread's database.

    Args:
        sql: SQL query to execute (can be SELECT, SHOW TABLES, etc.).

    Returns:
        Query results formatted as text table.

    Examples:
        >>> query_table("SELECT * FROM users LIMIT 10")
        "name  | age\\nAlice | 30\\nBob   | 25"

        >>> query_table("SHOW TABLES")
        "users\\nproducts"
    """
    try:
        thread_id = _get_current_thread_id()
        results = _db_storage.execute(sql, thread_id)

        if not results:
            return "Query returned no results"

        # Format results as text table
        if len(results) == 0:
            return "Query returned 0 rows"

        # Get column names from description if available
        # For now, just format as tab-separated
        lines = []
        for row in results:
            lines.append("\t".join(str(v) if v is not None else "NULL" for v in row))

        return "\n".join(lines)

    except Exception as e:
        return f"Error executing query: {str(e)}"


@tool
def list_tables() -> str:
    """
    List all tables in the thread's database.

    Returns:
        List of table names.

    Examples:
        >>> list_tables()
        "Tables in current thread:\\n- users\\n- products"
    """
    try:
        thread_id = _get_current_thread_id()
        tables = _db_storage.list_tables(thread_id)

        if not tables:
            return "No tables found in current thread's database"

        return "Tables in current thread:\n" + "\n".join(f"- {table}" for table in tables)

    except Exception as e:
        return f"Error listing tables: {str(e)}"


@tool
def describe_table(table_name: str) -> str:
    """
    Get schema information for a table.

    Args:
        table_name: Name of the table to describe.

    Returns:
        Table schema with column names and types.

    Examples:
        >>> describe_table("users")
        "Table 'users' schema:\\n- name: VARCHAR\\n- age: INTEGER"
    """
    try:
        thread_id = _get_current_thread_id()

        if not _db_storage.table_exists(table_name, thread_id):
            return f"Error: Table '{table_name}' does not exist"

        columns = _db_storage.get_table_info(table_name, thread_id)

        lines = [f"Table '{table_name}' schema:"]
        for col in columns:
            nullable = "NULL" if not col["notnull"] else "NOT NULL"
            pk = " PRIMARY KEY" if col["pk"] > 0 else ""
            lines.append(f"- {col['name']}: {col['type']} {nullable}{pk}")

        return "\n".join(lines)

    except Exception as e:
        return f"Error describing table: {str(e)}"


@tool
def drop_table(table_name: str) -> str:
    """
    Drop a table from the thread's database.

    Args:
        table_name: Name of the table to drop.

    Returns:
        Success message or error.

    Examples:
        >>> drop_table("old_table")
        "Table 'old_table' dropped"
    """
    try:
        thread_id = _get_current_thread_id()

        if not _db_storage.table_exists(table_name, thread_id):
            return f"Error: Table '{table_name}' does not exist"

        _db_storage.drop_table(table_name, thread_id)
        return f"Table '{table_name}' dropped"

    except Exception as e:
        return f"Error dropping table: {str(e)}"


@tool
def export_table(
    table_name: str,
    filename: str,
    format: Literal["csv", "parquet", "json"] = "csv",
) -> str:
    """
    Export a table to a file in the thread's file directory.

    Args:
        table_name: Name of the table to export.
        filename: Name for the exported file (extension added automatically).
        format: Export format - "csv", "parquet", or "json".

    Returns:
        Success message with file path.

    Examples:
        >>> export_table("users", "my_data", "csv")
        "Exported 'users' to files/.../my_data.csv (2 rows)"
    """
    try:
        thread_id = _get_current_thread_id()

        if not _db_storage.table_exists(table_name, thread_id):
            return f"Error: Table '{table_name}' does not exist"

        # Get file path for current thread
        safe_thread_id = sanitize_thread_id(thread_id)
        files_dir = settings.FILES_ROOT / safe_thread_id
        files_dir.mkdir(parents=True, exist_ok=True)

        # Add extension if not present
        if not filename.endswith(f".{format}"):
            filename = f"{filename}.{format}"

        output_path = files_dir / filename

        # Get row count
        count_result = _db_storage.execute(f"SELECT COUNT(*) FROM {table_name}", thread_id)
        row_count = count_result[0][0] if count_result else 0

        # Export
        _db_storage.export_table(table_name, output_path, format, thread_id)

        return f"Exported '{table_name}' to {filename} ({row_count} rows)"

    except Exception as e:
        return f"Error exporting table: {str(e)}"


@tool
def import_table(
    table_name: str,
    filename: str,
) -> str:
    """
    Import a CSV file into a new database table.

    The file must exist in the thread's file directory.

    Args:
        table_name: Name for the new table.
        filename: Name of the CSV file to import (must exist in files directory).

    Returns:
        Success message with row count.

    Examples:
        >>> import_table("sales", "sales_data.csv")
        "Imported 'sales_data.csv' into table 'sales' (150 rows)"
    """
    try:
        thread_id = _get_current_thread_id()

        # Get file path for current thread
        safe_thread_id = sanitize_thread_id(thread_id)
        files_dir = settings.FILES_ROOT / safe_thread_id
        input_path = files_dir / filename

        if not input_path.exists():
            return f"Error: File '{filename}' not found in thread's files directory"

        # Use database to import
        conn = _db_storage.get_connection(thread_id)
        try:
            # Drop table if exists
            conn.execute(f"DROP TABLE IF EXISTS {table_name}")

            # Create table from CSV
            conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM read_csv_auto('{input_path}')")

            # Get row count
            count_result = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
            row_count = count_result[0] if count_result else 0

            return f"Imported '{filename}' into table '{table_name}' ({row_count} rows)"
        finally:
            conn.close()

    except Exception as e:
        return f"Error importing file: {str(e)}"


# Export list of tools for use in agent
async def get_db_tools() -> list:
    """Get all database tools for use in the agent."""
    return [
        create_table,
        insert_table,
        query_table,
        list_tables,
        describe_table,
        drop_table,
        export_table,
        import_table,
    ]
