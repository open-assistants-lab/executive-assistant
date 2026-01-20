"""User registry for tracking ownership across threads, files, and database data."""

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
    user_id: str | None
    channel: str
    created_at: datetime
    updated_at: datetime
    message_count: int
    status: str


@dataclass
class FilePath:
    """A file path ownership record."""

    thread_id: str
    user_id: str | None
    channel: str
    created_at: datetime


@dataclass
class DBPath:
    """A database ownership record."""

    db_path: str
    thread_id: str
    user_id: str | None
    channel: str
    created_at: datetime


class UserRegistry:
    """
    User registry for tracking ownership across all resources.

    Provides:
    - Message/conversation logging for audit
    - File path ownership tracking
    - Database ownership tracking
    - Merge operations (link threads to user)
    - Remove operations (unlink threads)
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
        user_id: str,
        channel: str,
        message: BaseMessage,
        message_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        """
        Store a message for audit/record keeping.

        Args:
            conversation_id: Thread/conversation identifier
            user_id: User identifier
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
                    """INSERT INTO conversations (conversation_id, user_id, channel)
                       VALUES ($1, $2, $3)
                       ON CONFLICT (conversation_id) DO NOTHING""",
                    conversation_id, user_id, channel
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

    async def get_user_conversations(
        self,
        user_id: str,
        limit: int = 50,
    ) -> list[ConversationLog]:
        """
        Get all conversations for a user.

        Args:
            user_id: User identifier
            limit: Maximum number of conversations to return

        Returns:
            List of conversation logs
        """
        conn = await asyncpg.connect(self._conn_string)
        try:
            rows = await conn.fetch(
                """SELECT conversation_id, user_id, channel, created_at, updated_at,
                          message_count, status
                   FROM conversations
                   WHERE user_id = $1
                   ORDER BY updated_at DESC
                   LIMIT $2""",
                user_id, limit
            )

            return [
                ConversationLog(
                    conversation_id=row["conversation_id"],
                    user_id=row["user_id"],
                    channel=row["channel"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    message_count=row["message_count"],
                    status=row["status"],
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
                """SELECT conversation_id, user_id, channel, created_at, updated_at,
                          message_count, status
                   FROM conversations
                   WHERE conversation_id = $1""",
                conversation_id,
            )

            if not row:
                return None

            return ConversationLog(
                conversation_id=row["conversation_id"],
                user_id=row["user_id"],
                channel=row["channel"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                message_count=row["message_count"],
                status=row["status"],
            )
        finally:
            await conn.close()

    async def update_structured_summary(
        self,
        conversation_id: str,
        structured_summary: dict[str, Any],
    ) -> None:
        """
        Update the structured summary (JSONB) for a conversation.

        Args:
            conversation_id: Thread/conversation identifier
            structured_summary: The structured summary dict
        """
        conn = await asyncpg.connect(self._conn_string)
        try:
            await conn.execute(
                """UPDATE conversations
                   SET structured_summary = $2::jsonb
                   WHERE conversation_id = $1""",
                conversation_id, json.dumps(structured_summary)
            )
        finally:
            await conn.close()

    async def update_active_request(
        self,
        conversation_id: str,
        active_request: str,
    ) -> None:
        """
        Update the active request (intent-first) for a conversation.

        Args:
            conversation_id: Thread/conversation identifier
            active_request: The current user request text
        """
        conn = await asyncpg.connect(self._conn_string)
        try:
            await conn.execute(
                """UPDATE conversations
                   SET active_request = $2
                   WHERE conversation_id = $1""",
                conversation_id, active_request
            )
        finally:
            await conn.close()

    async def get_structured_summary(
        self,
        conversation_id: str,
    ) -> dict[str, Any] | None:
        """
        Get the structured summary for a conversation.

        Args:
            conversation_id: Thread/conversation identifier

        Returns:
            Structured summary dict or None
        """
        conn = await asyncpg.connect(self._conn_string)
        try:
            row = await conn.fetchrow(
                """SELECT structured_summary
                   FROM conversations
                   WHERE conversation_id = $1""",
                conversation_id,
            )

            if not row or not row.get("structured_summary"):
                return None

            return row["structured_summary"]
        finally:
            await conn.close()

    # ==================== Identity Management ====================

    async def create_identity_if_not_exists(
        self,
        thread_id: str,
        identity_id: str,
        channel: str,
    ) -> bool:
        """
        Create identity record if it doesn't exist.

        Args:
            thread_id: Thread identifier
            identity_id: Auto-generated identity ID (anon_*)
            channel: Channel type ('telegram', 'email', 'http')

        Returns:
            True if created, False if already existed
        """
        conn = await asyncpg.connect(self._conn_string)
        try:
            await conn.execute(
                """INSERT INTO identities (identity_id, thread_id, channel)
                   VALUES ($1, $2, $3)
                   ON CONFLICT (thread_id) DO NOTHING""",
                identity_id, thread_id, channel
            )
            return True
        except Exception:
            return False
        finally:
            await conn.close()

    async def get_identity_by_thread_id(
        self,
        thread_id: str,
    ) -> dict | None:
        """
        Get identity by thread_id.

        Args:
            thread_id: Thread identifier

        Returns:
            Identity dict or None if not found
        """
        conn = await asyncpg.connect(self._conn_string)
        try:
            row = await conn.fetchrow(
                """SELECT * FROM identities WHERE thread_id = $1""",
                thread_id
            )

            if not row:
                return None

            return dict(row)
        finally:
            await conn.close()

    async def get_persistent_user_id(
        self,
        thread_id: str,
    ) -> str | None:
        """
        Get persistent user_id for a thread_id.

        Returns persistent_user_id if verified, otherwise returns identity_id.

        Args:
            thread_id: Thread identifier

        Returns:
            user_id string or None if not found
        """
        identity = await self.get_identity_by_thread_id(thread_id)
        if not identity:
            return None

        # Return persistent_user_id if verified, else identity_id (anon_*)
        return identity.get("persistent_user_id") or identity.get("identity_id")

    async def update_identity_merge(
        self,
        identity_id: str,
        persistent_user_id: str,
        verification_status: str = "verified",
    ) -> None:
        """
        Update identity after merge.

        Args:
            identity_id: Identity ID to update
            persistent_user_id: New persistent user ID
            verification_status: New verification status
        """
        conn = await asyncpg.connect(self._conn_string)
        try:
            await conn.execute(
                """UPDATE identities
                   SET persistent_user_id = $1,
                       verification_status = $2,
                       merged_at = NOW()
                   WHERE identity_id = $3""",
                persistent_user_id, verification_status, identity_id
            )
        finally:
            await conn.close()

    async def update_identity_pending(
        self,
        thread_id: str,
        verification_method: str,
        verification_contact: str,
    ) -> None:
        """
        Update identity to pending verification status.

        Args:
            thread_id: Thread identifier
            verification_method: Method ('email', 'phone', etc.)
            verification_contact: Contact info (email, phone)
        """
        conn = await asyncpg.connect(self._conn_string)
        try:
            await conn.execute(
                """UPDATE identities
                   SET verification_status = 'pending',
                       verification_method = $1,
                       verification_contact = $2
                   WHERE thread_id = $3""",
                verification_method, verification_contact, thread_id
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
                """SELECT thread_id, user_id, channel, created_at
                   FROM file_paths
                   WHERE thread_id = $1""",
                thread_id,
            )

            if not row:
                return None

            return FilePath(
                thread_id=row["thread_id"],
                user_id=row["user_id"],
                channel=row["channel"],
                created_at=row["created_at"],
            )
        finally:
            await conn.close()

    # ==================== Database Path Tracking ====================

    async def register_db_path(
        self,
        thread_id: str,
        channel: str,
        db_path: str,
    ) -> None:
        """
        Register a database for a thread (ownership tracking).

        Args:
            thread_id: Thread identifier
            channel: Channel name
            db_path: Path to the database file
        """
        conn = await asyncpg.connect(self._conn_string)
        try:
            await conn.execute(
                """INSERT INTO db_paths (db_path, thread_id, channel)
                   VALUES ($1, $2, $3)
                   ON CONFLICT (thread_id) DO UPDATE SET db_path = EXCLUDED.db_path""",
                db_path, thread_id, channel
            )
        finally:
            await conn.close()

    async def get_db_path(self, thread_id: str) -> DBPath | None:
        """
        Get database path info for a thread.

        Args:
            thread_id: Thread identifier

        Returns:
            DBPath record or None
        """
        conn = await asyncpg.connect(self._conn_string)
        try:
            row = await conn.fetchrow(
                """SELECT db_path, thread_id, user_id, channel, created_at
                   FROM db_paths
                   WHERE thread_id = $1""",
                thread_id,
            )

            if not row:
                return None

            return DBPath(
                db_path=row["db_path"],
                thread_id=row["thread_id"],
                user_id=row["user_id"],
                channel=row["channel"],
                created_at=row["created_at"],
            )
        finally:
            await conn.close()

    # ==================== Merge Operations ====================

    async def merge_threads(
        self,
        source_thread_ids: list[str],
        target_user_id: str,
    ) -> dict[str, Any]:
        """
        Merge multiple threads into a single user (ownership merge only).

        This updates ownership records but does NOT migrate checkpoint state.
        Conversations remain separate in LangGraph checkpoints.

        Args:
            source_thread_ids: List of thread IDs to merge
            target_user_id: Target user ID for merged ownership

        Returns:
            Summary of merge operation
        """
        conn = await asyncpg.connect(self._conn_string)
        try:
            async with conn.transaction():
                # Log the merge operation to user_registry table
                op_id = await conn.fetchval(
                    """INSERT INTO user_registry (operation_type, source_thread_ids, target_user_id, status)
                       VALUES ($1, $2, $3, 'in_progress')
                       RETURNING id""",
                    "merge", source_thread_ids, target_user_id
                )

                # Update conversations
                conv_result = await conn.execute(
                    """UPDATE conversations
                       SET user_id = $1, updated_at = NOW()
                       WHERE conversation_id = ANY($2)""",
                    target_user_id, source_thread_ids
                )

                # Update file_paths
                file_result = await conn.execute(
                    """UPDATE file_paths
                       SET user_id = $1
                       WHERE thread_id = ANY($2)""",
                    target_user_id, source_thread_ids
                )

                # Update db_paths
                db_result = await conn.execute(
                    """UPDATE db_paths
                       SET user_id = $1
                       WHERE thread_id = ANY($2)""",
                    target_user_id, source_thread_ids
                )

                # Parse counts from results
                conv_count = int(conv_result.split()[-1]) if conv_result else 0
                file_count = int(file_result.split()[-1]) if file_result else 0
                db_count = int(db_result.split()[-1]) if db_result else 0

                # Mark operation as completed
                await conn.execute(
                    """UPDATE user_registry
                       SET status = 'completed', completed_at = NOW()
                       WHERE id = $1""",
                    op_id
                )

                return {
                    "operation_id": op_id,
                    "target_user_id": target_user_id,
                    "source_thread_ids": source_thread_ids,
                    "conversations_updated": conv_count,
                    "file_paths_updated": file_count,
                    "db_paths_updated": db_count,
                }
        except Exception as e:
            # Mark operation as failed
            try:
                await conn.execute(
                    """UPDATE user_registry
                       SET status = 'failed', error_message = $1, completed_at = NOW()
                       WHERE id = (SELECT id FROM user_registry ORDER BY created_at DESC LIMIT 1)""",
                    str(e)
                )
            except Exception:
                pass
            raise
        finally:
            await conn.close()

    async def remove_thread(self, thread_id: str) -> dict[str, Any]:
        """
        Remove a thread (unlink from user, mark as removed).

        This removes ownership records but keeps audit history.

        Args:
            thread_id: Thread ID to remove

        Returns:
            Summary of removal operation
        """
        conn = await asyncpg.connect(self._conn_string)
        try:
            async with conn.transaction():
                # Log the remove operation to user_registry table
                op_id = await conn.fetchval(
                    """INSERT INTO user_registry (operation_type, source_thread_ids, status)
                       VALUES ($1, $2, 'in_progress')
                       RETURNING id""",
                    "remove", [thread_id]
                )

                # Update conversation status
                conv_result = await conn.execute(
                    """UPDATE conversations
                       SET status = 'removed', user_id = NULL, updated_at = NOW()
                       WHERE conversation_id = $1""",
                    thread_id
                )

                # Remove from file_paths
                file_result = await conn.execute(
                    """DELETE FROM file_paths
                       WHERE thread_id = $1""",
                    thread_id
                )

                # Remove from db_paths
                db_result = await conn.execute(
                    """DELETE FROM db_paths
                       WHERE thread_id = $1""",
                    thread_id
                )

                # Mark operation as completed
                await conn.execute(
                    """UPDATE user_registry
                       SET status = 'completed', completed_at = NOW()
                       WHERE id = $1""",
                    op_id
                )

                return {
                    "operation_id": op_id,
                    "thread_id": thread_id,
                    "conversations_updated": int(conv_result.split()[-1]) if conv_result else 0,
                    "file_paths_deleted": int(file_result.split()[-1]) if file_result else 0,
                    "db_paths_deleted": int(db_result.split()[-1]) if db_result else 0,
                }
        except Exception as e:
            # Mark operation as failed
            try:
                await conn.execute(
                    """UPDATE user_registry
                       SET status = 'failed', error_message = $1, completed_at = NOW()
                       WHERE id = (SELECT id FROM user_registry ORDER BY created_at DESC LIMIT 1)""",
                    str(e)
                )
            except Exception:
                pass
            raise
        finally:
            await conn.close()

    # ==================== Query Operations ====================

    async def get_message_count(
        self,
        user_id: str | None = None,
        channel: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> int:
        """
        Get message count with optional filters.

        Args:
            user_id: Filter by user ID
            channel: Filter by channel
            start_date: Filter messages after this date
            end_date: Filter messages before this date

        Returns:
            Number of messages matching the criteria
        """
        conditions = []
        params = []
        param_count = 0

        if user_id:
            param_count += 1
            conditions.append(f"c.user_id = ${param_count}")
            params.append(user_id)

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

    async def get_user_files(self, user_id: str) -> list[FilePath]:
        """
        Get all file paths owned by a user.

        Args:
            user_id: User identifier

        Returns:
            List of FilePath records
        """
        conn = await asyncpg.connect(self._conn_string)
        try:
            rows = await conn.fetch(
                """SELECT thread_id, user_id, channel, created_at
                   FROM file_paths
                   WHERE user_id = $1
                   ORDER BY created_at DESC""",
                user_id
            )

            return [
                FilePath(
                    thread_id=row["thread_id"],
                    user_id=row["user_id"],
                    channel=row["channel"],
                    created_at=row["created_at"],
                )
                for row in rows
            ]
        finally:
            await conn.close()

    async def get_user_dbs(self, user_id: str) -> list[DBPath]:
        """
        Get all databases owned by a user.

        Args:
            user_id: User identifier

        Returns:
            List of DBPath records
        """
        conn = await asyncpg.connect(self._conn_string)
        try:
            rows = await conn.fetch(
                """SELECT db_path, thread_id, user_id, channel, created_at
                   FROM db_paths
                   WHERE user_id = $1
                   ORDER BY created_at DESC""",
                user_id
            )

            return [
                DBPath(
                    db_path=row["db_path"],
                    thread_id=row["thread_id"],
                    user_id=row["user_id"],
                    channel=row["channel"],
                    created_at=row["created_at"],
                )
                for row in rows
            ]
        finally:
            await conn.close()
