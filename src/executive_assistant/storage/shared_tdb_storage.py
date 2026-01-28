"""Shared TDB storage for organization-wide data."""

from pathlib import Path

from executive_assistant.config import settings
from executive_assistant.storage.sqlite_db_storage import SQLiteDatabase, _get_sqlite_connection


class SharedTDBStorage(SQLiteDatabase):
    """Shared TDB storage using SQLite (single DB file for all threads)."""

    def __init__(self, db_path: Path | None = None) -> None:
        """
        Initialize shared TDB storage.

        Args:
            db_path: Full path to the shared TDB file. If None, uses SHARED_ROOT/tdb.
        """
        if db_path is None:
            db_path = settings.get_shared_tdb_path("shared")
        path = Path(db_path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = _get_sqlite_connection("shared", path.parent)
        super().__init__(thread_id="shared", conn=conn, path=path)


_shared_tdb_storage = SharedTDBStorage()


def get_shared_tdb_storage() -> SharedTDBStorage:
    """Get the shared TDB storage instance."""
    return _shared_tdb_storage
