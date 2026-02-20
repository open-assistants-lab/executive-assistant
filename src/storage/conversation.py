"""Conversation storage - messages and journal for long-term memory."""

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import duckdb

from src.config import get_settings


@dataclass
class Message:
    """A single message in the conversation."""

    ts: datetime
    role: str  # "user" or "assistant"
    content: str
    metadata: dict | None = None


@dataclass
class JournalEntry:
    """Daily journal entry (summary)."""

    date: date
    summary: str
    msg_count: int
    metadata: dict | None = None


class ConversationStore:
    """Manages long-term conversation storage (messages + journal).

    Structure:
        /data/users/{user_id}/.conversation/
        ├── messages.duckdb  # Raw messages (all time)
        └── journal.duckdb   # Daily summaries
    """

    def __init__(self, user_id: str):
        self.user_id = user_id
        settings = get_settings()
        config = settings.memory

        base_path = Path(config.messages.path.format(user_id=user_id)).parent
        base_path.mkdir(parents=True, exist_ok=True)

        self.messages_db_path = str((base_path / "messages.duckdb").resolve())
        self.journal_db_path = str((base_path / "journal.duckdb").resolve())

        self._init_messages_db()
        self._init_journal_db()

    def _init_messages_db(self):
        """Initialize messages DuckDB."""
        conn = duckdb.connect(self.messages_db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                ts TIMESTAMP,
                role VARCHAR,
                content TEXT,
                metadata JSON
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ts ON messages(ts)")
        conn.close()

    def _init_journal_db(self):
        """Initialize journal DuckDB."""
        conn = duckdb.connect(self.journal_db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS journal (
                date DATE PRIMARY KEY,
                summary TEXT,
                msg_count INTEGER,
                metadata JSON
            )
        """)
        conn.close()

    def add_message(self, role: str, content: str, metadata: dict | None = None):
        """Add a message to the conversation."""
        conn = duckdb.connect(self.messages_db_path)
        conn.execute(
            "INSERT INTO messages VALUES (?, ?, ?, ?)",
            [datetime.now(), role, content, metadata],
        )
        conn.close()

    def get_messages(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int | None = None,
    ) -> list[Message]:
        """Get messages within a date range."""
        conn = duckdb.connect(self.messages_db_path)

        query = "SELECT ts, role, content, metadata FROM messages"
        params = []

        if start_date or end_date:
            query += " WHERE "
            conditions = []
            if start_date:
                conditions.append("ts >= ?")
                params.append(datetime.combine(start_date, datetime.min.time()))
            if end_date:
                conditions.append("ts <= ?")
                params.append(datetime.combine(end_date, datetime.max.time()))
            query += " AND ".join(conditions)

        query += " ORDER BY ts ASC"

        if limit:
            query += f" LIMIT {limit}"

        result = conn.execute(query, params).fetchall()
        conn.close()

        return [
            Message(
                ts=row[0],
                role=row[1],
                content=row[2],
                metadata=row[3],
            )
            for row in result
        ]

    def get_recent_messages(self, count: int = 100) -> list[Message]:
        """Get N most recent messages."""
        conn = duckdb.connect(self.messages_db_path)
        result = conn.execute(
            "SELECT ts, role, content, metadata FROM messages ORDER BY ts DESC LIMIT ?",
            [count],
        ).fetchall()
        conn.close()

        messages = [
            Message(
                ts=row[0],
                role=row[1],
                content=row[2],
                metadata=row[3],
            )
            for row in result
        ]
        return list(reversed(messages))

    def add_journal(self, summary: str, msg_count: int, metadata: dict | None = None):
        """Add a daily journal entry."""
        conn = duckdb.connect(self.journal_db_path)
        today = date.today()

        conn.execute(
            """
            INSERT OR REPLACE INTO journal (date, summary, msg_count, metadata)
            VALUES (?, ?, ?, ?)
            """,
            [today, summary, msg_count, metadata],
        )
        conn.close()

    def get_journal(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[JournalEntry]:
        """Get journal entries within a date range."""
        conn = duckdb.connect(self.journal_db_path)

        query = "SELECT date, summary, msg_count, metadata FROM journal"
        params = []

        if start_date or end_date:
            query += " WHERE "
            conditions = []
            if start_date:
                conditions.append("date >= ?")
                params.append(start_date)
            if end_date:
                conditions.append("date <= ?")
                params.append(end_date)
            query += " AND ".join(conditions)

        query += " ORDER BY date DESC"

        result = conn.execute(query, params).fetchall()
        conn.close()

        return [
            JournalEntry(
                date=row[0],
                summary=row[1],
                msg_count=row[2],
                metadata=row[3],
            )
            for row in result
        ]

    def get_recent_journal(self, days: int = 7) -> list[JournalEntry]:
        """Get journal entries for last N days."""
        start = date.today()
        from datetime import timedelta

        return self.get_journal(start_date=start - timedelta(days=days))

    def count_messages(self, start_date: date | None = None, end_date: date | None = None) -> int:
        """Count messages in a date range."""
        conn = duckdb.connect(self.messages_db_path)

        query = "SELECT COUNT(*) FROM messages"
        params = []

        if start_date or end_date:
            query += " WHERE "
            conditions = []
            if start_date:
                conditions.append("ts >= ?")
                params.append(datetime.combine(start_date, datetime.min.time()))
            if end_date:
                conditions.append("ts <= ?")
                params.append(datetime.combine(end_date, datetime.max.time()))
            query += " AND ".join(conditions)

        result = conn.execute(query, params).fetchone()
        conn.close()

        return result[0] if result else 0


# Singleton per user
_stores: dict[str, ConversationStore] = {}


def get_conversation_store(user_id: str = "default") -> ConversationStore:
    """Get conversation store for a user."""
    if user_id not in _stores:
        _stores[user_id] = ConversationStore(user_id)
    return _stores[user_id]
