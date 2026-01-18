"""Shared database storage for organization-wide data."""

from pathlib import Path

from cassey.config import settings
from cassey.storage.db_storage import DBStorage


class SharedDBStorage(DBStorage):
    """Shared DB storage (single DB file for all threads)."""

    def __init__(self, db_path: Path | None = None, db_name: str = "shared.db") -> None:
        """
        Initialize shared DB storage.

        Args:
            db_path: Full path to the shared DB file. If None, uses SHARED_ROOT/db_name.
            db_name: Name of the DB file (used only if db_path is None).
        """
        if db_path is None:
            db_path = settings.SHARED_ROOT / db_name
        path = Path(db_path).resolve()
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
