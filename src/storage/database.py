"""Database manager for Executive Assistant."""

from pathlib import Path
from typing import Optional

from langgraph.checkpoint.sqlite import SqliteSaver
from sqlalchemy.orm import declarative_base

from src.config import get_settings

Base = declarative_base()


class DatabaseManager:
    """Manages database connections and checkpointer."""

    _instance: Optional["DatabaseManager"] = None
    _checkpointer: SqliteSaver | None = None

    def __new__(cls) -> "DatabaseManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def initialize(self) -> None:
        """Initialize SQLite checkpointer."""
        settings = get_settings()
        user_id = settings.database.user or "default"

        checkpoint_path = Path("data/users") / user_id / "messages" / "checkpoints.db"
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

        self._checkpointer = SqliteSaver.from_conn_string(f"sqlite:///{checkpoint_path}")

    async def close(self) -> None:
        """Close database connections."""
        self._checkpointer = None

    @property
    def checkpointer(self) -> SqliteSaver:
        """Get LangGraph checkpointer."""
        if self._checkpointer is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return self._checkpointer


def get_database() -> DatabaseManager:
    """Get database manager singleton."""
    return DatabaseManager()


def init_db() -> DatabaseManager:
    """Initialize database and return manager."""
    db = get_database()
    db.initialize()
    return db
