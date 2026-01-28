"""Database storage for tabular data with thread/user isolation."""

from pathlib import Path
import re
from typing import Any

import duckdb

from executive_assistant.config import settings
from executive_assistant.storage.user_registry import sanitize_thread_id
from executive_assistant.storage.thread_storage import get_thread_id


_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def validate_identifier(name: str) -> str:
    """Validate SQL identifier to prevent injection via table names."""
    if not _IDENTIFIER_RE.match(name):
        raise ValueError(
            f"Invalid identifier '{name}'. Use letters, numbers, and underscores only, "
            "starting with a letter or underscore."
        )
    return name


class DBStorage:
    """
    Database storage for tabular data.

    Each thread has its own isolated database file.
    Supports per-thread storage (no groups).
    """

    def __init__(self, root: Path) -> None:
        """
        Initialize database storage with a required root directory.

        Args:
            root: Root directory for database files (required).
        """
        self.root = Path(root).resolve()

    def _get_db_path(self, thread_id: str | None = None) -> Path:
        """
        Get the database path for a thread.

        Priority:
        1. thread_id if provided
        2. thread_id from context

        Args:
            thread_id: Thread identifier.

        Returns:
            Path to the database file.
        """
        # Use the instance root if provided (scoped DBStorage)
        if self.root:
            db_path = (self.root / "db.sqlite").resolve()
            db_path.parent.mkdir(parents=True, exist_ok=True)
            return db_path

        if thread_id is None:
            thread_id = get_thread_id()

        if thread_id is None:
            raise ValueError("No thread_id provided and none in context")

        db_path = settings.get_thread_tdb_path(thread_id)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return db_path

    def get_connection(self, thread_id: str | None = None) -> duckdb.DuckDBPyConnection:
        """
        Get a database connection for the current thread.

        Args:
            thread_id: Thread identifier. If None, uses current context thread_id.

        Returns:
            Database connection object.
        """
        db_path = self._get_db_path(thread_id)
        return duckdb.connect(str(db_path))

    def execute(self, query: str, thread_id: str | None = None) -> list[tuple]:
        """
        Execute a SQL query and return results.

        Args:
            query: SQL query to execute.
            thread_id: Thread identifier. If None, uses current context thread_id.

        Returns:
            Query results as list of tuples.
        """
        conn = self.get_connection(thread_id)
        try:
            result = conn.execute(query).fetchall()
            return result
        finally:
            conn.close()

    def execute_df(self, query: str, thread_id: str | None = None) -> Any:
        """
        Execute a SQL query and return results as a pandas DataFrame.

        Args:
            query: SQL query to execute.
            thread_id: Thread identifier. If None, uses current context thread_id.

        Returns:
            Query results as pandas DataFrame.
        """
        import pandas as pd

        conn = self.get_connection(thread_id)
        try:
            result = conn.execute(query).fetchdf()
            return result
        finally:
            conn.close()

    def create_table_from_data(
        self,
        table_name: str,
        data: list[dict] | list[tuple],
        columns: list[str] | None = None,
        thread_id: str | None = None,
    ) -> None:
        """
        Create a table from data (list of dicts or tuples).

        Args:
            table_name: Name of the table to create.
            data: Data to insert (list of dicts or list of tuples).
            columns: Column names (required if data is list of tuples).
            thread_id: Thread identifier. If None, uses current context thread_id.
        """
        validate_identifier(table_name)
        import pandas as pd

        conn = self.get_connection(thread_id)
        try:
            # Drop table if exists
            conn.execute(f"DROP TABLE IF EXISTS {table_name}")

            if isinstance(data, list) and len(data) > 0:
                # Convert to pandas DataFrame
                if columns:
                    df = pd.DataFrame(data, columns=columns)
                else:
                    df = pd.DataFrame(data)

                # Register and create table
                conn.register("df_data", df)
                conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM df_data")
            else:
                # Empty data - create table with no rows
                if columns:
                    col_defs = ", ".join(f"{col} VARCHAR" for col in columns)
                    conn.execute(f"CREATE TABLE {table_name} ({col_defs})")
                else:
                    raise ValueError("Cannot create table: no data and no columns provided")
        finally:
            conn.close()

    def append_to_table(
        self,
        table_name: str,
        data: list[dict] | list[tuple],
        thread_id: str | None = None,
    ) -> None:
        """
        Append data to an existing table.

        Args:
            table_name: Name of the table to append to.
            data: Data to insert.
            thread_id: Thread identifier. If None, uses current context thread_id.
        """
        validate_identifier(table_name)
        import pandas as pd

        conn = self.get_connection(thread_id)
        try:
            df = pd.DataFrame(data)
            conn.register("new_data", df)
            conn.execute(f"INSERT INTO {table_name} SELECT * FROM new_data")
        finally:
            conn.close()

    def list_tables(self, thread_id: str | None = None) -> list[str]:
        """
        List all tables in the thread's database.

        Args:
            thread_id: Thread identifier. If None, uses current context thread_id.

        Returns:
            List of table names.
        """
        conn = self.get_connection(thread_id)
        try:
            result = conn.execute("SHOW TABLES").fetchall()
            return [row[0] for row in result]
        finally:
            conn.close()

    def table_exists(self, table_name: str, thread_id: str | None = None) -> bool:
        """
        Check if a table exists.

        Args:
            table_name: Name of the table.
            thread_id: Thread identifier. If None, uses current context thread_id.

        Returns:
            True if table exists, False otherwise.
        """
        tables = self.list_tables(thread_id)
        return table_name in tables

    def get_table_info(self, table_name: str, thread_id: str | None = None) -> list[dict]:
        """
        Get information about a table's columns.

        Args:
            table_name: Name of the table.
            thread_id: Thread identifier. If None, uses current context thread_id.

        Returns:
            List of column info dicts.
        """
        validate_identifier(table_name)
        conn = self.get_connection(thread_id)
        try:
            result = conn.execute(f"PRAGMA table_info('{table_name}')").fetchall()
            return [
                {
                    "cid": row[0],
                    "name": row[1],
                    "type": row[2],
                    "notnull": row[3],
                    "dflt_value": row[4],
                    "pk": row[5],
                }
                for row in result
            ]
        finally:
            conn.close()

    def drop_table(self, table_name: str, thread_id: str | None = None) -> None:
        """
        Drop a table if it exists.

        Args:
            table_name: Name of the table to drop.
            thread_id: Thread identifier. If None, uses current context thread_id.
        """
        validate_identifier(table_name)
        conn = self.get_connection(thread_id)
        try:
            conn.execute(f"DROP TABLE IF EXISTS {table_name}")
        finally:
            conn.close()

    def export_table(
        self,
        table_name: str,
        output_path: Path,
        format: str = "csv",
        thread_id: str | None = None,
    ) -> None:
        """
        Export a table to a file.

        Args:
            table_name: Name of the table to export.
            output_path: Path to save the exported file.
            format: Export format ("csv", "parquet", "json").
            thread_id: Thread identifier. If None, uses current context thread_id.
        """
        validate_identifier(table_name)
        conn = self.get_connection(thread_id)
        try:
            if format == "csv":
                conn.execute(f"COPY {table_name} TO '{output_path}' (HEADER, DELIMITER ',')")
            elif format == "parquet":
                conn.execute(f"COPY {table_name} TO '{output_path}' (FORMAT 'parquet')")
            elif format == "json":
                conn.execute(f"COPY {table_name} TO '{output_path}' (FORMAT 'json')")
            else:
                raise ValueError(f"Unsupported export format: {format}")
        finally:
            conn.close()

    def delete_db(self, thread_id: str) -> bool:
        """
        Delete the database file for a thread.

        Args:
            thread_id: Thread identifier.

        Returns:
            True if file was deleted, False if it didn't exist.
        """
        db_path = self._get_db_path(thread_id)
        if db_path.exists():
            db_path.unlink()
            return True
        return False

    def merge_databases(
        self,
        source_thread_ids: list[str],
        target_thread_id: str,
    ) -> dict[str, Any]:
        """
        Merge databases from multiple threads into one.

        Copies tables from source databases into the target database.
        Tables are prefixed with source thread name to avoid conflicts.

        Args:
            source_thread_ids: List of source thread IDs to merge.
            target_thread_id: Target thread ID for merged database.

        Returns:
            Summary of merge operation.
        """
        target_db_path = self._get_db_path(target_thread_id)
        target_db_path.parent.mkdir(parents=True, exist_ok=True)

        tables_merged = 0
        errors = []

        for source_thread_id in source_thread_ids:
            source_db_path = self._get_db_path(source_thread_id)

            if not source_db_path.exists():
                errors.append(f"Source DB not found: {source_thread_id}")
                continue

            # Sanitize source thread_id for table prefix
            safe_source = sanitize_thread_id(source_thread_id)

            try:
                # Get source tables
                source_conn = duckdb.connect(str(source_db_path))
                try:
                    source_tables = source_conn.execute("SHOW TABLES").fetchall()
                    source_table_names = [row[0] for row in source_tables]
                finally:
                    source_conn.close()

                # Copy tables to target
                target_conn = duckdb.connect(str(target_db_path))
                try:
                    # Attach source database
                    target_conn.execute(f"ATTACH '{source_db_path}' AS source_db")

                    for table_name in source_table_names:
                        # Copy with prefix to avoid conflicts
                        new_table_name = f"{table_name}_from_{safe_source}"
                        target_conn.execute(
                            f"CREATE TABLE {new_table_name} AS SELECT * FROM source_db.{table_name}"
                        )
                        tables_merged += 1

                    target_conn.execute("DETACH source_db")
                finally:
                    target_conn.close()

                # Delete source database after successful merge
                source_db_path.unlink()

            except Exception as e:
                errors.append(f"Error merging {source_thread_id}: {str(e)}")

        return {
            "target_thread_id": target_thread_id,
            "source_thread_ids": source_thread_ids,
            "tables_merged": tables_merged,
            "errors": errors,
        }


# Cache DBStorage instances per context (thread)
_db_storage_by_context: dict[str, DBStorage] = {}


def get_db_storage() -> DBStorage:
    """
    Get a database storage instance scoped to the current thread context.

    Returns:
        A DBStorage instance scoped to the current thread.

    Raises:
        ValueError: If no thread_id context is available.
    """
    thread_id = get_thread_id()
    if thread_id:
        cache_key = f"thread:{thread_id}"
        cached = _db_storage_by_context.get(cache_key)
        if cached:
            return cached
        db_path = settings.get_thread_tdb_path(thread_id)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        storage = DBStorage(root=db_path.parent)
        _db_storage_by_context[cache_key] = storage
        return storage

    raise ValueError(
        "DBStorage requires thread_id context. "
        "Ensure context is set before calling get_db_storage()."
    )
