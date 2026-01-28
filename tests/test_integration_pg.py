"""PostgreSQL integration tests.

These tests require a real PostgreSQL connection and will be skipped
unless the --run-postgres flag is provided.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
import asyncpg

from executive_assistant.config import settings


# =============================================================================
# Connection Tests
# =============================================================================

@pytest.mark.postgres
class TestPostgresConnection:
    """Test database connection and basic operations."""

    @pytest.mark.asyncio
    async def test_connect_to_database(self):
        """Test that we can connect to PostgreSQL."""
        conn = await asyncpg.connect(settings.POSTGRES_URL)
        try:
            # Simple query to verify connection
            result = await conn.fetchval("SELECT 1")
            assert result == 1
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_database_version(self, db_conn):
        """Test getting database version."""
        version = await db_conn.fetchval("SELECT version()")
        assert version is not None
        assert "PostgreSQL" in version


# =============================================================================
# Schema Tests
# =============================================================================

@pytest.mark.postgres
class TestDatabaseSchema:
    """Test that database schema is properly set up."""

    @pytest.mark.asyncio
    async def test_checkpoints_table_exists(self, db_conn):
        """Test that checkpoints table exists (LangGraph)."""
        # Check if table exists
        result = await db_conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'checkpoints'
            )
        """)
        assert result is True

    @pytest.mark.asyncio
    async def test_conversations_table_exists(self, db_conn):
        """Test that conversations table exists."""
        result = await db_conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'conversations'
            )
        """)
        assert result is True

    @pytest.mark.asyncio
    async def test_messages_table_exists(self, db_conn):
        """Test that messages table exists."""
        result = await db_conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'messages'
            )
        """)
        assert result is True

    @pytest.mark.asyncio
    async def test_scheduled_flows_table_exists(self, db_conn):
        """Test that scheduled_flows table exists."""
        result = await db_conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'scheduled_flows'
            )
        """)
        assert result is True

    @pytest.mark.asyncio
    async def test_reminders_table_exists(self, db_conn):
        """Test that reminders table exists."""
        result = await db_conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'reminders'
            )
        """)
        assert result is True


# =============================================================================
# Conversation and Message Tests
# =============================================================================

@pytest.mark.postgres
class TestConversationsAndMessages:
    """Test conversation and message operations."""

    @pytest.mark.asyncio
    async def test_create_conversation(self, db_conn, clean_test_data):
        """Test creating a conversation."""
        conversation_id = f"test_conv_{uuid.uuid4().hex[:8]}"

        await db_conn.execute(
            """INSERT INTO conversations (conversation_id, channel)
               VALUES ($1, 'test')""",
            conversation_id
        )

        # Verify conversation
        result = await db_conn.fetchrow(
            "SELECT * FROM conversations WHERE conversation_id = $1",
            conversation_id
        )
        assert result is not None
        assert result["channel"] == "test"
        assert result["status"] == "active"

    @pytest.mark.asyncio
    async def test_add_message_to_conversation(self, db_conn, clean_test_data):
        """Test adding a message to a conversation."""
        conversation_id = f"test_conv_{uuid.uuid4().hex[:8]}"

        # Create conversation
        await db_conn.execute(
            """INSERT INTO conversations (conversation_id, channel)
               VALUES ($1, 'test')""",
            conversation_id
        )

        # Add message
        await db_conn.execute(
            """INSERT INTO messages (conversation_id, message_id, role, content)
               VALUES ($1, $2, $3, $4)""",
            conversation_id, "msg_1", "human", "Hello, world!"
        )

        # Verify message
        result = await db_conn.fetchrow(
            "SELECT * FROM messages WHERE conversation_id = $1",
            conversation_id
        )
        assert result is not None
        assert result["role"] == "human"
        assert result["content"] == "Hello, world!"

    @pytest.mark.asyncio
    async def test_conversation_message_count(self, db_conn, clean_test_data):
        """Test that message_count is updated via trigger."""
        conversation_id = f"test_conv_{uuid.uuid4().hex[:8]}"

        # Create conversation
        await db_conn.execute(
            """INSERT INTO conversations (conversation_id, channel)
               VALUES ($1, 'test')""",
            conversation_id
        )

        # Add multiple messages
        for i in range(3):
            await db_conn.execute(
                """INSERT INTO messages (conversation_id, message_id, role, content)
                   VALUES ($1, $2, $3, $4)""",
                conversation_id, f"msg_{i}", "human", f"Message {i}"
            )

        # Check message_count
        result = await db_conn.fetchrow(
            "SELECT message_count FROM conversations WHERE conversation_id = $1",
            conversation_id
        )
        assert result["message_count"] == 3


# =============================================================================
# Worker and Scheduled Job Tests
# =============================================================================

@pytest.mark.postgres
class TestWorkersAndJobs:
    """Test scheduled flow operations."""

    @pytest.mark.asyncio
    async def test_create_scheduled_flow(self, db_conn, clean_test_data):
        """Test creating a scheduled flow."""
        thread_id = f"test_thread_{uuid.uuid4().hex[:8]}"

        await db_conn.execute(
            """INSERT INTO scheduled_flows
               (thread_id, name, task, flow, due_time)
               VALUES ($1, $2, $3, $4, NOW() + INTERVAL '1 hour')""",
            thread_id, "Test Flow", "Test task", "Simple flow"
        )

        result = await db_conn.fetchrow(
            "SELECT * FROM scheduled_flows WHERE thread_id = $1 AND name = $2",
            thread_id, "Test Flow"
        )
        assert result is not None
        assert result["name"] == "Test Flow"
        assert result["status"] == "pending"

    @pytest.mark.asyncio
    async def test_flow_status_transition(self, db_conn, clean_test_data):
        """Test updating flow status through its lifecycle."""
        thread_id = f"test_thread_{uuid.uuid4().hex[:8]}"

        job_result = await db_conn.fetchrow(
            """INSERT INTO scheduled_flows
               (thread_id, name, task, flow, due_time)
               VALUES ($1, $2, $3, $4, NOW() + INTERVAL '1 hour')
               RETURNING id""",
            thread_id, "Test Flow", "Test task", "Flow"
        )
        job_id = job_result["id"]

        await db_conn.execute(
            """UPDATE scheduled_flows
               SET status = 'running', started_at = NOW()
               WHERE id = $1""",
            job_id
        )

        result = await db_conn.fetchrow(
            "SELECT * FROM scheduled_flows WHERE id = $1",
            job_id
        )
        assert result["status"] == "running"
        assert result["started_at"] is not None

        await db_conn.execute(
            """UPDATE scheduled_flows
               SET status = 'completed', completed_at = NOW()
               WHERE id = $1""",
            job_id
        )

        result = await db_conn.fetchrow(
            "SELECT * FROM scheduled_flows WHERE id = $1",
            job_id
        )
        assert result["status"] == "completed"
        assert result["completed_at"] is not None


class TestReminders:
    """Test reminder operations."""

    @pytest.mark.asyncio
    async def test_create_reminder(self, db_conn, clean_test_data):
        """Test creating a reminder."""
        thread_id = f"test_thread_{uuid.uuid4().hex[:8]}"

        await db_conn.execute(
            """INSERT INTO reminders (thread_id, message, due_time)
               VALUES ($1, $2, NOW() + INTERVAL '1 day')""",
            thread_id, "Test reminder"
        )

        # Verify reminder
        result = await db_conn.fetchrow(
            "SELECT * FROM reminders WHERE thread_id = $1",
            thread_id
        )
        assert result is not None
        assert result["message"] == "Test reminder"
        assert result["status"] == "pending"

    @pytest.mark.asyncio
    async def test_reminder_with_recurrence(self, db_conn, clean_test_data):
        """Test creating a recurring reminder."""
        thread_id = f"test_thread_{uuid.uuid4().hex[:8]}"

        await db_conn.execute(
            """INSERT INTO reminders (thread_id, message, due_time, recurrence)
               VALUES ($1, $2, NOW() + INTERVAL '1 hour', $3)""",
            thread_id, "Daily check-in", "0 9 * * *"
        )

        # Verify reminder
        result = await db_conn.fetchrow(
            "SELECT * FROM reminders WHERE thread_id = $1",
            thread_id
        )
        assert result is not None
        assert result["recurrence"] == "0 9 * * *"


# =============================================================================
# File and DB Path Tests
# =============================================================================

@pytest.mark.postgres
class TestFilePaths:
    """Test file path ownership tracking."""

    @pytest.mark.asyncio
    async def test_create_file_path(self, db_conn, clean_test_data):
        """Test creating a file path entry."""
        thread_id = f"test_thread_{uuid.uuid4().hex[:8]}"

        await db_conn.execute(
            """INSERT INTO file_paths (thread_id, channel)
               VALUES ($1, $2)""",
            thread_id, "telegram"
        )

        # Verify entry
        result = await db_conn.fetchrow(
            "SELECT * FROM file_paths WHERE thread_id = $1",
            thread_id
        )
        assert result is not None
        assert result["channel"] == "telegram"


@pytest.mark.postgres
class TestTDBPaths:
    """Test transactional database path ownership tracking."""

    @pytest.mark.asyncio
    async def test_create_tdb_path(self, db_conn, clean_test_data):
        """Test creating a TDB path entry."""
        thread_id = f"test_thread_{uuid.uuid4().hex[:8]}"
        tdb_path = "/data/tdb/test_thread.db"

        await db_conn.execute(
            """INSERT INTO tdb_paths (thread_id, tdb_path, channel)
               VALUES ($1, $2, $3)""",
            thread_id, tdb_path, "telegram"
        )

        # Verify entry
        result = await db_conn.fetchrow(
            "SELECT * FROM tdb_paths WHERE thread_id = $1",
            thread_id
        )
        assert result is not None
        assert result["tdb_path"] == tdb_path
