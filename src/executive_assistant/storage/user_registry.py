"""User registry for tracking ownership across threads, files, and database data."""

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import asyncpg
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    AIMessage,
    ToolMessage,
    SystemMessage,
)

from executive_assistant.config import settings


def sanitize_thread_id(thread_id: str) -> str:
    """
    Sanitize thread_id for use as filename/directory name.

    Replaces characters that could cause issues in filenames.

    Args:
        thread_id: Raw thread_id (e.g., "telegram:user123", "email:user@example.com")

    Returns:
        Sanitized string safe for filenames (e.g., "telegram_user123", "email_user_example.com")
    """
    replacements = {
        ":": "_",
        "/": "_",
        "@": "_",
        "\\": "_",
    }
    for old, new in replacements.items():
        thread_id = thread_id.replace(old, new)
    return thread_id


def _schedule_async(coro: Any) -> None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(coro)
        return
    loop.create_task(coro)

@dataclass
class MessageLog:
    """A logged message for audit purposes."""

    id: int
    conversation_id: str
    message_id: str | None
    role: str
    content: str
    metadata: dict[str, Any] | None
    created_at: datetime
    token_count: int | None


@dataclass
class ConversationLog:
    """A conversation log entry."""

    conversation_id: str
    channel: str
    created_at: datetime
    updated_at: datetime
    message_count: int
    status: str


@dataclass
class FilePath:
    """A file path ownership record."""

    thread_id: str
    channel: str
    created_at: datetime


@dataclass
class TDBPath:
    """A transactional database ownership record."""

    db_path: str
    thread_id: str
    channel: str
    created_at: datetime


class VDBPath:
    """A vector database ownership record."""

    vs_path: str
    thread_id: str
    channel: str
    created_at: datetime


class MemPath:
    """A memory DB ownership record."""

    mem_path: str
    thread_id: str
    channel: str
    created_at: datetime


class ADBPath:
    """An analytics DB ownership record."""

    adb_path: str
    thread_id: str
    channel: str
    created_at: datetime


class UserRegistry:
    """
    User registry for tracking ownership across all resources.

    Provides:
    - Message/conversation logging for audit
    - File path ownership tracking
    - Transactional database ownership tracking
    - Vector database ownership tracking
    """

    def __init__(self, conn_string: str | None = None):
        """
        Initialize user registry.

        Args:
            conn_string: PostgreSQL connection string. Defaults to settings.POSTGRES_URL.
        """
        self._conn_string = conn_string or settings.POSTGRES_URL

    def _get_role(self, message: BaseMessage) -> str:
        """Map message type to role."""
        if isinstance(message, HumanMessage):
            return "human"
        elif isinstance(message, AIMessage):
            return "assistant"
        elif isinstance(message, ToolMessage):
            return "tool"
        elif isinstance(message, SystemMessage):
            return "system"
        return "unknown"

    def _get_content(self, message: BaseMessage) -> str:
        """Extract content from message."""
        if isinstance(message, ToolMessage):
            return f"[{message.name}] {message.content}"
        return message.content or ""

    def _get_metadata(self, message: BaseMessage) -> dict[str, Any] | None:
        """Extract metadata from message."""
        metadata = {}

        if isinstance(message, AIMessage):
            if hasattr(message, "tool_calls") and message.tool_calls:
                metadata["tool_calls"] = message.tool_calls
            if hasattr(message, "response_metadata") and message.response_metadata:
                metadata["response_metadata"] = message.response_metadata
        elif isinstance(message, ToolMessage):
            metadata["tool_name"] = message.name
            metadata["tool_call_id"] = message.tool_call_id

        return metadata if metadata else None

    # ==================== Message Logging ====================

    async def log_message(
        self,
        conversation_id: str,
        channel: str,
        message: BaseMessage,
        message_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        """
        Store a message for audit/record keeping.

        Args:
            conversation_id: Thread/conversation identifier
            channel: Channel name (telegram, http, etc.)
            message: The message to log
            message_id: Channel-specific message ID
            metadata: Additional metadata

        Returns:
            The ID of the inserted message
        """
        role = self._get_role(message)
        content = self._get_content(message)
        message_metadata = self._get_metadata(message)

        # Merge provided metadata with extracted metadata
        if metadata:
            message_metadata = {**(message_metadata or {}), **metadata}

        # Estimate token count (rough approximation: ~4 chars per token)
        # This is adequate for cost tracking without requiring tiktoken
        token_count = int(len(content) / 4) if content else 0

        # Add metadata JSON size to token count
        if message_metadata:
            metadata_json = json.dumps(message_metadata)
            token_count += int(len(metadata_json) / 4)

        conn = await asyncpg.connect(self._conn_string)
        try:
            async with conn.transaction():
                # Ensure conversation exists
                await conn.execute(
                    """INSERT INTO conversations (conversation_id, channel)
                       VALUES ($1, $2)
                       ON CONFLICT (conversation_id) DO NOTHING""",
                    conversation_id, channel
                )

                # Insert message (trigger handles conversation update)
                msg_id = await conn.fetchval(
                    """INSERT INTO messages (conversation_id, message_id, role, content, metadata, token_count)
                       VALUES ($1, $2, $3, $4, $5, $6)
                       RETURNING id""",
                    conversation_id, message_id, role, content,
                    json.dumps(message_metadata) if message_metadata else None,
                    token_count
                )

                return msg_id
        finally:
            await conn.close()

    async def get_conversation_history(
        self,
        conversation_id: str,
        limit: int = 100,
    ) -> list[MessageLog]:
        """
        Get conversation history for audit/export.

        Args:
            conversation_id: Thread/conversation identifier
            limit: Maximum number of messages to return

        Returns:
            List of message logs in chronological order
        """
        conn = await asyncpg.connect(self._conn_string)
        try:
            rows = await conn.fetch(
                """SELECT id, conversation_id, message_id, role, content, metadata, created_at, token_count
                   FROM messages
                   WHERE conversation_id = $1
                   ORDER BY created_at ASC
                   LIMIT $2""",
                conversation_id, limit
            )

            return [
                MessageLog(
                    id=row["id"],
                    conversation_id=row["conversation_id"],
                    message_id=row["message_id"],
                    role=row["role"],
                    content=row["content"],
                    metadata=row["metadata"],
                    created_at=row["created_at"],
                    token_count=row["token_count"],
                )
                for row in rows
            ]
        finally:
            await conn.close()

    async def get_conversation(self, conversation_id: str) -> ConversationLog | None:
        """
        Get conversation metadata.

        Args:
            conversation_id: Thread/conversation identifier

        Returns:
            Conversation log or None if not found
        """
        conn = await asyncpg.connect(self._conn_string)
        try:
            row = await conn.fetchrow(
                """SELECT conversation_id, channel, created_at, updated_at,
                          message_count, status
                   FROM conversations
                   WHERE conversation_id = $1""",
                conversation_id,
            )

            if not row:
                return None

            return ConversationLog(
                conversation_id=row["conversation_id"],
                channel=row["channel"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                message_count=row["message_count"],
                status=row["status"],
            )
        finally:
            await conn.close()

    # ==================== File Path Tracking ====================

    async def register_file_path(
        self,
        thread_id: str,
        channel: str,
        file_path: str,
    ) -> None:
        """
        Register a file path for a thread (ownership tracking).

        Args:
            thread_id: Thread identifier
            channel: Channel name
            file_path: Path to the file/directory
        """
        conn = await asyncpg.connect(self._conn_string)
        try:
            await conn.execute(
                """INSERT INTO file_paths (thread_id, channel)
                   VALUES ($1, $2)
                   ON CONFLICT (thread_id) DO UPDATE SET channel = EXCLUDED.channel""",
                thread_id, channel
            )
        finally:
            await conn.close()

    async def get_file_path(self, thread_id: str) -> FilePath | None:
        """
        Get file path info for a thread.

        Args:
            thread_id: Thread identifier

        Returns:
            FilePath record or None
        """
        conn = await asyncpg.connect(self._conn_string)
        try:
            row = await conn.fetchrow(
                """SELECT thread_id, channel, created_at
                   FROM file_paths
                   WHERE thread_id = $1""",
                thread_id,
            )

            if not row:
                return None

            return FilePath(
                thread_id=row["thread_id"],
                channel=row["channel"],
                created_at=row["created_at"],
            )
        finally:
            await conn.close()

    # ==================== Transactional Database Path Tracking ====================

    async def register_tdb_path(
        self,
        thread_id: str,
        channel: str,
        tdb_path: str,
    ) -> None:
        """
        Register a transactional database for a thread (ownership tracking).

        Args:
            thread_id: Thread identifier
            channel: Channel name
            tdb_path: Path to the transactional database file
        """
        conn = await asyncpg.connect(self._conn_string)
        try:
            await conn.execute(
                """INSERT INTO tdb_paths (tdb_path, thread_id, channel)
                   VALUES ($1, $2, $3)
                   ON CONFLICT (thread_id) DO UPDATE SET tdb_path = EXCLUDED.tdb_path""",
                tdb_path, thread_id, channel
            )
        except asyncpg.UndefinedTableError:
            return
        finally:
            await conn.close()

    async def get_tdb_path(self, thread_id: str) -> TDBPath | None:
        """
        Get transactional database path info for a thread.

        Args:
            thread_id: Thread identifier

        Returns:
            TDBPath record or None
        """
        conn = await asyncpg.connect(self._conn_string)
        try:
            row = await conn.fetchrow(
                """SELECT tdb_path, thread_id, channel, created_at
                   FROM tdb_paths
                   WHERE thread_id = $1""",
                thread_id,
            )

            if not row:
                return None

            return TDBPath(
                tdb_path=row["tdb_path"],
                thread_id=row["thread_id"],
                channel=row["channel"],
                created_at=row["created_at"],
            )
        finally:
            await conn.close()

    # ==================== Vector Database Path Tracking ====================

    async def register_vdb_path(self, thread_id: str, channel: str, vdb_path: str) -> None:
        conn = await asyncpg.connect(self._conn_string)
        try:
            await conn.execute(
                """INSERT INTO vdb_paths (vdb_path, thread_id, channel)
                   VALUES ($1, $2, $3)
                   ON CONFLICT (thread_id) DO UPDATE SET vdb_path = EXCLUDED.vdb_path""",
                vdb_path, thread_id, channel
            )
        except asyncpg.UndefinedTableError:
            return
        finally:
            await conn.close()

    async def register_mem_path(self, thread_id: str, channel: str, mem_path: str) -> None:
        conn = await asyncpg.connect(self._conn_string)
        try:
            await conn.execute(
                """INSERT INTO mem_paths (mem_path, thread_id, channel)
                   VALUES ($1, $2, $3)
                   ON CONFLICT (thread_id) DO UPDATE SET mem_path = EXCLUDED.mem_path""",
                mem_path, thread_id, channel
            )
        except asyncpg.UndefinedTableError:
            return
        finally:
            await conn.close()

    async def register_adb_path(self, thread_id: str, channel: str, adb_path: str) -> None:
        conn = await asyncpg.connect(self._conn_string)
        try:
            await conn.execute(
                """INSERT INTO adb_paths (adb_path, thread_id, channel)
                   VALUES ($1, $2, $3)
                   ON CONFLICT (thread_id) DO UPDATE SET adb_path = EXCLUDED.adb_path""",
                adb_path, thread_id, channel
            )
        except asyncpg.UndefinedTableError:
            return
        finally:
            await conn.close()

    # ==================== Query Operations ====================

    async def get_message_count(
        self,
        channel: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> int:
        """
        Get message count with optional filters.

        Args:
            channel: Filter by channel
            start_date: Filter messages after this date
            end_date: Filter messages before this date

        Returns:
            Number of messages matching the criteria
        """
        conditions = []
        params = []
        param_count = 0

        if channel:
            param_count += 1
            conditions.append(f"c.channel = ${param_count}")
            params.append(channel)

        if start_date:
            param_count += 1
            conditions.append(f"m.created_at >= ${param_count}")
            params.append(start_date)

        if end_date:
            param_count += 1
            conditions.append(f"m.created_at <= ${param_count}")
            params.append(end_date)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        conn = await asyncpg.connect(self._conn_string)
        try:
            return await conn.fetchval(
                f"""SELECT COUNT(*)
                   FROM messages m
                   JOIN conversations c ON m.conversation_id = c.conversation_id
                   WHERE {where_clause}""",
                *params
            )
        finally:
            await conn.close()

def register_vdb_path_best_effort(thread_id: str | None, channel: str, vdb_path: str) -> None:
    if not thread_id:
        return
    registry = UserRegistry()
    _schedule_async(registry.register_vdb_path(thread_id, channel, vdb_path))

def register_mem_path_best_effort(thread_id: str | None, channel: str, mem_path: str) -> None:
    if not thread_id:
        return
    registry = UserRegistry()
    _schedule_async(registry.register_mem_path(thread_id, channel, mem_path))

def register_adb_path_best_effort(thread_id: str | None, channel: str, adb_path: str) -> None:
    if not thread_id:
        return
    registry = UserRegistry()
    _schedule_async(registry.register_adb_path(thread_id, channel, adb_path))

def register_file_path_best_effort(thread_id: str | None, channel: str, file_path: str) -> None:
    if not thread_id:
        return
    registry = UserRegistry()
    _schedule_async(registry.register_file_path(thread_id, channel, file_path))

def register_tdb_path_best_effort(thread_id: str | None, channel: str, tdb_path: str) -> None:
    if not thread_id:
        return
    registry = UserRegistry()
    _schedule_async(registry.register_tdb_path(thread_id, channel, tdb_path))
