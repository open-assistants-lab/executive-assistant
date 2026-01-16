"""Knowledge base storage using per-thread DuckDB files."""

from pathlib import Path

from cassey.config import settings
from cassey.storage.db_storage import DBStorage
from cassey.storage.file_sandbox import get_thread_id


class KBStorage(DBStorage):
    """KB storage that mirrors DBStorage layout with a separate root."""

    def __init__(self, root: Path | None = None) -> None:
        super().__init__(root or settings.KB_ROOT)

    def _get_db_path(self, thread_id: str | None = None) -> Path:
        """
        Get the KB database path for a thread.

        Args:
            thread_id: Thread identifier. If None, uses current context thread_id.

        Returns:
            Path to the KB database file.
        """
        if thread_id is None:
            thread_id = get_thread_id()

        if thread_id is None:
            raise ValueError("No thread_id provided and no thread_id in context")

        # Use new path helper with backward compatibility fallback
        kb_path = settings.get_thread_kb_path(thread_id)
        kb_path.parent.mkdir(parents=True, exist_ok=True)
        return kb_path


_kb_storage = KBStorage()


def get_kb_storage() -> KBStorage:
    """Get the global KB storage instance."""
    return _kb_storage
