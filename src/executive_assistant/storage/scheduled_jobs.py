"""Scheduled jobs storage and management.

Handles storage and retrieval of scheduled jobs that execute worker agents.
Supports cron expressions for recurring jobs.
"""

import asyncpg
from dataclasses import dataclass
from datetime import datetime

from executive_assistant.config.settings import settings


@dataclass
class ScheduledJob:
    """A scheduled job record."""

    id: int
    user_id: str
    thread_id: str
    worker_id: int | None
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
        """Check if job is pending."""
        return self.status == "pending"

    @property
    def is_running(self) -> bool:
        """Check if job is running."""
        return self.status == "running"

    @property
    def is_completed(self) -> bool:
        """Check if job completed successfully."""
        return self.status == "completed"

    @property
    def is_failed(self) -> bool:
        """Check if job failed."""
        return self.status == "failed"

    @property
    def is_recurring(self) -> bool:
        """Check if job has a recurrence schedule."""
        return self.cron is not None and self.cron != ""


class ScheduledJobStorage:
    """Storage for scheduled jobs in PostgreSQL."""

    def __init__(self, conn_string: str | None = None) -> None:
        """Initialize scheduled job storage."""
        self._conn_string = conn_string or settings.POSTGRES_URL

    async def create(
        self,
        user_id: str,
        thread_id: str,
        task: str,
        flow: str,
        due_time: datetime,
        worker_id: int | None = None,
        name: str | None = None,
        cron: str | None = None,
    ) -> ScheduledJob:
        """Create a new scheduled job.

        Args:
            user_id: User who owns this job
            thread_id: Thread where job was created
            task: Concrete task description
            flow: Execution flow with conditions/loops
            due_time: When to execute the job
            worker_id: Optional worker ID to execute the job
            name: Optional name for the job
            cron: Optional cron expression for recurring jobs

        Returns:
            Created ScheduledJob instance
        """
        conn = await asyncpg.connect(self._conn_string)
        try:
            row = await conn.fetchrow(
                """
                INSERT INTO scheduled_jobs (
                    user_id, thread_id, worker_id, name, task, flow, due_time, cron
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING *
                """,
                user_id,
                thread_id,
                worker_id,
                name,
                task,
                flow,
                due_time,
                cron,
            )
        finally:
            await conn.close()

        return self._row_to_job(row)

    async def get_by_id(self, job_id: int) -> ScheduledJob | None:
        """Get job by ID.

        Args:
            job_id: Job ID

        Returns:
            ScheduledJob instance or None if not found
        """
        conn = await asyncpg.connect(self._conn_string)
        try:
            row = await conn.fetchrow(
                "SELECT * FROM scheduled_jobs WHERE id = $1",
                job_id,
            )
        finally:
            await conn.close()

        return self._row_to_job(row) if row else None

    async def get_due_jobs(self, before: datetime) -> list[ScheduledJob]:
        """Get all pending jobs due before the given time.

        Args:
            before: Get jobs due at or before this time

        Returns:
            List of ScheduledJob instances that are due
        """
        conn = await asyncpg.connect(self._conn_string)
        try:
            rows = await conn.fetch(
                """
                SELECT * FROM scheduled_jobs
                WHERE status = 'pending' AND due_time <= $1
                ORDER BY due_time ASC
                """,
                before,
            )
        finally:
            await conn.close()

        return [self._row_to_job(row) for row in rows]

    async def list_by_user(
        self, user_id: str, status: str | None = None
    ) -> list[ScheduledJob]:
        """List jobs for a user, optionally filtered by status.

        Args:
            user_id: User ID to filter by
            status: Optional status filter

        Returns:
            List of ScheduledJob instances
        """
        conn = await asyncpg.connect(self._conn_string)
        try:
            if status:
                rows = await conn.fetch(
                    """
                    SELECT * FROM scheduled_jobs
                    WHERE user_id = $1 AND status = $2
                    ORDER BY created_at DESC
                    """,
                    user_id,
                    status,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT * FROM scheduled_jobs
                    WHERE user_id = $1
                    ORDER BY created_at DESC
                    """,
                    user_id,
                )
        finally:
            await conn.close()

        return [self._row_to_job(row) for row in rows]

    async def list_by_thread(
        self, thread_id: str, status: str | None = None
    ) -> list[ScheduledJob]:
        """List jobs for a thread, optionally filtered by status.

        Args:
            thread_id: Thread ID to filter by
            status: Optional status filter

        Returns:
            List of ScheduledJob instances
        """
        conn = await asyncpg.connect(self._conn_string)
        try:
            if status:
                rows = await conn.fetch(
                    """
                    SELECT * FROM scheduled_jobs
                    WHERE thread_id = $1 AND status = $2
                    ORDER BY created_at DESC
                    """,
                    thread_id,
                    status,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT * FROM scheduled_jobs
                    WHERE thread_id = $1
                    ORDER BY created_at DESC
                    """,
                    thread_id,
                )
        finally:
            await conn.close()

        return [self._row_to_job(row) for row in rows]

    async def mark_started(self, job_id: int, started_at: datetime | None = None) -> bool:
        """Mark job as running.

        Args:
            job_id: Job ID to update
            started_at: Optional start time (defaults to now)

        Returns:
            True if job was updated, False if not found
        """
        if started_at is None:
            started_at = datetime.now()

        conn = await asyncpg.connect(self._conn_string)
        try:
            result = await conn.execute(
                """
                UPDATE scheduled_jobs
                SET status = 'running', started_at = $1
                WHERE id = $2 AND status = 'pending'
                """,
                started_at,
                job_id,
            )
        finally:
            await conn.close()

        return "UPDATE 1" in result

    async def mark_completed(
        self, job_id: int, result: str | None = None, completed_at: datetime | None = None
    ) -> bool:
        """Mark job as completed.

        Args:
            job_id: Job ID to update
            result: Optional result text from execution
            completed_at: Optional completion time (defaults to now)

        Returns:
            True if job was updated, False if not found
        """
        if completed_at is None:
            completed_at = datetime.now()

        conn = await asyncpg.connect(self._conn_string)
        try:
            result = await conn.execute(
                """
                UPDATE scheduled_jobs
                SET status = 'completed', completed_at = $1, result = $2
                WHERE id = $3 AND status = 'running'
                """,
                completed_at,
                result,
                job_id,
            )
        finally:
            await conn.close()

        return "UPDATE 1" in result

    async def mark_failed(
        self, job_id: int, error_message: str, completed_at: datetime | None = None
    ) -> bool:
        """Mark job as failed.

        Args:
            job_id: Job ID to update
            error_message: Error message describing the failure
            completed_at: Optional completion time (defaults to now)

        Returns:
            True if job was updated, False if not found
        """
        if completed_at is None:
            completed_at = datetime.now()

        conn = await asyncpg.connect(self._conn_string)
        try:
            result = await conn.execute(
                """
                UPDATE scheduled_jobs
                SET status = 'failed', completed_at = $1, error_message = $2
                WHERE id = $3 AND status IN ('pending', 'running')
                """,
                completed_at,
                error_message,
                job_id,
            )
        finally:
            await conn.close()

        return "UPDATE 1" in result

    async def cancel(self, job_id: int) -> bool:
        """Cancel a pending job.

        Args:
            job_id: Job ID to cancel

        Returns:
            True if job was cancelled, False if not found or already running
        """
        conn = await asyncpg.connect(self._conn_string)
        try:
            result = await conn.execute(
                """
                UPDATE scheduled_jobs
                SET status = 'cancelled', completed_at = NOW()
                WHERE id = $1 AND status = 'pending'
                """,
                job_id,
            )
        finally:
            await conn.close()

        return "UPDATE 1" in result

    async def create_next_instance(
        self,
        parent_job: ScheduledJob,
        next_due_time: datetime,
    ) -> ScheduledJob | None:
        """Create the next instance of a recurring job.

        Args:
            parent_job: The completed job to create a follow-up for
            next_due_time: When the next instance should run

        Returns:
            New ScheduledJob instance, or None if parent wasn't recurring
        """
        if not parent_job.cron:
            return None

        return await self.create(
            user_id=parent_job.user_id,
            thread_id=parent_job.thread_id,
            task=parent_job.task,
            flow=parent_job.flow,
            due_time=next_due_time,
            worker_id=parent_job.worker_id,
            name=parent_job.name,
            cron=parent_job.cron,
        )

    @staticmethod
    def _row_to_job(row) -> ScheduledJob:
        """Convert database row to ScheduledJob object."""
        return ScheduledJob(
            id=row["id"],
            user_id=row["user_id"],
            thread_id=row["thread_id"],
            worker_id=row["worker_id"],
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
_job_storage: ScheduledJobStorage | None = None


async def get_scheduled_job_storage() -> ScheduledJobStorage:
    """Get or create scheduled job storage instance."""
    global _job_storage
    if _job_storage is None:
        _job_storage = ScheduledJobStorage()
    return _job_storage
