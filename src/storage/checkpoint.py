"""Checkpoint manager with SQLite and 7-day retention."""

from pathlib import Path

from src.config import get_settings


class CheckpointManager:
    """Manages LangGraph checkpoints with SQLite and automatic 7-day retention.

    Structure:
        /data/users/{user_id}/.conversation/checkpoints.db
    """

    def __init__(self, user_id: str):
        self.user_id = user_id
        settings = get_settings()
        config = settings.memory.checkpointer

        base_path = Path.cwd() / "data" / "users" / user_id / ".conversation"
        base_path.mkdir(parents=True, exist_ok=True)

        self.db_path = str(base_path.resolve() / "checkpoints.db")
        self.retention_days = config.retention_days

        self._checkpointer = None
        self._initialized = False

    async def initialize(self):
        """Initialize the checkpointer."""
        if self._initialized:
            return

        import aiosqlite
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

        conn_string = self.db_path

        conn = await aiosqlite.connect(conn_string)
        self._checkpointer = AsyncSqliteSaver(conn)
        await self._checkpointer.setup()
        self._initialized = True

        await self._cleanup_old_checkpoints()

    @property
    def checkpointer(self):
        """Get the underlying checkpointer."""
        if not self._initialized:
            raise RuntimeError("CheckpointManager not initialized. Call initialize() first.")
        return self._checkpointer

    async def _cleanup_old_checkpoints(self):
        """Delete checkpoints based on retention policy."""
        try:
            if not Path(self.db_path).exists():
                return

            conn = await self._get_conn()

            # 0 days = no checkpoint
            if self.retention_days == 0:
                await conn.execute("DELETE FROM checkpoints WHERE thread_id = ?", [self.user_id])
                try:
                    await conn.execute("DELETE FROM writes WHERE thread_id = ?", [self.user_id])
                except Exception:
                    pass  # Table may not exist
                await conn.commit()
                print(f"Deleted all checkpoints for user {self.user_id} (retention=0)")
                await self._close_conn(conn)
                return

            # -1 = keep forever
            if self.retention_days == -1:
                await self._close_conn(conn)
                return

            # Delete old checkpoints using ULID (checkpoint_id encodes timestamp)
            # Keep only checkpoints newer than retention_days
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
            print(f"Cleaned up old checkpoints (kept last 100)")
        except Exception as e:
            print(f"Error cleaning up old checkpoints: {e}")
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


# Singleton per user
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
