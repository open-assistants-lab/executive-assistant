"""SQLite helper skill for guiding AI to use SQLite-compatible syntax."""

from langchain_core.tools import tool


@tool
def sqlite_guide(topic: str = "") -> str:
    """Get SQLite syntax guide and common patterns.

    Use this when you need help writing SQLite-compatible queries or
    converting from other SQL dialects.

    Args:
        topic: Optional topic like 'arrays', 'dates', 'json', 'examples'

    Returns:
        SQLite syntax guide for the requested topic.
    """
    guides = {
        "arrays": """
SQLite Arrays via JSON:
- Storage: Store as TEXT with JSON: tags TEXT
- Insert: json_array('tag1', 'tag2', 'tag3')
- Query: WHERE tags LIKE '%\"tag1\"%'  (simple)
- Query: WHERE EXISTS (SELECT 1 FROM json_each(tags) WHERE value = 'tag1')  (proper)
- Extract: json_extract(tags, '$[0]')  -- first element
        """,

        "dates": """
SQLite Date/Time Functions:
- Current date: date('now')
- Current datetime: datetime('now')
- Add days: date('now', '+7 days')
- Subtract days: date('now', '-30 days')
- Format: strftime('%Y-%m-%d', date_column)
- Parse: date('2025-01-17')
- Compare: WHERE date_column >= date('now', '-7 days')
        """,

        "json": """
SQLite JSON Functions:
- Create array: json_array(1, 2, 3)
- Create object: json_object('key', 'value')
- Extract value: json_extract(json_col, '$.key')
- Table from JSON array: json_each(json_col) -> returns (key, value, type)
- Check contains: json_extract(tags, '$') LIKE '%\"tag1\"%'
        """,

        "examples": """
Common SQLite Patterns:

-- Timesheet table
CREATE TABLE timesheets (
    id INTEGER PRIMARY KEY,
    date TEXT NOT NULL,
    hours REAL,
    project TEXT,
    tags TEXT  -- JSON array
);

-- Insert with tags
INSERT INTO timesheets (date, hours, project, tags)
VALUES ('2025-01-17', 4.5, 'Cassey', json_array('billing', 'admin'));

-- Query by tag
SELECT * FROM timesheets
WHERE EXISTS (
    SELECT 1 FROM json_each(tags)
    WHERE value = 'billing'
);

-- Date range query
SELECT * FROM timesheets
WHERE date >= date('now', '-7 days')
ORDER BY date DESC;
        """,
    }

    if topic and topic in guides:
        return guides[topic].strip()

    # Return overview
    return """
SQLite Syntax Guide

Available topics: arrays, dates, json, examples

Quick Reference:
- Arrays: Use json_array(), json_each(), json_extract()
- Dates: date('now'), datetime('now'), strftime()
- Auto-increment: INTEGER PRIMARY KEY
- String concat: ||
- Case insensitive: LIKE is case-insensitive in SQLite

Use sqlite_guide(topic="arrays") for array patterns.
Use sqlite_guide(topic="dates") for date functions.
Use sqlite_guide(topic="json") for JSON functions.
Use sqlite_guide(topic="examples") for common patterns.
    """.strip()


async def get_sqlite_helper_tools() -> list:
    """Get SQLite helper tools."""
    return [sqlite_guide]
