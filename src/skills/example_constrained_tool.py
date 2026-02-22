"""Example constrained tool for testing."""

from typing import Any

from langchain_core.tools import tool


@tool
def write_sql_query(
    query: str,
    database: str,
    runtime: Any | None = None,
) -> str:
    """Write and validate a SQL query for a specific database.

    Args:
        query: The SQL query to validate
        database: Database name (e.g., "sql-analytics", "inventory")
    """
    # Check if required skill is loaded
    skills_loaded = []
    if runtime:
        skills_loaded = runtime.state.get("skills_loaded", [])

    if database not in skills_loaded:
        return (
            f"Error: You must load the '{database}' skill first. "
            f"Use load_skill('{database}') to load the database schema."
        )

    # Execute only if skill is loaded
    return f"SQL Query for {database}:\n\n```sql\n{query}\n```\n\n✓ Query validated against {database} schema"
