"""SQLite storage for group DB.

Provides per-group SQLite databases for general data management
(timesheets, CRM, tasks, etc.).
"""

from __future__ import annotations

import csv
import sqlite3
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from cassey.config import settings
from cassey.storage.db_storage import validate_identifier
from cassey.storage.group_storage import get_workspace_id


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
        validate_identifier(table_name)
        self.conn.execute(f"DROP TABLE IF EXISTS {table_name}")
        self.commit()

    def create_table(self, table_name: str, columns: list[str]) -> None:
        """Create an empty table with specified columns.

        Args:
            table_name: Name for the new table.
            columns: List of column definitions (e.g., ["id INTEGER PRIMARY KEY", "name TEXT"])
        """
        validate_identifier(table_name)
        cols_def = ", ".join(columns)
        self.conn.execute(f"CREATE TABLE IF NOT EXISTS {table_name} ({cols_def})")
        self.commit()

    def create_table_from_data(
        self,
        table_name: str,
        data: list[dict] | list[list],
        columns: list[str] | None = None,
    ) -> None:
        """Create a table and populate it from data.

        Args:
            table_name: Name for the new table.
            data: List of dicts (column names from keys) or list of lists.
            columns: Column names (required if data is list of lists).
        """
        validate_identifier(table_name)

        if not data:
            raise ValueError("Cannot create table from empty data")

        # Infer columns and types from data
        if isinstance(data[0], dict):
            # Infer from dict keys
            inferred_columns = list(data[0].keys())
            column_defs = []
            for col in inferred_columns:
                # Simple type inference
                is_int = all(isinstance(row.get(col), int) for row in data if col in row)
                is_float = all(isinstance(row.get(col), float) and not isinstance(row.get(col), int) for row in data if col in row)
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

        # Create table
        self.conn.execute(f"CREATE TABLE {table_name} ({columns_sql})")

        # Insert data
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
        validate_identifier(table_name)

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
                for header, value in zip(headers, first_data):
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
    Return the DB directory for a group.

    Storage layout: data/groups/{group_id}/db/

    Args:
        storage_id: Group identifier (optional, uses context if None).

    Returns:
        Path to the DB directory.
    """
    if storage_id is None:
        # Priority: user_id (individual) > group_id (team) > thread_id (fallback)
        from cassey.storage.group_storage import get_user_id
        from cassey.storage.file_sandbox import get_thread_id

        storage_id = get_user_id()
        if storage_id is None:
            storage_id = get_workspace_id()
        if storage_id is None:
            storage_id = get_thread_id()

    if not storage_id:
        raise ValueError("No storage_id provided and none in context")

    # Use user path if not a group, otherwise use group path
    from cassey.storage.group_storage import get_workspace_id
    group_id = get_workspace_id()
    if storage_id == group_id:
        # This is a group, use group path
        db_path = settings.get_workspace_db_path(storage_id)
    else:
        # This is a user_id, use user path
        db_path = settings.get_user_db_path(storage_id)

    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path.parent


@lru_cache(maxsize=128)
def _get_sqlite_connection(storage_id: str, path: Path) -> sqlite3.Connection:
    """Get a cached SQLite connection for a group.

    Args:
        storage_id: Group identifier.
        path: Path to the DB directory.

    Returns:
        SQLite connection object.
    """
    db_path = path / "db.sqlite"
    # Allow sharing connections across threads (needed for async environment)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)

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
        # Priority: user_id (individual) > group_id (team) > thread_id (fallback)
        from cassey.storage.group_storage import get_user_id
        from cassey.storage.file_sandbox import get_thread_id

        storage_id = get_user_id()
        if storage_id is None:
            storage_id = get_workspace_id()
        if storage_id is None:
            storage_id = get_thread_id()
        if storage_id is None:
            raise ValueError("No context (user_id, group_id, or thread_id) available")

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


def close_all_connections():
    """Close all cached SQLite connections (for shutdown)."""
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
