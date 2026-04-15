"""App tools — SDK-native implementation.

Structured data apps using SQLite + FTS5 + ChromaDB for full-text
and semantic search. Each app has tables with typed columns, and
TEXT columns automatically get FTS5 + vector search.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from src.app_logging import get_logger
from src.sdk.tools import ToolAnnotations, tool
from src.sdk.tools_core.apps_storage import AppStorage

logger = get_logger()


def _get_storage(user_id: str) -> AppStorage:
    return AppStorage(user_id)


@tool
def app_create(name: str, tables: dict[str, dict[str, str]], user_id: str = "default") -> str:
    """Create a new app with one or more tables.

    Args:
        name: App name (e.g., 'pos', 'project', 'wine')
        tables: Dict of {table_name: {column: type}} where type is TEXT, INTEGER, REAL, BOOLEAN.
               Text columns get FTS5 + sqlite-vec automatically
        user_id: User identifier

    Returns:
        Success message with app details
    """
    try:
        storage = _get_storage(user_id)
        app_schema = storage.create_app(name, tables)

        tables_info = []
        for tname, tschema in app_schema.tables.items():
            text_cols = ", ".join(tschema.text_columns) if tschema.text_columns else "none"
            tables_info.append(f"  - {tname}: {list(tschema.columns.keys())} (text: {text_cols})")

        return f"App '{name}' created successfully.\n\nTables:\n" + "\n".join(tables_info)
    except Exception as e:
        logger.error("app_create.error", {"name": name, "error": str(e)}, user_id=user_id)
        return f"Error creating app: {e}"


app_create.annotations = ToolAnnotations(title="Create App", destructive=True)


@tool
def app_list(user_id: str = "default") -> str:
    """List all apps the user has created.

    Args:
        user_id: User identifier

    Returns:
        List of app names
    """
    try:
        storage = _get_storage(user_id)
        apps = storage.list_apps()

        if not apps:
            return "No apps found. Create one with app_create()."

        return "Apps:\n" + "\n".join(f"  - {app}" for app in sorted(apps))
    except Exception as e:
        logger.error("app_list.error", {"error": str(e)}, user_id=user_id)
        return f"Error listing apps: {e}"


app_list.annotations = ToolAnnotations(title="List Apps", read_only=True, idempotent=True)


@tool
def app_schema(name: str, user_id: str = "default") -> str:
    """Get schema for an app.

    Args:
        name: App name
        user_id: User identifier

    Returns:
        App schema details with all tables
    """
    try:
        storage = _get_storage(user_id)
        schema = storage.get_schema(name)

        if not schema:
            return f"App '{name}' not found."

        lines = [f"App: {name}", "", "Tables:"]

        for tname, tschema in schema.tables.items():
            columns_str = ", ".join(f"{col}: {typ}" for col, typ in tschema.columns.items())
            text_cols = ", ".join(tschema.text_columns) if tschema.text_columns else "none"
            lines.append(f"  - {tname}: {columns_str}")
            lines.append(f"    Text columns (FTS5 + vec): {text_cols}")

        return "\n".join(lines)
    except Exception as e:
        logger.error("app_schema.error", {"name": name, "error": str(e)}, user_id=user_id)
        return f"Error getting schema: {e}"


app_schema.annotations = ToolAnnotations(title="App Schema", read_only=True, idempotent=True)


@tool
def app_delete(name: str, user_id: str = "default") -> str:
    """Delete an app and all its data.

    Args:
        name: App name to delete
        user_id: User identifier

    Returns:
        Success or error message
    """
    try:
        storage = _get_storage(user_id)
        if storage.delete_app(name):
            return f"App '{name}' deleted successfully."
        return f"App '{name}' not found."
    except Exception as e:
        logger.error("app_delete.error", {"name": name, "error": str(e)}, user_id=user_id)
        return f"Error deleting app: {e}"


app_delete.annotations = ToolAnnotations(title="Delete App", destructive=True)


@tool
def app_insert(app: str, table: str, data: dict[str, Any], user_id: str = "default") -> str:
    """Insert a row into a table.

    Args:
        app: App name
        table: Table name
        data: Dict of column: value pairs
        user_id: User identifier

    Returns:
        Success or error message
    """
    try:
        storage = _get_storage(user_id)
        row_id = storage.insert(app, table, data)
        return f"Inserted row {row_id} into '{app}.{table}'."
    except Exception as e:
        logger.error(
            "app_insert.error", {"app": app, "table": table, "error": str(e)}, user_id=user_id
        )
        return f"Error inserting data: {e}"


app_insert.annotations = ToolAnnotations(title="Insert App Row")


@tool
def app_update(
    app: str, table: str, id: int, data: dict[str, Any], user_id: str = "default"
) -> str:
    """Update a row by ID.

    Args:
        app: App name
        table: Table name
        id: Row ID to update
        data: Dict of column: value pairs to update
        user_id: User identifier

    Returns:
        Success or error message
    """
    try:
        storage = _get_storage(user_id)
        if storage.update(app, table, id, data):
            return f"Updated row {id} in '{app}.{table}'."
        return f"Row {id} not found in '{app}.{table}'."
    except Exception as e:
        logger.error(
            "app_update.error",
            {"app": app, "table": table, "id": id, "error": str(e)},
            user_id=user_id,
        )
        return f"Error updating data: {e}"


app_update.annotations = ToolAnnotations(title="Update App Row")


@tool
def app_delete_row(app: str, table: str, id: int, user_id: str = "default") -> str:
    """Delete a row by ID.

    Args:
        app: App name
        table: Table name
        id: Row ID to delete
        user_id: User identifier

    Returns:
        Success or error message
    """
    try:
        storage = _get_storage(user_id)
        if storage.delete(app, table, id):
            return f"Deleted row {id} from '{app}.{table}'."
        return f"Row {id} not found in '{app}.{table}'."
    except Exception as e:
        logger.error(
            "app_delete_row.error",
            {"app": app, "table": table, "id": id, "error": str(e)},
            user_id=user_id,
        )
        return f"Error deleting data: {e}"


app_delete_row.annotations = ToolAnnotations(title="Delete App Row", destructive=True)


@tool
def app_column_add(
    app: str,
    table: str,
    column: str,
    col_type: str,
    enable_search: bool = True,
    user_id: str = "default",
) -> str:
    """Add a column to a table.

    Args:
        app: App name
        table: Table name
        column: Column name
        col_type: Column type (TEXT, INTEGER, REAL, BOOLEAN)
        enable_search: If True and col_type is TEXT, enable FTS5 + vec (default True)
        user_id: User identifier

    Returns:
        Success or error message
    """
    try:
        storage = _get_storage(user_id)
        if storage.column_add(app, table, column, col_type, enable_search):
            search_info = (
                " with FTS5 search" if enable_search and col_type.upper() == "TEXT" else ""
            )
            return f"Added column '{column}' ({col_type}) to '{app}.{table}'{search_info}."
        return f"Failed to add column to '{app}.{table}'."
    except Exception as e:
        logger.error(
            "app_column_add.error",
            {"app": app, "table": table, "column": column, "error": str(e)},
            user_id=user_id,
        )
        return f"Error adding column: {e}"


app_column_add.annotations = ToolAnnotations(title="Add App Column")


@tool
def app_column_delete(app: str, table: str, column: str, user_id: str = "default") -> str:
    """Delete a column from a table.

    Args:
        app: App name
        table: Table name
        column: Column name to delete
        user_id: User identifier

    Returns:
        Success or error message
    """
    try:
        storage = _get_storage(user_id)
        if storage.column_delete(app, table, column):
            return f"Deleted column '{column}' from '{app}.{table}'."
        return f"Column '{column}' not found in '{app}.{table}'."
    except Exception as e:
        logger.error(
            "app_column_delete.error",
            {"app": app, "table": table, "column": column, "error": str(e)},
            user_id=user_id,
        )
        return f"Error deleting column: {e}"


app_column_delete.annotations = ToolAnnotations(title="Delete App Column", destructive=True)


@tool
def app_column_rename(
    app: str, table: str, old_name: str, new_name: str, user_id: str = "default"
) -> str:
    """Rename a column in a table.

    Args:
        app: App name
        table: Table name
        old_name: Current column name
        new_name: New column name
        user_id: User identifier

    Returns:
        Success or error message
    """
    try:
        storage = _get_storage(user_id)
        if storage.column_rename(app, table, old_name, new_name):
            return f"Renamed column '{old_name}' to '{new_name}' in '{app}.{table}'."
        return f"Failed to rename column '{old_name}' in '{app}.{table}'."
    except Exception as e:
        logger.error(
            "app_column_rename.error",
            {
                "app": app,
                "table": table,
                "old_name": old_name,
                "new_name": new_name,
                "error": str(e),
            },
            user_id=user_id,
        )
        return f"Error renaming column: {e}"


app_column_rename.annotations = ToolAnnotations(title="Rename App Column")


def _convert_date_in_query(query: str) -> str:
    now = datetime.now()
    query = re.sub(
        r"last month",
        str(int(datetime(now.year, now.month - 1 if now.month > 1 else 12, 1).timestamp() * 1000)),
        query,
        flags=re.IGNORECASE,
    )
    query = re.sub(
        r"this month",
        str(int(datetime(now.year, now.month, 1).timestamp() * 1000)),
        query,
        flags=re.IGNORECASE,
    )
    query = re.sub(
        r"today",
        str(int(datetime(now.year, now.month, now.day).timestamp() * 1000)),
        query,
        flags=re.IGNORECASE,
    )

    date_pattern = re.compile(r"(\d{4}-\d{2}-\d{2})")
    for match in date_pattern.finditer(query):
        date_str = match.group(1)
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            ts = int(dt.timestamp() * 1000)
            query = query.replace(date_str, str(ts))
        except ValueError:
            pass

    return query


@tool
def app_query(app: str, query: str, user_id: str = "default") -> str:
    """Query app data with SQL.

    Args:
        app: App name
        query: SQL query (SELECT, INSERT, UPDATE, DELETE)
        user_id: User identifier

    Returns:
        Query results
    """
    try:
        storage = _get_storage(user_id)
        schema = storage.get_schema(app)

        if not schema:
            return f"App '{app}' not found."

        query = _convert_date_in_query(query)

        results = storage.query_sql(app, query)

        if not results:
            return "No results found."

        formatted = []
        for row in results[:20]:
            formatted.append(str(row))

        return "\n".join(formatted) + (
            f"\n\n... and {len(results) - 20} more" if len(results) > 20 else ""
        )

    except Exception as e:
        logger.error(
            "app_query.error", {"app": app, "query": query, "error": str(e)}, user_id=user_id
        )
        return f"Error querying app: {e}"


app_query.annotations = ToolAnnotations(title="Query App Data", open_world=True)


@tool
def app_search_fts(
    app: str, table: str, column: str, query: str, limit: int = 10, user_id: str = "default"
) -> str:
    """Search app data using keyword search (FTS5).

    Only works on TEXT columns that have been indexed for search.
    Columns like 'description', 'notes', 'content', 'title' are typically indexed.
    Avoid using on columns with choices/options (e.g., 'status', 'category', 'type').

    Args:
        app: App name
        table: Table name
        column: Column name to search (must be TEXT type, not options)
        query: Search query (keywords)
        limit: Max results (default 10)
        user_id: User identifier

    Returns:
        Matching rows with scores
    """
    try:
        storage = _get_storage(user_id)
        schema = storage.get_schema(app)

        if not schema:
            return f"App '{app}' not found."

        if table not in schema.tables:
            return f"Table '{table}' not found in app '{app}'."

        table_schema = schema.tables[table]
        if column not in table_schema.columns:
            return f"Column '{column}' not found in table '{table}'. Available: {list(table_schema.columns.keys())}"

        col_type = table_schema.columns.get(column, "").upper()
        if "TEXT" not in col_type:
            return f"Column '{column}' is '{col_type}', not TEXT. FTS5 only works on TEXT columns."

        results = storage.search_fts(app, table, column, query, limit=limit)

        if not results:
            return f"No results found for '{query}' in {table}.{column}"

        formatted = [f"Found {len(results)} results:"]
        for row in results[:20]:
            formatted.append(str(row))

        return "\n".join(formatted)

    except Exception as e:
        logger.error(
            "app_search_fts.error",
            {"app": app, "table": table, "column": column, "query": query, "error": str(e)},
            user_id=user_id,
        )
        return f"Error searching: {e}"


app_search_fts.annotations = ToolAnnotations(
    title="Search App (FTS5)", read_only=True, open_world=True
)


@tool
def app_search_semantic(
    app: str, table: str, column: str, query: str, limit: int = 10, user_id: str = "default"
) -> str:
    """Search app data using semantic/vector search (AI-powered).

    Only works on TEXT columns that have been indexed for vector search.
    Best for natural language queries on columns like 'description', 'notes', 'content'.
    Avoid using on columns with choices/options (e.g., 'status', 'category', 'type').

    Args:
        app: App name
        table: Table name
        column: Column name to search (must be TEXT type, not options)
        query: Natural language search query
        limit: Max results (default 10)
        user_id: User identifier

    Returns:
        Matching rows ranked by semantic similarity
    """
    try:
        storage = _get_storage(user_id)
        schema = storage.get_schema(app)

        if not schema:
            return f"App '{app}' not found."

        if table not in schema.tables:
            return f"Table '{table}' not found in app '{app}'."

        table_schema = schema.tables[table]
        if column not in table_schema.columns:
            return f"Column '{column}' not found in table '{table}'. Available: {list(table_schema.columns.keys())}"

        col_type = table_schema.columns.get(column, "").upper()
        if "TEXT" not in col_type:
            return f"Column '{column}' is '{col_type}', not TEXT. Semantic search only works on TEXT columns."

        results = storage.search_semantic(app, table, column, query, limit=limit)

        if not results:
            return f"No semantic results found for '{query}' in {table}.{column}"

        formatted = [f"Found {len(results)} semantic results:"]
        for row in results[:20]:
            formatted.append(str(row))

        return "\n".join(formatted)

    except Exception as e:
        logger.error(
            "app_search_semantic.error",
            {"app": app, "table": table, "column": column, "query": query, "error": str(e)},
            user_id=user_id,
        )
        return f"Error searching: {e}"


app_search_semantic.annotations = ToolAnnotations(
    title="Search App (Semantic)", read_only=True, open_world=True
)


@tool
def app_search_hybrid(
    app: str,
    table: str,
    column: str,
    query: str,
    limit: int = 10,
    fts_weight: float = 0.5,
    user_id: str = "default",
) -> str:
    """Search app data using hybrid search (keyword + semantic combined).

    Combines keyword search (FTS5) with semantic/vector search for best results.
    Only works on TEXT columns that have been indexed for search.
    Best for natural language queries on columns like 'description', 'notes', 'content'.
    Avoid using on columns with choices/options (e.g., 'status', 'category', 'type').

    Args:
        app: App name
        table: Table name
        column: Column name to search (must be TEXT type, not options)
        query: Natural language search query
        limit: Max results (default 10)
        fts_weight: Weight for keyword search (0-1), semantic gets (1-fts_weight). Default 0.5
        user_id: User identifier

    Returns:
        Matching rows ranked by combined keyword + semantic similarity
    """
    try:
        storage = _get_storage(user_id)
        schema = storage.get_schema(app)

        if not schema:
            return f"App '{app}' not found."

        if table not in schema.tables:
            return f"Table '{table}' not found in app '{app}'."

        table_schema = schema.tables[table]
        if column not in table_schema.columns:
            return f"Column '{column}' not found in table '{table}'. Available: {list(table_schema.columns.keys())}"

        col_type = table_schema.columns.get(column, "").upper()
        if "TEXT" not in col_type:
            return f"Column '{column}' is '{col_type}', not TEXT. Hybrid search only works on TEXT columns."

        results = storage.search_hybrid(
            app, table, column, query, limit=limit, fts_weight=fts_weight
        )

        if not results:
            return f"No results found for '{query}' in {table}.{column}"

        formatted = [f"Found {len(results)} hybrid results:"]
        for row in results[:20]:
            formatted.append(str(row))

        return "\n".join(formatted)

    except Exception as e:
        logger.error(
            "app_search_hybrid.error",
            {"app": app, "table": table, "column": column, "query": query, "error": str(e)},
            user_id=user_id,
        )
        return f"Error searching: {e}"


app_search_hybrid.annotations = ToolAnnotations(
    title="Search App (Hybrid)", read_only=True, open_world=True
)
