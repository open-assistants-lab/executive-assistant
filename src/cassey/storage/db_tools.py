"""Database tools for tabular data operations (context-scoped)."""

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


def _get_current_context_id() -> str:
    """Get the current context ID (group_id or thread_id fallback).

    This ensures DB tools respect the group_id context just like file uploads do.

    Raises:
        ValueError: If no context is available.
    """
    from cassey.storage.group_storage import get_workspace_id
    from cassey.storage.db_storage import get_db_storage

    # Try group_id first (team groups and "personal groups")
    workspace_id = get_workspace_id()
    if workspace_id:
        return workspace_id

    # Fallback to thread_id (legacy)
    thread_id = get_thread_id()
    if thread_id:
        return thread_id

    raise ValueError(
        "No context (group_id or thread_id) available. "
        "Database tools must be called from within a channel message handler."
    )


def _get_db() -> SQLiteDatabase:
    """Get the current context's SQLite database.

    Respects group_id context (when set) just like file uploads do.
    This fixes the split storage bug where files and DB were in different directories.
    """
    # Let get_sqlite_db use group_id from context automatically
    return get_sqlite_db()


def _get_db_with_scope(scope: Literal["context", "shared"] = "context") -> SQLiteDatabase:
    """Get database based on scope.

    Args:
        scope: "context" (default) uses group_id/thread_id context,
               "shared" uses organization-wide shared database.

    Returns:
        SQLiteDatabase instance for the requested scope.

    Raises:
        ValueError: If scope is invalid or admin check fails for shared writes.
    """
    if scope == "shared":
        from cassey.storage.shared_db_storage import get_shared_db_storage
        return get_shared_db_storage()
    elif scope == "context":
        return get_sqlite_db()  # Uses group_id/thread_id from context
    else:
        raise ValueError(f"Invalid scope: {scope}. Must be 'context' or 'shared'.")



@tool
@require_permission("write")
def create_db_table(
    table_name: str,
    data: str = "",
    columns: str = "",
    scope: Literal["context", "shared"] = "context",
) -> str:
    """Create a new table for structured data storage. [DB]

    USE THIS WHEN: Starting a new tracking task (timesheets, habits, expenses) or when you need queryable, tabular data for analysis.

    See also: data_management skill for guidance on schema design.

    Args:
        table_name: Name for the new table (letters, numbers, underscore).
        data: JSON array of objects to create table with data.
               Leave empty to create empty table structure.
        columns: Comma-separated column names (e.g., "name,email,phone").
               Required when creating empty table; optional with data.
        scope: "context" (default) for group/thread-scoped storage,
               "shared" for organization-wide shared storage (admin-only writes).

    Returns:
        Success message with row count or table schema.
    """
    import json

    # Handle empty data (create table structure only)
    if not data or not data.strip():
        if not columns:
            return "Error: Either data or columns must be provided"

        column_list = [col.strip() for col in columns.split(",")]
        # Add TEXT type to columns without explicit type
        column_defs = []
        for col in column_list:
            if " " in col:  # Already has type (e.g., "id INTEGER PRIMARY KEY")
                column_defs.append(col)
            else:  # Just column name, add TEXT type
                column_defs.append(f"{col} TEXT")

        try:
            db = _get_db_with_scope(scope)
            db.create_table(table_name, column_defs)
            # Only record metadata for context-scoped DBs
            if scope == "context":
                context_id = _get_current_context_id()
                record_db_path(context_id, db.path)
                record_db_table_added(context_id, table_name)
            col_str = ", ".join(column_defs)
            return f"Table '{table_name}' created with columns: {col_str}"
        except Exception as e:
            return f"Error creating table: {str(e)}"

    # Parse data
    try:
        parsed_data = json.loads(data)
    except json.JSONDecodeError as e:
        return f'Error: Invalid JSON data - {str(e)}. Expected format: \'[{{"name": "Alice", "age": 30}}]\''

    # Determine column names
    column_list = None
    if columns:
        column_list = [col.strip() for col in columns.split(",")]
    elif isinstance(parsed_data, list) and len(parsed_data) > 0 and isinstance(parsed_data[0], dict):
        column_list = list(parsed_data[0].keys())
    else:
        return "Error: columns parameter required for array data"

    try:
        db = _get_db_with_scope(scope)
        db.create_table_from_data(table_name, parsed_data, column_list)
        # Only record metadata for context-scoped DBs
        if scope == "context":
            context_id = _get_current_context_id()
            record_db_path(context_id, db.path)
            record_db_table_added(context_id, table_name)
        return f"Table '{table_name}' created with {len(parsed_data)} rows"
    except Exception as e:
        return f"Error creating table: {str(e)}"


@tool
@require_permission("write")
def insert_db_table(
    table_name: str,
    data: str,
    scope: Literal["context", "shared"] = "context",
) -> str:
    """Add rows to an existing table. [DB]

    USE THIS WHEN: You need to add new records/entries to a table you've already created.

    Args:
        table_name: Name of the table to insert into.
        data: JSON array of objects with keys matching table columns.
        scope: "context" (default) for group/thread-scoped storage,
               "shared" for organization-wide shared storage (admin-only writes).

    Returns:
        Success message with row count.
    """
    import json

    try:
        parsed_data = json.loads(data)
    except json.JSONDecodeError as e:
        return f"Error: Invalid JSON data - {str(e)}"

    if not isinstance(parsed_data, list):
        return "Error: data must be a JSON array"

    try:
        db = _get_db_with_scope(scope)

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
    scope: Literal["context", "shared"] = "context",
) -> str:
    """Execute SQL queries to retrieve, analyze, or modify data. [DB]

    USE THIS WHEN: You need to search/filter data, calculate aggregates (SUM, AVG, COUNT), join tables, or perform complex analysis.

    Database: SQLite (not DuckDB). Use SQLite-compatible syntax.
    - JSON: json_array(), json_extract(), json_each()
    - Dates: date('now'), strftime('%Y-%m-%d', col)

    Args:
        sql: SQL query (SELECT, INSERT, UPDATE, DELETE, etc.).
        scope: "context" (default) for group/thread-scoped storage,
               "shared" for organization-wide shared storage.

    Returns:
        Query results formatted as text table, or rows affected for writes.
    """
    try:
        db = _get_db_with_scope(scope)
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
def list_db_tables(scope: Literal["context", "shared"] = "context") -> str:
    """List all tables in the database. [DB]

    USE THIS WHEN: You need to see what tables exist or verify table names.

    Args:
        scope: "context" (default) for group/thread-scoped storage,
               "shared" for organization-wide shared storage.

    Returns:
        List of table names.
    """
    try:
        db = _get_db_with_scope(scope)
        tables = db.list_tables()

        if not tables:
            return "No tables found in DB"

        return "Tables in DB:\n" + "\n".join(f"- {table}" for table in tables)

    except Exception as e:
        return f"Error listing tables: {str(e)}"


@tool
@require_permission("read")
def describe_db_table(table_name: str, scope: Literal["context", "shared"] = "context") -> str:
    """Get table schema (column names and types). [DB]

    USE THIS WHEN: You need to see what columns exist in a table before querying or inserting data.

    Args:
        table_name: Name of the table to describe.
        scope: "context" (default) for group/thread-scoped storage,
               "shared" for organization-wide shared storage.

    Returns:
        Table schema with column names and types.
    """
    try:
        validate_identifier(table_name)
        db = _get_db_with_scope(scope)

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
def delete_db_table(table_name: str, scope: Literal["context", "shared"] = "context") -> str:
    """Delete a table and all its data. [DB]

    USE THIS WHEN: You need to remove an entire table permanently.

    Warning: This cannot be undone.

    Args:
        table_name: Name of the table to delete.
        scope: "context" (default) for group/thread-scoped storage,
               "shared" for organization-wide shared storage (admin-only writes).

    Returns:
        Success message or error.
    """
    try:
        validate_identifier(table_name)
        db = _get_db_with_scope(scope)

        if not db.table_exists(table_name):
            return f"Error: Table '{table_name}' does not exist"

        db.drop_table(table_name)
        # Only record metadata for context-scoped DBs
        if scope == "context":
            thread_id = _get_current_thread_id()
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
    scope: Literal["context", "shared"] = "context",
) -> str:
    """Export table data to a CSV file. [DB → Files]

    USE THIS WHEN: You need to export data for analysis in other tools, create reports, or backup data.

    Args:
        table_name: Name of the table to export.
        filename: Name for the exported file (extension added automatically).
        format: Export format (only "csv" supported).
        scope: "context" (default) for group/thread-scoped storage,
               "shared" for organization-wide shared storage.

    Returns:
        Success message with file path and row count.
    """
    try:
        validate_identifier(table_name)
        db = _get_db_with_scope(scope)

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
    scope: Literal["context", "shared"] = "context",
) -> str:
    """Import CSV file data into a new table. [Files → DB]

    USE THIS WHEN: You have CSV data in your files directory that you want to query or analyze with SQL.

    Args:
        table_name: Name for the new table.
        filename: Name of the CSV file (must exist in files directory).
        scope: "context" (default) for group/thread-scoped storage,
               "shared" for organization-wide shared storage (admin-only writes).

    Returns:
        Success message with row count.
    """
    try:
        validate_identifier(table_name)

        # Get file path for current context
        files_dir = settings.get_context_files_path()
        input_path = files_dir / filename

        if not input_path.exists():
            return f"Error: File '{filename}' not found in files directory"

        # Import using SQLite's CSV import
        db = _get_db_with_scope(scope)
        row_count = db.import_csv(table_name, input_path)

        # Only record metadata for context-scoped DBs
        if scope == "context":
            context_id = _get_current_context_id()
            record_db_path(context_id, db.path)
            record_db_table_added(context_id, table_name)
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
