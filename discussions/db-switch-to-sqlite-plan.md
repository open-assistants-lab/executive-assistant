# Switch DB from DuckDB to SQLite

## Goal

Replace DuckDB with SQLite for the per-workspace `db` component, while keeping DuckDB for KB (vector search).

---

## Current State

```python
# src/cassey/storage/seekdb_storage.py (being phased out)

# Current DuckDB usage per workspace:
# data/workspaces/{workspace_id}/db/db.duckdb
```

**Why SQLite instead?**

| Aspect | DuckDB | SQLite |
|--------|--------|--------|
| Optimized for | Analytics (OLAP) | Transactions (OLTP) |
| Write pattern | Batch/bulk | Individual row inserts |
| Concurrency | Limited | WAL mode, excellent |
| Use case fit | Data science | App-like data (CRM, timesheet) |

**DB use cases are OLTP:**
- Timesheets (insert time entries, update status)
- Mini CRM (CRUD on contacts, deals)
- Task lists (create, read, update, delete tasks)
- Inventories, ledgers, etc.

---

## Peer Review Findings & Fixes

### Issue 1: Missing Methods in SQLiteDatabase

**Problem:** The original `SQLiteDatabase` class was missing several methods that `db_tools.py` currently uses:
- `create_table_from_data()` - Used to create tables from JSON data
- `get_table_info()` - Used to get column info with nullable/pk flags
- `append_to_table()` - Used to insert rows into existing tables
- `export_table()` - Used to export tables to CSV
- `drop_table()` - Used to drop tables

**Fix:** Added all missing methods to `SQLiteDatabase` class (see updated implementation below).

### Issue 2: CSV Import/Export Gap

**Problem:** DuckDB has `read_csv_auto()` for import and built-in export. SQLite has neither.

**Fix:**
- Import: Use Python's `csv` module to parse and insert rows
- Export: Use Python's `csv` module to write query results to file

### Issue 3: Storage Path Consistency

**Problem:** Need to ensure the path system matches the workspace-first architecture.

**Fix:** Use `settings.get_workspace_db_path()` which respects the workspace storage layout.

### Issue 4: Method Return Format Mismatch

**Problem:** `db_tools.py` expects `get_table_info()` to return a list of dicts with `name`, `type`, `notnull`, `pk` keys. Original plan had `get_schema()` returning `{column: type}`.

**Fix:** Renamed to `get_table_info()` with correct return format matching current usage.

---

## Implementation Status

### Completed

| File | Status | Notes |
|------|--------|-------|
| `src/cassey/storage/sqlite_db_storage.py` | ✅ Created | ~355 lines, includes SQLiteDatabase class with all required methods |
| `src/cassey/skills/sqlite_helper.py` | ✅ Created | ~105 lines, sqlite_guide tool with topics: arrays, dates, json, examples |
| `src/cassey/skills/__init__.py` | ✅ Created | Exports `get_sqlite_helper_tools` |
| `src/cassey/storage/db_tools.py` | ✅ Modified | Switched from DuckDB to SQLite, updated all tool descriptions |
| `src/cassey/tools/registry.py` | ✅ Modified | Added `get_sqlite_helper_tools()` function and import |
| `tests/test_sqlite_db_storage.py` | ✅ Created | ~495 lines, comprehensive test suite |

### Test Results

All 23 tests passing:

```
tests/test_sqlite_db_storage.py::TestSQLiteDatabase::test_create_and_query_table PASSED
tests/test_sqlite_db_storage.py::TestSQLiteDatabase::test_create_table_from_list_data PASSED
tests/test_sqlite_db_storage.py::TestSQLiteDatabase::test_table_exists PASSED
tests/test_sqlite_db_storage.py::TestSQLiteDatabase::test_list_tables PASSED
tests/test_sqlite_db_storage.py::TestSQLiteDatabase::test_get_table_info PASSED
tests/test_sqlite_db_storage.py::TestSQLiteDatabase::test_drop_table PASSED
tests/test_sqlite_db_storage.py::TestSQLiteDatabase::test_append_to_table PASSED
tests/test_sqlite_db_storage.py::TestSQLiteDatabase::test_export_table PASSED
tests/test_sqlite_db_storage.py::TestSQLiteDatabase::test_import_csv PASSED
tests/test_sqlite_db_storage.py::TestSQLiteDatabase::test_context_manager PASSED
tests/test_sqlite_db_storage.py::TestSQLiteDatabase::test_executemany PASSED
tests/test_sqlite_db_storage.py::TestConnectionCaching::test_connection_caching PASSED
tests/test_sqlite_db_storage.py::TestConnectionCaching::test_reset_cache PASSED
tests/test_sqlite_db_storage.py::TestSQLiteJSON::test_json_array_create_and_query PASSED
tests/test_sqlite_db_storage.py::TestSQLiteJSON::test_json_extract PASSED
tests/test_sqlite_db_storage.py::TestSQLiteDates::test_date_functions PASSED
tests/test_sqlite_db_storage.py::TestTypeInference::test_infer_int_type PASSED
tests/test_sqlite_db_storage.py::TestTypeInference::test_infer_real_type PASSED
tests/test_sqlite_db_storage.py::TestTypeInference::test_infer_text_type PASSED
tests/test_sqlite_db_storage.py::TestValidation::test_invalid_identifier PASSED
tests/test_sqlite_db_storage.py::TestValidation::test_empty_data_error PASSED
tests/test_sqlite_db_storage.py::TestValidation::test_columns_required_for_list_data PASSED
tests/test_sqlite_db_storage.py::TestValidation::test_unsupported_export_format PASSED

======================== 23 passed, 1 warning in 2.34s ========================
```

### Key Implementation Details

1. **Connection Caching**: `@lru_cache` on `_get_sqlite_connection()` ensures one connection per workspace
2. **WAL Mode**: Enabled for better concurrency (`PRAGMA journal_mode=WAL`)
3. **Type Inference**: `create_table_from_data()` automatically detects INTEGER/REAL/TEXT from data
4. **CSV Import/Export**: Handled via Python's `csv` module since SQLite lacks built-in CSV support
5. **Context Manager**: `SQLiteDatabase` supports `with` statement for transaction management

### Remaining Work

| Task | Priority | Status |
|------|----------|--------|
| Tool condensation (17→6 tools) | High | ⏳ Planned, pending group refactoring |
| Multiple database files per directory | Medium | ⏳ Planned |
| Remove old `seekdb_storage.py` | Low | ⏳ Pending |
| Integration tests with actual agent workflows | Medium | ⏳ Pending |

---

## Tool Condensation Plan (17 → 6 tools)

**Current state:** 17 separate tools (8 DB + 9 shared DB + helpers)

**Problem:** Too many tools, many are just SQL queries in disguise.

### Proposed Tool Set

| Tool | Parameters | Description |
|------|------------|-------------|
| `query_db` | `sql`, `database="default"`, `scope="workspace"` | Universal SQL executor |
| `create_db_table` | `table_name`, `data`, `database="default"`, `scope="workspace"` | JSON → table with type inference |
| `drop_db_table` | `table_name`, `database="default"`, `scope="workspace"` | Drop table |
| `export_db_table` | `table_name`, `filename`, `database="default"`, `scope="workspace"` | CSV export |
| `import_db_table` | `table_name`, `filename`, `database="default"`, `scope="workspace"` | CSV import |
| `list_databases` | `scope="workspace"` | List available .sqlite files |

### Scope Values

| Scope | Path | Who can write |
|-------|------|---------------|
| `"user"` | `data/users/{user_id}/db/` | User only |
| `"workspace"` → `"group"` | `data/workspaces/{id}/db/` → `data/groups/{id}/db/` | Group members |
| `"shared"` | `data/shared/db/` | Admin only |

### Removed Tools (handled by `query_db`)

| Removed Tool | Replacement |
|--------------|-------------|
| `list_db_tables` | `query_db("SELECT name FROM sqlite_master WHERE type='table'")` |
| `describe_db_table` | `query_db("PRAGMA table_info('table_name')")` |
| `insert_db_table` | `query_db("INSERT INTO ... VALUES ...")` |
| `list_shared_db_tables` | `query_db("SELECT name FROM sqlite_master ...", scope="shared")` |
| `describe_shared_db_table` | `query_db("PRAGMA table_info(...) ...", scope="shared")` |
| `create_shared_db_table` | `create_db_table(..., scope="shared")` |
| `insert_shared_db_table` | `query_db("INSERT ...", scope="shared")` |
| `drop_shared_db_table` | `drop_db_table(..., scope="shared")` |
| `import_shared_db_table` | `import_db_table(..., scope="shared")` |
| `execute_shared_db` | `query_db(sql, scope="shared")` |

**Note:** This condensation is planned but not yet implemented. It will be done after the "workspace → group" refactoring to avoid double work.

---

## Proposed Architecture

```
Cassey Storage per workspace:
├── DB/                     → SQLite (this change)
│   └── db.sqlite
├── KB/                     → DuckDB (unchanged, needs VSS)
│   └── kb.db
├── mem/                    → DuckDB FTS (unchanged, or could migrate to SQLite FTS5)
│   └── mem.db
└── files/                  → File storage (unchanged)
```

---

## Files to Modify

### 1. Create `src/cassey/storage/sqlite_db_storage.py`

```python
"""SQLite storage for workspace DB.

Provides per-workspace SQLite databases for general data management
(timesheets, CRM, tasks, etc.).
"""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path
from functools import lru_cache
from typing import Any
from dataclasses import dataclass

from cassey.storage.workspace_storage import (
    get_workspace_id,
    sanitize_thread_id,
    validate_identifier,
)


@dataclass
class SQLiteDatabase:
    """A workspace SQLite database."""

    workspace_id: str
    conn: sqlite3.Connection
    path: Path

    def execute(self, sql: str, params: list | tuple | None = None) -> sqlite3.Cursor:
        """Execute SQL and return cursor."""
        if params is None:
            params = []
        return self.conn.execute(sql, params)

    def executemany(self, sql: str, params: list) -> sqlite3.Cursor:
        """Execute SQL with many parameter sets."""
        return self.conn.executemany(sql, params)

    def commit(self) -> None:
        """Commit transaction."""
        self.conn.commit()

    def rollback(self) -> None:
        """Rollback transaction."""
        self.conn.rollback()

    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists."""
        cursor = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            [table_name]
        )
        return cursor.fetchone() is not None

    def list_tables(self) -> list[str]:
        """List all tables."""
        cursor = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        return [row[0] for row in cursor.fetchall()]

    def get_table_info(self, table_name: str) -> list[dict]:
        """Get table schema info (name, type, notnull, pk).

        Returns:
            List of dicts with keys: name, type, notnull, pk
        """
        cursor = self.conn.execute(f"PRAGMA table_info('{table_name}')")
        return [
            {
                "name": row[1],
                "type": row[2],
                "notnull": row[3] == 1,
                "pk": row[5],
            }
            for row in cursor.fetchall()
        ]

    def drop_table(self, table_name: str) -> None:
        """Drop a table if it exists."""
        self.conn.execute(f"DROP TABLE IF EXISTS {table_name}")
        self.commit()

    def create_table_from_data(
        self,
        table_name: str,
        data: list[dict] | list[list]],
        columns: list[str] | None = None,
    ) -> None:
        """Create a table and populate it from data.

        Args:
            table_name: Name for the new table.
            data: List of dicts (column names from keys) or list of lists.
            columns: Column names (required if data is list of lists).
        """
        validate_identifier(table_name)

        # Infer columns and types from data
        if isinstance(data, list) and len(data) > 0:
            if isinstance(data[0], dict):
                # Infer from dict keys
                inferred_columns = list(data[0].keys())
                column_defs = []
                for col in inferred_columns:
                    # Simple type inference
                    is_int = all(isinstance(row.get(col), int) for row in data if col in row)
                    is_float = all(isinstance(row.get(col), float) for row in data if col in row)
                    if is_int:
                        col_type = "INTEGER"
                    elif is_float:
                        col_type = "REAL"
                    else:
                        col_type = "TEXT"
                    column_defs.append(f"{col} {col_type}")
                columns_sql = ", ".join(column_defs)
            else:
                # Use provided columns for list of lists
                if not columns:
                    raise ValueError("columns required when data is list of lists")
                # Default to TEXT for all columns when data is list of lists
                columns_sql = ", ".join(f"{col} TEXT" for col in columns)
        else:
            raise ValueError("Cannot infer schema from empty data")

        # Create table
        self.conn.execute(f"CREATE TABLE {table_name} ({columns_sql})")

        # Insert data
        if data:
            if isinstance(data[0], dict):
                # Insert from list of dicts
                for row in data:
                    cols = ", ".join(row.keys())
                    placeholders = ", ".join(["?"] * len(row))
                    values = list(row.values())
                    self.conn.execute(f"INSERT INTO {table_name} ({cols}) VALUES ({placeholders})", values)
            else:
                # Insert from list of lists
                self.conn.executemany(
                    f"INSERT INTO {table_name} VALUES ({', '.join(['?'] * len(columns))})",
                    data
                )

        self.commit()

    def append_to_table(self, table_name: str, data: list[dict]) -> None:
        """Append data to an existing table.

        Args:
            table_name: Name of the table.
            data: List of dicts with column names as keys.
        """
        if not data:
            return

        # Get column names from first row
        first_row = data[0]
        cols = ", ".join(first_row.keys())
        placeholders = ", ".join(["?"] * len(first_row))

        # Insert all rows
        for row in data:
            values = list(row.values())
            self.conn.execute(f"INSERT INTO {table_name} ({cols}) VALUES ({placeholders})", values)

        self.commit()

    def export_table(self, table_name: str, output_path: Path, format: str = "csv") -> None:
        """Export table to a file.

        Args:
            table_name: Name of the table.
            output_path: Path to output file.
            format: Export format (only "csv" supported for now).
        """
        if format.lower() != "csv":
            raise ValueError(f"Unsupported export format: {format}. Only 'csv' is supported.")

        # Query all data
        cursor = self.conn.execute(f"SELECT * FROM {table_name}")

        # Write CSV
        with open(output_path, "w", newline="") as f:
            writer = csv.writer(f)
            # Write header
            if cursor.description:
                writer.writerow([desc[0] for desc in cursor.description])
            # Write rows
            writer.writerows(cursor.fetchall())

    def import_csv(self, table_name: str, csv_path: Path) -> int:
        """Import a CSV file into a new table.

        Args:
            table_name: Name for the new table.
            csv_path: Path to the CSV file.

        Returns:
            Number of rows imported.
        """
        validate_identifier(table_name)

        with open(csv_path, "r", newline="") as f:
            reader = csv.reader(f)
            headers = next(reader)  # First row is headers

            # Infer types from first data row
            first_data = next(reader, None)
            if first_data:
                column_defs = []
                for i, (header, value) in enumerate(zip(headers, first_data)):
                    try:
                        int(value)
                        col_type = "INTEGER"
                    except ValueError:
                        try:
                            float(value)
                            col_type = "REAL"
                        except ValueError:
                            col_type = "TEXT"
                    column_defs.append(f"{header} {col_type}")

                # Create table
                columns_sql = ", ".join(column_defs)
                self.conn.execute(f"CREATE TABLE {table_name} ({columns_sql})")

                # Insert first row
                placeholders = ", ".join(["?"] * len(headers))
                self.conn.execute(f"INSERT INTO {table_name} VALUES ({placeholders})", first_data)

                # Insert remaining rows
                row_count = 1
                for row in reader:
                    self.conn.execute(f"INSERT INTO {table_name} VALUES ({placeholders})", row)
                    row_count += 1

                self.commit()
                return row_count
            else:
                raise ValueError("CSV file is empty (no headers found)")

    def close(self) -> None:
        """Close the database connection.

        Note: Connections are cached, so this should typically
        only be called during shutdown or testing.
        """
        self.conn.close()

    def __enter__(self):
        """Context manager entry for transactions."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - commit or rollback."""
        if exc_type is None:
            self.conn.commit()
        else:
            self.conn.rollback()
        return False


def get_db_storage_dir(storage_id: str | None = None) -> Path:
    """
    Return the DB directory for a workspace.

    Storage layout: data/workspaces/{workspace_id}/db/

    Args:
        storage_id: Workspace identifier (optional, uses context if None).

    Returns:
        Path to the DB directory.
    """
    from cassey.config import settings

    if storage_id is None:
        storage_id = get_workspace_id()

    if not storage_id:
        raise ValueError("No storage_id provided and none in context")

    db_path = settings.get_workspace_db_path(storage_id)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path.parent


@lru_cache(maxsize=128)
def _get_sqlite_connection(storage_id: str, path: Path) -> sqlite3.Connection:
    """Get a cached SQLite connection for a workspace.

    Args:
        storage_id: Workspace identifier.
        path: Path to the DB directory.

    Returns:
        SQLite connection object.
    """
    db_path = path / "db.sqlite"
    conn = sqlite3.connect(str(db_path))

    # Enable WAL mode for better concurrency
    conn.execute("PRAGMA journal_mode=WAL")
    # Foreign keys
    conn.execute("PRAGMA foreign_keys=ON")
    # Performance tuning
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-64000")  # 64MB cache

    return conn


def get_sqlite_db(storage_id: str | None = None) -> SQLiteDatabase:
    """
    Get a SQLite database for a workspace.

    Args:
        storage_id: Workspace identifier (optional, uses context if None).

    Returns:
        SQLiteDatabase instance.
    """
    if storage_id is None:
        storage_id = get_workspace_id()

    path = get_db_storage_dir(storage_id)
    conn = _get_sqlite_connection(storage_id, path)

    return SQLiteDatabase(
        workspace_id=storage_id,
        conn=conn,
        path=path / "db.sqlite"
    )


def reset_connection_cache():
    """Reset the connection cache (for testing)."""
    _get_sqlite_connection.cache_clear()


# ============================================================================
# Backward Compatibility Functions
# ============================================================================

def get_db_connection(storage_id: str | None = None) -> sqlite3.Connection:
    """
    Get raw SQLite connection (for backward compatibility).

    Deprecated: Use get_sqlite_db() instead.
    """
    db = get_sqlite_db(storage_id)
    return db.conn
```

### 2. Tackling SQL Dialect Differences (Prompt + Skill)

**Approach**: Guide the AI to use SQLite-compatible syntax through prompts and a helper skill.

#### 2a. Update Tool Descriptions (Prompt)

```python
# src/cassey/tools/db_tools.py

@tool
def query_db(sql: str) -> str:
    """Execute SQL query on the workspace SQLite database.

    ⚠️ IMPORTANT: This database uses SQLite (not DuckDB). Use SQLite-compatible syntax:

    ✅ SUPPORTED:
    - Standard SQL: SELECT, INSERT, UPDATE, DELETE, CREATE TABLE, DROP TABLE
    - JSON for arrays: json_array(), json_extract(), json_each()
    - String operations: || for concatenation, LIKE, SUBSTR, REPLACE
    - Dates: date('now'), datetime('now'), strftime('%Y-%m-%d', col)
    - Auto-increment: INTEGER PRIMARY KEY (auto-increments automatically)

    ❌ NOT SUPPORTED (DuckDB-specific):
    - Array literals [1,2,3] → Use json_array(1,2,3)
    - LIST/ARRAY types → Use JSON stored as TEXT
    - DuckDB-specific functions → Use SQLite equivalents

    Examples:
    - CREATE TABLE timesheets (id INTEGER PRIMARY KEY, date TEXT, hours REAL, project TEXT, tags TEXT)  -- tags as JSON
    - INSERT INTO timesheets (date, hours, project, tags) VALUES ('2025-01-17', 4.5, 'Cassey', json_array('billing', 'admin'))
    - SELECT * FROM timesheets WHERE json_each(tags) = 'billing'
    - SELECT * FROM timesheets WHERE date >= date('now', '-7 days')

    Args:
        sql: SQL query to execute.

    Returns:
        Query results as formatted string.
    """
```

#### 2b. Create SQLite Helper Skill

```python
# src/cassey/skills/sqlite_helper.py

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
```

### 3. Update `src/cassey/tools/db_tools.py`

Replace DuckDB imports with SQLite (with updated descriptions):

```python
# Before:
from cassey.storage.seekdb_storage import get_seekdb_connection

# After:
from cassey.storage.sqlite_db_storage import get_sqlite_db


@tool
def query_db(sql: str) -> str:
    """Execute SQL query on the workspace SQLite database.

    ⚠️ IMPORTANT: This database uses SQLite (not DuckDB). Use SQLite-compatible syntax.

    Supported: SELECT, INSERT, UPDATE, DELETE, CREATE TABLE, DROP TABLE
    - Arrays: Use json_array(), json_each(), json_extract()
    - Dates: date('now'), datetime('now'), strftime()
    - Auto-increment: INTEGER PRIMARY KEY (automatic)

    Examples:
    - CREATE TABLE timesheets (id INTEGER PRIMARY KEY, date TEXT, hours REAL, project)
    - INSERT INTO timesheets (date, hours, project) VALUES ('2025-01-17', 4.5, 'Cassey')
    - SELECT * FROM timesheets WHERE date >= date('now', '-7 days')

    Args:
        sql: SQL query to execute.

    Returns:
        Query results as formatted string.
    """
    try:
        db = get_sqlite_db()
        cursor = db.execute(sql)

        # Handle different query types
        sql_upper = sql.strip().upper()

        if sql_upper.startswith(("SELECT", "PRAGMA", "EXPLAIN")):
            # Return results
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            return format_query_results(columns, rows)
        else:
            # Write operation
            db.conn.commit()
            rows_affected = cursor.rowcount
            return f"Query executed successfully. Rows affected: {rows_affected}"

    except Exception as e:
        return f"Error executing SQL: {str(e)}"


@tool
def list_tables() -> str:
    """List all tables in the workspace DB."""
    db = get_sqlite_db()
    tables = db.list_tables()

    if not tables:
        return "No tables found in the database."

    return "Tables in the database:\n" + "\n".join(f"- {t}" for t in tables)


@tool
def describe_table(table_name: str) -> str:
    """Get the schema (columns and types) of a table.

    Args:
        table_name: Name of the table to describe.

    Returns:
        Table schema as formatted string.
    """
    try:
        from cassey.storage.workspace_storage import validate_identifier

        validate_identifier(table_name)
        db = get_sqlite_db()

        if not db.table_exists(table_name):
            return f"Table '{table_name}' does not exist."

        columns = db.get_table_info(table_name)

        if not columns:
            return f"Table '{table_name}' has no columns."

        result = f"Table '{table_name}' schema:\n"
        for col in columns:
            nullable = "NULL" if not col["notnull"] else "NOT NULL"
            pk = " PRIMARY KEY" if col["pk"] > 0 else ""
            result += f"  - {col['name']}: {col['type']} {nullable}{pk}\n"

        return result

    except Exception as e:
        return f"Error describing table: {str(e)}"


def format_query_results(columns: list[str], rows: list[tuple]) -> str:
    """Format query results as readable string."""
    if not rows:
        return "No results."

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
```

### 4. Update `src/cassey/skills/registry.py`

Register the SQLite helper skill:

```python
# Add to the skills registry
from cassey.skills.sqlite_helper import get_sqlite_helper_tools

async def get_all_skills() -> list:
    skills = await get_existing_skills()
    skills.extend(await get_sqlite_helper_tools())
    return skills
```

### 5. Update Tests

Replace `seekdb_storage` tests with `sqlite_db_storage` tests:

| Test File | Changes |
|-----------|---------|
| `tests/test_sqlite_db_storage.py` | New file for SQLite-specific tests |
| `tests/integration/test_db_tools.py` | Update imports, verify SQLite behavior |
| `tests/test_sqlite_guide.py` | New file for sqlite_guide skill tests |

**Key SQLite differences to test:**
- Array storage via JSON (not native arrays)
- Date functions: `date('now')`, `strftime()`
- Auto-increment: `INTEGER PRIMARY KEY`
- Case-insensitive LIKE

### 6. Documentation Updates

| File | Changes |
|------|---------|
| `README.md` | Update DB section to mention SQLite |
| `docs/architecture.md` | Update storage architecture diagram |
| `.env.example` | No changes (DB path uses existing setting) |

---

## Migration: Not Needed

**No migration is required** — Cassey has not launched yet. This is a greenfield change:

- Development workspaces can be deleted and recreated with SQLite
- No production data exists to migrate
- The old `seekdb_storage.py` can be removed entirely once `sqlite_db_storage.py` is deployed

**Action**: Simply delete `src/cassey/storage/seekdb_storage.py` after deployment.

---

## Breaking Changes

| Change | Impact | Mitigation |
|--------|--------|------------|
| DuckDB → SQLite | SQL syntax differences for DB queries | Update tool descriptions, provide sqlite_guide skill |
| No native array type | Data structures relying on arrays break | Use JSON or separate tables |

**Note**: These breaking changes only affect the DB component. KB (vector search) remains on DuckDB.

---

## Timeline

| Phase | Tasks |
|-------|-------|
| **1. Foundation** | Create `sqlite_db_storage.py` with connection caching, WAL mode, context manager support |
| **2. SQL Dialect** | Update tool descriptions with SQLite syntax warnings, create `sqlite_guide` skill |
| **3. Tools** | Update `db_tools.py` to use SQLite with enhanced prompts |
| **4. Registry** | Register `sqlite_guide` skill in skills registry |
| **5. Testing** | Create SQLite tests, verify JSON arrays, date functions, transactions |
| **6. Cleanup** | Remove `seekdb_storage.py`, update documentation |

---

## Summary

| Component | Current | Target |
|-----------|---------|--------|
| **DB** | DuckDB | SQLite ✅ |
| **KB** | DuckDB | DuckDB (unchanged, needs VSS) |
| **mem** | DuckDB FTS | DuckDB FTS (or migrate to SQLite FTS5) |

**Primary benefit:** Better fit for transactional workloads (timesheets, CRM, tasks) while keeping DuckDB where it shines (vector search).

**SQL Dialect Approach:**
- **Prompt**: Enhanced tool descriptions guide AI toward SQLite syntax
- **Skill**: `sqlite_guide` provides on-demand help for arrays, dates, JSON, examples
- **No runtime conversion**: AI learns patterns through examples and guidance
