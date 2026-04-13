"""Database manager for Executive Assistant.

NOTE: This legacy module is not used in the main production code path.
The active checkpointer is managed by CheckpointManager in checkpoint.py,
which respects the CHECKPOINT_ENABLED config flag.

This module is kept for backward compatibility only.
"""

from pathlib import Path
from typing import Optional

from src.app_logging import get_logger
from src.config import get_settings

logger = get_logger()

Base = object  # placeholder; SQLAlchemy declarative_base removed (unused)


class DatabaseManager:
    """Manages database connections and checkpointer.

    Respects CHECKPOINT_ENABLED config. If disabled (default),
    the checkpointer will be None and no SQLite connection is created.
    """

    _instance: Optional["DatabaseManager"] = None
    _checkpointer = None

    def __new__(cls) -> "DatabaseManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def initialize(self) -> None:
        """Initialize SQLite checkpointer only if enabled in config."""
        settings = get_settings()

        if not settings.memory.checkpointer.enabled:
            logger.info("database.checkpointer_disabled", {}, channel="system")
            self._checkpointer = None
            return

        from langgraph.checkpoint.sqlite import SqliteSaver

        user_id = settings.database.user or "default"
        checkpoint_path = Path("data/users") / user_id / "messages" / "checkpoints.db"
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

        self._checkpointer = SqliteSaver.from_conn_string(f"sqlite:///{checkpoint_path}")
        logger.info(
            "database.checkpointer_enabled", {"path": str(checkpoint_path)}, channel="system"
        )

    async def close(self) -> None:
        """Close database connections."""
        self._checkpointer = None

    @property
    def checkpointer(self):
        """Get LangGraph checkpointer (may be None if disabled)."""
        return self._checkpointer


def get_database() -> DatabaseManager:
    """Get database manager singleton."""
    return DatabaseManager()


def init_db() -> DatabaseManager:
    """Initialize database and return manager."""
    db = get_database()
    db.initialize()
    return db
