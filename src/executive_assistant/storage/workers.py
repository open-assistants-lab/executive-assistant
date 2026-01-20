"""Worker storage and management."""

import asyncpg
from dataclasses import dataclass
from datetime import datetime

from executive_assistant.config.settings import settings


@dataclass
class Worker:
    """A worker agent record."""

    id: int
    user_id: str
    thread_id: str
    name: str
    tools: list[str]
    prompt: str
    status: str  # active, archived, deleted
    created_at: datetime
    archived_at: datetime | None

    @property
    def is_active(self) -> bool:
        """Check if worker is active."""
        return self.status == "active"


class WorkerStorage:
    """Storage for workers in PostgreSQL."""

    def __init__(self, conn_string: str | None = None) -> None:
        """Initialize worker storage."""
        self._conn_string = conn_string or settings.POSTGRES_URL

    async def create(
        self,
        user_id: str,
        thread_id: str,
        name: str,
        tools: list[str],
        prompt: str,
    ) -> Worker:
        """Create a new worker.

        Args:
            user_id: User who owns this worker
            thread_id: Thread where worker was created
            name: Name for the worker
            tools: List of tool names to assign to this worker
            prompt: System prompt for the worker

        Returns:
            Created Worker instance
        """
        conn = await asyncpg.connect(self._conn_string)
        try:
            row = await conn.fetchrow(
                """
                INSERT INTO workers (user_id, thread_id, name, tools, prompt)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING *
                """,
                user_id,
                thread_id,
                name,
                tools,
                prompt,
            )
        finally:
            await conn.close()

        return self._row_to_worker(row)

    async def get_by_id(self, worker_id: int) -> Worker | None:
        """Get worker by ID.

        Args:
            worker_id: Worker ID

        Returns:
            Worker instance or None if not found
        """
        conn = await asyncpg.connect(self._conn_string)
        try:
            row = await conn.fetchrow(
                "SELECT * FROM workers WHERE id = $1",
                worker_id,
            )
        finally:
            await conn.close()

        return self._row_to_worker(row) if row else None

    async def list_by_user(
        self, user_id: str, status: str | None = None
    ) -> list[Worker]:
        """List workers for a user, optionally filtered by status.

        Args:
            user_id: User ID to filter by
            status: Optional status filter (active, archived, deleted)

        Returns:
            List of Worker instances
        """
        conn = await asyncpg.connect(self._conn_string)
        try:
            if status:
                rows = await conn.fetch(
                    """
                    SELECT * FROM workers
                    WHERE user_id = $1 AND status = $2
                    ORDER BY created_at DESC
                    """,
                    user_id,
                    status,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT * FROM workers
                    WHERE user_id = $1
                    ORDER BY created_at DESC
                    """,
                    user_id,
                )
        finally:
            await conn.close()

        return [self._row_to_worker(row) for row in rows]

    async def list_by_thread(
        self, thread_id: str, status: str | None = None
    ) -> list[Worker]:
        """List workers for a thread, optionally filtered by status.

        Args:
            thread_id: Thread ID to filter by
            status: Optional status filter (active, archived, deleted)

        Returns:
            List of Worker instances
        """
        conn = await asyncpg.connect(self._conn_string)
        try:
            if status:
                rows = await conn.fetch(
                    """
                    SELECT * FROM workers
                    WHERE thread_id = $1 AND status = $2
                    ORDER BY created_at DESC
                    """,
                    thread_id,
                    status,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT * FROM workers
                    WHERE thread_id = $1
                    ORDER BY created_at DESC
                    """,
                    thread_id,
                )
        finally:
            await conn.close()

        return [self._row_to_worker(row) for row in rows]

    async def archive(self, worker_id: int) -> bool:
        """Archive a worker (soft delete).

        Args:
            worker_id: Worker ID to archive

        Returns:
            True if worker was archived, False if not found
        """
        conn = await asyncpg.connect(self._conn_string)
        try:
            result = await conn.execute(
                """
                UPDATE workers
                SET status = 'archived', archived_at = NOW()
                WHERE id = $1 AND status = 'active'
                """,
                worker_id,
            )
        finally:
            await conn.close()

        return "UPDATE 1" in result

    async def delete(self, worker_id: int) -> bool:
        """Hard delete a worker.

        Args:
            worker_id: Worker ID to delete

        Returns:
            True if worker was deleted, False if not found
        """
        conn = await asyncpg.connect(self._conn_string)
        try:
            result = await conn.execute(
                "DELETE FROM workers WHERE id = $1",
                worker_id,
            )
        finally:
            await conn.close()

        return "UPDATE 1" in result or "DELETE 1" in result

    @staticmethod
    def _row_to_worker(row) -> Worker:
        """Convert database row to Worker object."""
        return Worker(
            id=row["id"],
            user_id=row["user_id"],
            thread_id=row["thread_id"],
            name=row["name"],
            tools=list(row["tools"]) if row["tools"] else [],
            prompt=row["prompt"],
            status=row["status"],
            created_at=row["created_at"],
            archived_at=row["archived_at"],
        )


# Global storage instance
_worker_storage: WorkerStorage | None = None


async def get_worker_storage() -> WorkerStorage:
    """Get or create worker storage instance."""
    global _worker_storage
    if _worker_storage is None:
        _worker_storage = WorkerStorage()
    return _worker_storage
