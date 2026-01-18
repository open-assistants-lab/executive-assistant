"""Shared DB tools for organization-wide data (admin writes, everyone reads)."""

from typing import Literal

from langchain_core.tools import tool

from cassey.config import settings
from cassey.storage.db_storage import validate_identifier
from cassey.storage.file_sandbox import get_thread_id, get_user_id
from cassey.storage.shared_db_storage import get_shared_db_storage

_shared_db = get_shared_db_storage()


def _is_admin() -> bool:
    """Check whether the current context has admin privileges."""
    user_id = get_user_id()
    thread_id = get_thread_id()

    if user_id and user_id in settings.ADMIN_USER_IDS:
        return True
    if thread_id and thread_id in settings.ADMIN_THREAD_IDS:
        return True
    return False


def _require_admin() -> str | None:
    """Return an error message if admin privileges are missing."""
    if _is_admin():
        return None
    if not settings.ADMIN_USER_IDS and not settings.ADMIN_THREAD_IDS:
        return "Error: Admin access required. Configure ADMIN_USER_IDS or ADMIN_THREAD_IDS in .env."
    return "Error: Admin access required for shared DB writes."


def _ensure_readonly_sql(sql: str) -> str | None:
    """Validate SQL for read-only usage."""
    sql_stripped = sql.strip().lower()
    allowed_prefixes = ("select", "with", "show", "pragma", "describe", "explain")
    if not sql_stripped.startswith(allowed_prefixes):
        return "Error: Read-only query required. Use execute_shared_db for admin writes."
    return None


@tool
def query_shared_db(sql: str) -> str:
    """
    Run a read-only SQL query against the shared DB.

    Args:
        sql: Read-only SQL query (SELECT/SHOW/PRAGMA/EXPLAIN).
    """
    error = _ensure_readonly_sql(sql)
    if error:
        return error

    try:
        results = _shared_db.execute(sql)
        if not results:
            return "Query returned no results"
        return "\n".join("\t".join(str(v) if v is not None else "NULL" for v in row) for row in results)
    except Exception as e:
        return f"Error executing query: {e}"


@tool
def list_shared_db_tables() -> str:
    """List all tables in the shared DB."""
    try:
        tables = _shared_db.list_tables()
        if not tables:
            return "No tables found in shared DB"
        return "Shared DB tables:\n" + "\n".join(f"- {t}" for t in tables)
    except Exception as e:
        return f"Error listing tables: {e}"


@tool
def describe_shared_db_table(table_name: str) -> str:
    """Describe a shared DB table."""
    try:
        validate_identifier(table_name)
        if not _shared_db.table_exists(table_name):
            return f"Error: Table '{table_name}' does not exist"
        columns = _shared_db.get_table_info(table_name)
        lines = [f"Table '{table_name}' schema:"]
        for col in columns:
            nullable = "NULL" if not col["notnull"] else "NOT NULL"
            pk = " PRIMARY KEY" if col["pk"] > 0 else ""
            lines.append(f"- {col['name']}: {col['type']} {nullable}{pk}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error describing table: {e}"


@tool
def export_shared_db_table(
    table_name: str,
    filename: str,
    format: Literal["csv", "parquet", "json"] = "csv",
) -> str:
    """Export a shared DB table to the current context's files directory."""
    try:
        validate_identifier(table_name)
        if not _shared_db.table_exists(table_name):
            return f"Error: Table '{table_name}' does not exist"

        try:
            files_dir = settings.get_context_files_path()
        except ValueError:
            return "Error: No group_id or thread_id in context for export."

        files_dir.mkdir(parents=True, exist_ok=True)

        if not filename.endswith(f".{format}"):
            filename = f"{filename}.{format}"
        output_path = files_dir / filename

        count_result = _shared_db.execute(f"SELECT COUNT(*) FROM {table_name}")
        row_count = count_result[0][0] if count_result else 0

        _shared_db.export_table(table_name, output_path, format)
        return f"Exported '{table_name}' to {filename} ({row_count} rows)"
    except Exception as e:
        return f"Error exporting table: {e}"


@tool
def create_shared_db_table(
    table_name: str,
    data: str,
    columns: str = "",
) -> str:
    """Create a table in the shared DB (admin only)."""
    import json

    admin_error = _require_admin()
    if admin_error:
        return admin_error

    try:
        parsed_data = json.loads(data)
    except json.JSONDecodeError as e:
        return f"Error: Invalid JSON data - {e}"

    column_list = None
    if columns:
        column_list = [col.strip() for col in columns.split(",")]
    elif isinstance(parsed_data, list) and parsed_data and isinstance(parsed_data[0], dict):
        column_list = list(parsed_data[0].keys())
    else:
        return "Error: columns parameter required for array data"

    try:
        _shared_db.create_table_from_data(table_name, parsed_data, column_list)
        return f"Shared table '{table_name}' created with {len(parsed_data)} rows"
    except Exception as e:
        return f"Error creating table: {e}"


@tool
def insert_shared_db_table(
    table_name: str,
    data: str,
) -> str:
    """Insert rows into a shared DB table (admin only)."""
    import json

    admin_error = _require_admin()
    if admin_error:
        return admin_error

    try:
        parsed_data = json.loads(data)
    except json.JSONDecodeError as e:
        return f"Error: Invalid JSON data - {e}"

    if not isinstance(parsed_data, list):
        return "Error: data must be a JSON array"

    try:
        if not _shared_db.table_exists(table_name):
            return f"Error: Table '{table_name}' does not exist"
        _shared_db.append_to_table(table_name, parsed_data)
        return f"Inserted {len(parsed_data)} row(s) into shared table '{table_name}'"
    except Exception as e:
        return f"Error inserting data: {e}"


@tool
def drop_shared_db_table(table_name: str) -> str:
    """Drop a shared DB table (admin only)."""
    admin_error = _require_admin()
    if admin_error:
        return admin_error

    try:
        validate_identifier(table_name)
        if not _shared_db.table_exists(table_name):
            return f"Error: Table '{table_name}' does not exist"
        _shared_db.drop_table(table_name)
        return f"Shared table '{table_name}' dropped"
    except Exception as e:
        return f"Error dropping table: {e}"


@tool
def import_shared_db_table(
    table_name: str,
    filename: str,
) -> str:
    """Import a CSV file into a shared DB table (admin only)."""
    admin_error = _require_admin()
    if admin_error:
        return admin_error

    try:
        validate_identifier(table_name)

        try:
            files_dir = settings.get_context_files_path()
        except ValueError:
            return "Error: No group_id or thread_id in context for import."

        input_path = files_dir / filename
        if not input_path.exists():
            return f"Error: File '{filename}' not found in files directory"

        conn = _shared_db.get_connection()
        try:
            conn.execute(f"DROP TABLE IF EXISTS {table_name}")
            conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM read_csv_auto('{input_path}')")
            count_result = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
            row_count = count_result[0] if count_result else 0
            return f"Imported '{filename}' into shared table '{table_name}' ({row_count} rows)"
        finally:
            conn.close()
    except Exception as e:
        return f"Error importing file: {e}"


@tool
def execute_shared_db(sql: str) -> str:
    """Execute write SQL against shared DB (admin only)."""
    admin_error = _require_admin()
    if admin_error:
        return admin_error

    try:
        _shared_db.execute(sql)
        return "Shared DB command executed successfully."
    except Exception as e:
        return f"Error executing command: {e}"


async def get_shared_db_tools() -> list:
    """Get all shared DB tools."""
    return [
        query_shared_db,
        list_shared_db_tables,
        describe_shared_db_table,
        export_shared_db_table,
        create_shared_db_table,
        insert_shared_db_table,
        drop_shared_db_table,
        import_shared_db_table,
        execute_shared_db,
    ]
