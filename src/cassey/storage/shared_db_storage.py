"""Shared database storage for organization-wide data."""

from pathlib import Path

from cassey.config import settings
from cassey.storage.db_storage import DBStorage


class SharedDBStorage(DBStorage):
    """Shared DB storage (single DB file for all threads)."""

    def __init__(self, db_path: Path | None = None) -> None:
        path = (db_path or settings.SHARED_DB_PATH).resolve()
        super().__init__(root=path.parent)
        self._db_path = path

    def _get_db_path(self, thread_id: str | None = None) -> Path:
        """Return the shared DB path (ignores thread_id)."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        return self._db_path


_shared_db_storage = SharedDBStorage()


def get_shared_db_storage() -> SharedDBStorage:
    """Get the shared DB storage instance."""
    return _shared_db_storage
