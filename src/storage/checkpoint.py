"""Checkpoint manager with SQLite and 7-day retention."""

from pathlib import Path

from src.app_logging import get_logger
from src.config import get_settings


class CheckpointManager:
    """Manages LangGraph checkpoints with SQLite and automatic 7-day retention.

    Structure:
        /data/users/{user_id}/messages/checkpoints.db
    """

    def __init__(self, user_id: str):
        self.user_id = user_id
        self._logger = get_logger()
        self._checkpointer = None

        base_path = Path(f"data/users/{user_id}/messages")
        base_path.mkdir(parents=True, exist_ok=True)
        self.db_path = str((base_path / "checkpoints.db").resolve())

    @property
    def checkpointer(self):
        """Get the checkpointer (may be None if not initialized)."""
        return self._checkpointer

    async def initialize(self):
        """Initialize the checkpoint manager."""
        settings = get_settings()
        memory_config = settings.memory

        if not memory_config.checkpointer.enabled:
            self._logger.info(
                "checkpoint.disabled",
                {"user_id": self.user_id},
                channel="system",
            )
            return

        import aiosqlite
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

        conn = await aiosqlite.connect(self.db_path)
        self._checkpointer = AsyncSqliteSaver(conn)

        self._logger.info(
            "checkpoint.enabled",
            {"user_id": self.user_id, "path": self.db_path},
            channel="system",
        )

        await self._cleanup_old_checkpoints()

    async def _cleanup_old_checkpoints(self):
        """Clean up old checkpoints, keeping only recent ones."""
        try:
            import aiosqlite

            conn = await aiosqlite.connect(self.db_path)
            await conn.execute(
                """
                DELETE FROM checkpoints
                WHERE thread_id = ?
                AND checkpoint_id NOT IN (
                    SELECT checkpoint_id FROM checkpoints
                    WHERE thread_id = ?
                    ORDER BY checkpoint_id DESC
                    LIMIT 100
                )
            """,
                [self.user_id, self.user_id],
            )
            await conn.commit()
            self._logger.info(
                "checkpoint.cleanup",
                {"event": "cleaned", "user_id": self.user_id, "kept": 100},
                channel="system",
            )
        except Exception as e:
            self._logger.warning(
                "checkpoint.cleanup",
                {"event": "error", "user_id": self.user_id, "error": str(e)},
                channel="system",
            )
        finally:
            await self._close_conn(conn)

    async def _get_conn(self):
        """Get database connection."""
        import aiosqlite

        conn = await aiosqlite.connect(self.db_path)
        return conn

    async def _close_conn(self, conn):
        """Close database connection."""
        if conn:
            await conn.close()

    async def delete_thread(self):
        """Delete all checkpoints for this user."""
        if self._checkpointer:
            await self._checkpointer.adelete_thread(self.user_id)


_managers: dict[str, CheckpointManager] = {}


def get_checkpoint_manager(user_id: str = "default") -> CheckpointManager:
    """Get checkpoint manager for a user."""
    if user_id not in _managers:
        _managers[user_id] = CheckpointManager(user_id)
    return _managers[user_id]


async def init_checkpoint_manager(user_id: str = "default") -> CheckpointManager:
    """Initialize and return checkpoint manager."""
    manager = get_checkpoint_manager(user_id)
    await manager.initialize()
    return manager
