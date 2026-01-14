"""Reminder storage and management."""

import asyncpg
from dataclasses import dataclass
from datetime import datetime

from cassey.config.settings import settings


@dataclass
class Reminder:
    """A reminder record."""

    id: int
    user_id: str
    thread_ids: list[str]
    message: str
    due_time: datetime
    status: str  # pending, sent, cancelled, failed
    recurrence: str | None
    created_at: datetime
    sent_at: datetime | None
    error_message: str | None

    @property
    def is_pending(self) -> bool:
        """Check if reminder is still pending."""
        return self.status == "pending"

    @property
    def is_recurring(self) -> bool:
        """Check if reminder has recurrence."""
        return self.recurrence is not None and self.recurrence != ""


class ReminderStorage:
    """Storage for reminders in PostgreSQL."""

    def __init__(self, conn_string: str | None = None) -> None:
        """Initialize reminder storage."""
        self._conn_string = conn_string or settings.POSTGRES_URL

    async def create(
        self,
        user_id: str,
        thread_ids: list[str],
        message: str,
        due_time: datetime,
        recurrence: str | None = None,
    ) -> Reminder:
        """Create a new reminder."""
        conn = await asyncpg.connect(self._conn_string)
        try:
            row = await conn.fetchrow(
                """
                INSERT INTO reminders (user_id, thread_ids, message, due_time, recurrence)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING *
                """,
                user_id,
                thread_ids,
                message,
                due_time,
                recurrence,
            )
        finally:
            await conn.close()

        return self._row_to_reminder(row)

    async def get_by_id(self, reminder_id: int) -> Reminder | None:
        """Get reminder by ID."""
        conn = await asyncpg.connect(self._conn_string)
        try:
            row = await conn.fetchrow(
                "SELECT * FROM reminders WHERE id = $1",
                reminder_id,
            )
        finally:
            await conn.close()

        return self._row_to_reminder(row) if row else None

    async def get_pending_reminders(self, before: datetime) -> list[Reminder]:
        """Get all pending reminders due before the given time."""
        conn = await asyncpg.connect(self._conn_string)
        try:
            rows = await conn.fetch(
                """
                SELECT * FROM reminders
                WHERE status = 'pending' AND due_time <= $1
                ORDER BY due_time ASC
                """,
                before,
            )
        finally:
            await conn.close()

        return [self._row_to_reminder(row) for row in rows]

    async def list_by_user(
        self, user_id: str, status: str | None = None
    ) -> list[Reminder]:
        """List all reminders for a user, optionally filtered by status."""
        conn = await asyncpg.connect(self._conn_string)
        try:
            if status:
                rows = await conn.fetch(
                    """
                    SELECT * FROM reminders
                    WHERE user_id = $1 AND status = $2
                    ORDER BY due_time ASC
                    """,
                    user_id,
                    status,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT * FROM reminders
                    WHERE user_id = $1
                    ORDER BY due_time ASC
                    """,
                    user_id,
                )
        finally:
            await conn.close()

        return [self._row_to_reminder(row) for row in rows]

    async def mark_sent(self, reminder_id: int, sent_at: datetime | None = None) -> bool:
        """Mark reminder as sent."""
        if sent_at is None:
            sent_at = datetime.now()

        conn = await asyncpg.connect(self._conn_string)
        try:
            result = await conn.execute(
                """
                UPDATE reminders
                SET status = 'sent', sent_at = $1
                WHERE id = $2 AND status = 'pending'
                """,
                sent_at,
                reminder_id,
            )
        finally:
            await conn.close()

        return "UPDATE 1" in result

    async def mark_failed(
        self, reminder_id: int, error_message: str
    ) -> bool:
        """Mark reminder as failed."""
        conn = await asyncpg.connect(self._conn_string)
        try:
            result = await conn.execute(
                """
                UPDATE reminders
                SET status = 'failed', error_message = $1
                WHERE id = $2 AND status = 'pending'
                """,
                error_message,
                reminder_id,
            )
        finally:
            await conn.close()

        return "UPDATE 1" in result

    async def cancel(self, reminder_id: int) -> bool:
        """Cancel a pending reminder."""
        conn = await asyncpg.connect(self._conn_string)
        try:
            result = await conn.execute(
                """
                UPDATE reminders
                SET status = 'cancelled'
                WHERE id = $1 AND status = 'pending'
                """,
                reminder_id,
            )
        finally:
            await conn.close()

        return "UPDATE 1" in result

    async def update(
        self,
        reminder_id: int,
        message: str | None = None,
        due_time: datetime | None = None,
        recurrence: str | None = None,
    ) -> Reminder | None:
        """Update reminder fields."""
        updates = []
        params = []
        param_count = 1

        if message is not None:
            updates.append(f"message = ${param_count}")
            params.append(message)
            param_count += 1

        if due_time is not None:
            updates.append(f"due_time = ${param_count}")
            params.append(due_time)
            param_count += 1

        if recurrence is not None:
            updates.append(f"recurrence = ${param_count}")
            params.append(recurrence)
            param_count += 1

        if not updates:
            return await self.get_by_id(reminder_id)

        params.append(reminder_id)

        conn = await asyncpg.connect(self._conn_string)
        try:
            row = await conn.fetchrow(
                f"""
                UPDATE reminders
                SET {', '.join(updates)}
                WHERE id = ${param_count}
                RETURNING *
                """,
                *params,
            )
        finally:
            await conn.close()

        return self._row_to_reminder(row) if row else None

    @staticmethod
    def _row_to_reminder(row) -> Reminder:
        """Convert database row to Reminder object."""
        return Reminder(
            id=row["id"],
            user_id=row["user_id"],
            thread_ids=list(row["thread_ids"]) if row["thread_ids"] else [],
            message=row["message"],
            due_time=row["due_time"],
            status=row["status"],
            recurrence=row["recurrence"],
            created_at=row["created_at"],
            sent_at=row["sent_at"],
            error_message=row["error_message"],
        )


async def get_reminder_storage() -> ReminderStorage:
    """Get or create reminder storage instance."""
    return ReminderStorage()
