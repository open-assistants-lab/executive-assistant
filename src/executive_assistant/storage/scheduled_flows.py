"""Scheduled flows storage and management.

Handles storage and retrieval of scheduled flows that execute flow agents.
Supports cron expressions for recurring flows.
"""

import asyncpg
from dataclasses import dataclass
from datetime import datetime

from executive_assistant.config.settings import settings


@dataclass
class ScheduledFlow:
    """A scheduled flow record."""

    id: int
    thread_id: str
    name: str | None
    task: str
    flow: str
    due_time: datetime
    status: str  # pending, running, completed, failed, cancelled
    cron: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    result: str | None

    @property
    def is_pending(self) -> bool:
        """Check if flow is pending."""
        return self.status == "pending"

    @property
    def is_running(self) -> bool:
        """Check if flow is running."""
        return self.status == "running"

    @property
    def is_completed(self) -> bool:
        """Check if flow completed successfully."""
        return self.status == "completed"

    @property
    def is_failed(self) -> bool:
        """Check if flow failed."""
        return self.status == "failed"

    @property
    def is_recurring(self) -> bool:
        """Check if flow has a recurrence schedule."""
        return self.cron is not None and self.cron != ""


class ScheduledFlowStorage:
    """Storage for scheduled flows in PostgreSQL."""

    def __init__(self, conn_string: str | None = None) -> None:
        """Initialize scheduled flow storage."""
        self._conn_string = conn_string or settings.POSTGRES_URL
        self._schema_ready = False


    async def _ensure_schema(self, conn: asyncpg.Connection) -> None:
        """Ensure the scheduled_flows schema exists."""
        if self._schema_ready:
            return

        statements = [
            """
            CREATE TABLE IF NOT EXISTS scheduled_flows (
                id SERIAL PRIMARY KEY,
                thread_id VARCHAR(255) NOT NULL,
                name VARCHAR(255),
                task TEXT NOT NULL,
                flow TEXT NOT NULL,
                due_time TIMESTAMP NOT NULL,
                status VARCHAR(20) DEFAULT 'pending',
                cron VARCHAR(100),
                created_at TIMESTAMP DEFAULT NOW(),
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                error_message TEXT,
                result TEXT
            );
            """,
            "CREATE INDEX IF NOT EXISTS idx_scheduled_flows_due_time ON scheduled_flows(due_time) WHERE status = 'pending';",
            "CREATE INDEX IF NOT EXISTS idx_scheduled_flows_thread_id ON scheduled_flows(thread_id);",
            "CREATE INDEX IF NOT EXISTS idx_scheduled_flows_status ON scheduled_flows(status);",
        ]

        for statement in statements:
            await conn.execute(statement)

        # Backward-compat cleanup: drop legacy user_id column if present
        has_user_id = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'scheduled_flows'
                  AND column_name = 'user_id'
            )
            """
        )
        if has_user_id:
            await conn.execute("ALTER TABLE scheduled_flows DROP COLUMN IF EXISTS user_id;")

        self._schema_ready = True

    async def create(
        self,
        thread_id: str,
        task: str,
        flow: str,
        due_time: datetime,
        name: str | None = None,
        cron: str | None = None,
    ) -> ScheduledFlow:
        """Create a new scheduled flow.

        Args:
            thread_id: Thread where flow was created
            task: Concrete task description
            flow: Execution flow with conditions/loops
            due_time: When to execute the flow
            name: Optional name for the flow
            cron: Optional cron expression for recurring flows

        Returns:
            Created ScheduledFlow instance
        """
        conn = await asyncpg.connect(self._conn_string)
        await self._ensure_schema(conn)
        try:
            row = await conn.fetchrow(
                """
                INSERT INTO scheduled_flows (
                    thread_id, name, task, flow, due_time, cron
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING *
                """,
                thread_id,
                name,
                task,
                flow,
                due_time,
                cron,
            )
        finally:
            await conn.close()

        return self._row_to_flow(row)

    async def get_by_id(self, flow_id: int) -> ScheduledFlow | None:
        """Get flow by ID.

        Args:
            flow_id: Flow ID

        Returns:
            ScheduledFlow instance or None if not found
        """
        conn = await asyncpg.connect(self._conn_string)
        await self._ensure_schema(conn)
        try:
            row = await conn.fetchrow(
                "SELECT * FROM scheduled_flows WHERE id = $1",
                flow_id,
            )
        finally:
            await conn.close()

        return self._row_to_flow(row) if row else None

    async def get_due_flows(self, before: datetime) -> list[ScheduledFlow]:
        """Get all pending flows due before the given time.

        Args:
            before: Get flows due at or before this time

        Returns:
            List of ScheduledFlow instances that are due
        """
        conn = await asyncpg.connect(self._conn_string)
        await self._ensure_schema(conn)
        try:
            rows = await conn.fetch(
                """
                SELECT * FROM scheduled_flows
                WHERE status = 'pending' AND due_time <= $1
                ORDER BY due_time ASC
                """,
                before,
            )
        finally:
            await conn.close()

        return [self._row_to_flow(row) for row in rows]

    async def list_by_thread(
        self, thread_id: str, status: str | None = None
    ) -> list[ScheduledFlow]:
        """List flows for a thread, optionally filtered by status.

        Args:
            thread_id: Thread ID to filter by
            status: Optional status filter

        Returns:
            List of ScheduledFlow instances
        """
        conn = await asyncpg.connect(self._conn_string)
        await self._ensure_schema(conn)
        try:
            if status:
                rows = await conn.fetch(
                    """
                    SELECT * FROM scheduled_flows
                    WHERE thread_id = $1 AND status = $2
                    ORDER BY created_at DESC
                    """,
                    thread_id,
                    status,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT * FROM scheduled_flows
                    WHERE thread_id = $1
                    ORDER BY created_at DESC
                    """,
                    thread_id,
                )
        finally:
            await conn.close()

        return [self._row_to_flow(row) for row in rows]

    async def mark_started(self, flow_id: int, started_at: datetime | None = None) -> bool:
        """Mark flow as running.

        Args:
            flow_id: Flow ID to update
            started_at: Optional start time (defaults to now)

        Returns:
            True if flow was updated, False if not found
        """
        if started_at is None:
            started_at = datetime.now()

        conn = await asyncpg.connect(self._conn_string)
        await self._ensure_schema(conn)
        try:
            result = await conn.execute(
                """
                UPDATE scheduled_flows
                SET status = 'running', started_at = $1
                WHERE id = $2 AND status = 'pending'
                """,
                started_at,
                flow_id,
            )
        finally:
            await conn.close()

        return "UPDATE 1" in result

    async def mark_completed(
        self, flow_id: int, result: str | None = None, completed_at: datetime | None = None
    ) -> bool:
        """Mark flow as completed.

        Args:
            flow_id: Flow ID to update
            result: Optional result text from execution
            completed_at: Optional completion time (defaults to now)

        Returns:
            True if flow was updated, False if not found
        """
        if completed_at is None:
            completed_at = datetime.now()

        conn = await asyncpg.connect(self._conn_string)
        await self._ensure_schema(conn)
        try:
            result = await conn.execute(
                """
                UPDATE scheduled_flows
                SET status = 'completed', completed_at = $1, result = $2
                WHERE id = $3 AND status = 'running'
                """,
                completed_at,
                result,
                flow_id,
            )
        finally:
            await conn.close()

        return "UPDATE 1" in result

    async def mark_failed(
        self, flow_id: int, error_message: str, completed_at: datetime | None = None
    ) -> bool:
        """Mark flow as failed.

        Args:
            flow_id: Flow ID to update
            error_message: Error message describing the failure
            completed_at: Optional completion time (defaults to now)

        Returns:
            True if flow was updated, False if not found
        """
        if completed_at is None:
            completed_at = datetime.now()

        conn = await asyncpg.connect(self._conn_string)
        await self._ensure_schema(conn)
        try:
            result = await conn.execute(
                """
                UPDATE scheduled_flows
                SET status = 'failed', completed_at = $1, error_message = $2
                WHERE id = $3 AND status IN ('pending', 'running')
                """,
                completed_at,
                error_message,
                flow_id,
            )
        finally:
            await conn.close()

        return "UPDATE 1" in result

    async def delete(self, flow_id: int) -> bool:
        """Delete a flow by ID."""
        conn = await asyncpg.connect(self._conn_string)
        await self._ensure_schema(conn)
        try:
            result = await conn.execute(
                "DELETE FROM scheduled_flows WHERE id = $1",
                flow_id,
            )
        finally:
            await conn.close()

        return result and result.startswith("DELETE") and not result.endswith("DELETE 0")

    async def cancel(self, flow_id: int) -> bool:
        """Cancel a pending flow.

        Args:
            flow_id: Flow ID to cancel

        Returns:
            True if flow was cancelled, False if not found or already running
        """
        conn = await asyncpg.connect(self._conn_string)
        await self._ensure_schema(conn)
        try:
            result = await conn.execute(
                """
                UPDATE scheduled_flows
                SET status = 'cancelled', completed_at = NOW()
                WHERE id = $1 AND status = 'pending'
                """,
                flow_id,
            )
        finally:
            await conn.close()

        return "UPDATE 1" in result

    async def create_next_instance(
        self,
        parent_flow: ScheduledFlow,
        next_due_time: datetime,
    ) -> ScheduledFlow | None:
        """Create the next instance of a recurring flow.

        Args:
            parent_flow: The completed flow to create a follow-up for
            next_due_time: When the next instance should run

        Returns:
            New ScheduledFlow instance, or None if parent wasn't recurring
        """
        if not parent_flow.cron:
            return None

        return await self.create(
            thread_id=parent_flow.thread_id,
            task=parent_flow.task,
            flow=parent_flow.flow,
            due_time=next_due_time,
            name=parent_flow.name,
            cron=parent_flow.cron,
        )

    @staticmethod
    def _row_to_flow(row) -> ScheduledFlow:
        """Convert database row to ScheduledFlow object."""
        return ScheduledFlow(
            id=row["id"],
            thread_id=row["thread_id"],
            name=row["name"],
            task=row["task"],
            flow=row["flow"],
            due_time=row["due_time"],
            status=row["status"],
            cron=row["cron"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            error_message=row["error_message"],
            result=row["result"],
        )


# Global storage instance
_flow_storage: ScheduledFlowStorage | None = None


async def get_scheduled_flow_storage() -> ScheduledFlowStorage:
    """Get or create scheduled flow storage instance."""
    global _flow_storage
    if _flow_storage is None:
        _flow_storage = ScheduledFlowStorage()
    return _flow_storage
