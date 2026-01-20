"""Shared database storage for organization-wide data."""

from pathlib import Path

from executive_assistant.config import settings
from executive_assistant.storage.sqlite_db_storage import SQLiteDatabase, _get_sqlite_connection


class SharedDBStorage(SQLiteDatabase):
    """Shared DB storage using SQLite (single DB file for all threads)."""

    def __init__(self, db_path: Path | None = None) -> None:
        """
        Initialize shared DB storage.

        Args:
            db_path: Full path to the shared DB file. If None, uses SHARED_ROOT/db_name.
            db_name: Name of the DB file (used only if db_path is None).
        """
        if db_path is None:
            db_path = settings.get_shared_db_path("shared")
        path = Path(db_path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = _get_sqlite_connection("shared", path.parent)
        super().__init__(workspace_id="shared", conn=conn, path=path)


_shared_db_storage = SharedDBStorage()


def get_shared_db_storage() -> SharedDBStorage:
    """Get the shared DB storage instance."""
    return _shared_db_storage
