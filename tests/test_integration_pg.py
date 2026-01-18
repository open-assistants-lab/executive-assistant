"""PostgreSQL integration tests.

These tests require a real PostgreSQL connection and will be skipped
unless the --run-postgres flag is provided.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
import asyncpg

from cassey.config import settings


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
    async def test_users_table_exists(self, db_conn):
        """Test that users table exists."""
        result = await db_conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'users'
            )
        """)
        assert result is True

    @pytest.mark.asyncio
    async def test_groups_table_exists(self, db_conn):
        """Test that groups table exists."""
        result = await db_conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'groups'
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
    async def test_workers_table_exists(self, db_conn):
        """Test that workers table exists."""
        result = await db_conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'workers'
            )
        """)
        assert result is True

    @pytest.mark.asyncio
    async def test_scheduled_jobs_table_exists(self, db_conn):
        """Test that scheduled_jobs table exists."""
        result = await db_conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'scheduled_jobs'
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
# User Operations Tests
# =============================================================================

@pytest.mark.postgres
class TestUserOperations:
    """Test user CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_user(self, db_conn, clean_test_data):
        """Test creating a new user."""
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"

        await db_conn.execute(
            "INSERT INTO users (user_id) VALUES ($1)",
            user_id
        )

        # Verify user was created
        result = await db_conn.fetchrow(
            "SELECT * FROM users WHERE user_id = $1",
            user_id
        )
        assert result is not None
        assert result["user_id"] == user_id
        assert result["status"] == "active"  # Default status

    @pytest.mark.asyncio
    async def test_create_user_with_alias(self, db_conn, clean_test_data):
        """Test creating a user with an alias."""
        alias_id = f"anon:{uuid.uuid4().hex}"
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"

        await db_conn.execute(
            "INSERT INTO users (user_id) VALUES ($1)",
            user_id
        )
        await db_conn.execute(
            "INSERT INTO user_aliases (alias_id, user_id) VALUES ($1, $2)",
            alias_id, user_id
        )

        # Verify alias was created
        result = await db_conn.fetchrow(
            "SELECT * FROM user_aliases WHERE alias_id = $1",
            alias_id
        )
        assert result is not None
        assert result["user_id"] == user_id

    @pytest.mark.asyncio
    async def test_user_status_update(self, db_conn, clean_test_data):
        """Test updating user status."""
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"

        await db_conn.execute(
            "INSERT INTO users (user_id, status) VALUES ($1, 'active')",
            user_id
        )

        # Suspend user
        await db_conn.execute(
            "UPDATE users SET status = 'suspended' WHERE user_id = $1",
            user_id
        )

        # Verify status was updated
        result = await db_conn.fetchval(
            "SELECT status FROM users WHERE user_id = $1",
            user_id
        )
        assert result == "suspended"


# =============================================================================
# Group Operations Tests
# =============================================================================

@pytest.mark.postgres
class TestGroupOperations:
    """Test group CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_group(self, db_conn, clean_test_data):
        """Test creating a new group."""
        group_id = f"test_group_{uuid.uuid4().hex[:8]}"

        await db_conn.execute(
            "INSERT INTO groups (group_id, name) VALUES ($1, $2)",
            group_id, "Test Group"
        )

        # Verify group was created
        result = await db_conn.fetchrow(
            "SELECT * FROM groups WHERE group_id = $1",
            group_id
        )
        assert result is not None
        assert result["name"] == "Test Group"

    @pytest.mark.asyncio
    async def test_add_group_member(self, db_conn, clean_test_data):
        """Test adding a member to a group."""
        group_id = f"test_group_{uuid.uuid4().hex[:8]}"
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"

        # Create group and user
        await db_conn.execute(
            "INSERT INTO groups (group_id, name) VALUES ($1, $2)",
            group_id, "Test Group"
        )
        await db_conn.execute(
            "INSERT INTO users (user_id) VALUES ($1)",
            user_id
        )

        # Add member
        await db_conn.execute(
            "INSERT INTO group_members (group_id, user_id, role) VALUES ($1, $2, 'admin')",
            group_id, user_id
        )

        # Verify membership
        result = await db_conn.fetchrow(
            "SELECT * FROM group_members WHERE group_id = $1 AND user_id = $2",
            group_id, user_id
        )
        assert result is not None
        assert result["role"] == "admin"

    @pytest.mark.asyncio
    async def test_list_group_members(self, db_conn, clean_test_data):
        """Test listing all members of a group."""
        group_id = f"test_group_{uuid.uuid4().hex[:8]}"
        user_ids = [f"test_user_{uuid.uuid4().hex[:8]}" for _ in range(3)]

        # Create group and users
        await db_conn.execute(
            "INSERT INTO groups (group_id, name) VALUES ($1, $2)",
            group_id, "Test Group"
        )
        for user_id in user_ids:
            await db_conn.execute(
                "INSERT INTO users (user_id) VALUES ($1)",
                user_id
            )
            await db_conn.execute(
                "INSERT INTO group_members (group_id, user_id, role) VALUES ($1, $2, 'member')",
                group_id, user_id
            )

        # List members
        results = await db_conn.fetch(
            "SELECT user_id FROM group_members WHERE group_id = $1",
            group_id
        )
        member_ids = [r["user_id"] for r in results]
        assert len(member_ids) == 3
        for user_id in user_ids:
            assert user_id in member_ids


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
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"

        await db_conn.execute(
            """INSERT INTO conversations (conversation_id, user_id, channel)
               VALUES ($1, $2, 'test')""",
            conversation_id, user_id
        )

        # Verify conversation
        result = await db_conn.fetchrow(
            "SELECT * FROM conversations WHERE conversation_id = $1",
            conversation_id
        )
        assert result is not None
        assert result["user_id"] == user_id
        assert result["channel"] == "test"
        assert result["status"] == "active"

    @pytest.mark.asyncio
    async def test_add_message_to_conversation(self, db_conn, clean_test_data):
        """Test adding a message to a conversation."""
        conversation_id = f"test_conv_{uuid.uuid4().hex[:8]}"

        # Create conversation
        await db_conn.execute(
            """INSERT INTO conversations (conversation_id, user_id, channel)
               VALUES ($1, 'test_user', 'test')""",
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
            """INSERT INTO conversations (conversation_id, user_id, channel)
               VALUES ($1, 'test_user', 'test')""",
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
    """Test worker and scheduled job operations."""

    @pytest.mark.asyncio
    async def test_create_worker(self, db_conn, clean_test_data):
        """Test creating a worker."""
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"
        thread_id = f"test_thread_{uuid.uuid4().hex[:8]}"

        await db_conn.execute(
            """INSERT INTO workers (user_id, thread_id, name, tools, prompt)
               VALUES ($1, $2, $3, $4, $5)""",
            user_id, thread_id, "Test Worker",
            ["web_search", "execute_python"],
            "You are a helpful assistant."
        )

        # Verify worker
        result = await db_conn.fetchrow(
            "SELECT * FROM workers WHERE user_id = $1 AND thread_id = $2",
            user_id, thread_id
        )
        assert result is not None
        assert result["name"] == "Test Worker"
        assert result["tools"] == ["web_search", "execute_python"]

    @pytest.mark.asyncio
    async def test_create_scheduled_job(self, db_conn, clean_test_data):
        """Test creating a scheduled job."""
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"
        thread_id = f"test_thread_{uuid.uuid4().hex[:8]}"

        # First create a worker
        worker_result = await db_conn.fetchrow(
            """INSERT INTO workers (user_id, thread_id, name, tools, prompt)
               VALUES ($1, $2, $3, $4, $5)
               RETURNING id""",
            user_id, thread_id, "Test Worker",
            ["web_search"],
            "Test prompt"
        )
        worker_id = worker_result["id"]

        # Create scheduled job
        await db_conn.execute(
            """INSERT INTO scheduled_jobs
               (user_id, thread_id, worker_id, name, task, flow, due_time)
               VALUES ($1, $2, $3, $4, $5, $6, NOW() + INTERVAL '1 hour')""",
            user_id, thread_id, worker_id,
            "Test Job", "Test task description", "Simple flow"
        )

        # Verify job
        result = await db_conn.fetchrow(
            "SELECT * FROM scheduled_jobs WHERE user_id = $1 AND thread_id = $2",
            user_id, thread_id
        )
        assert result is not None
        assert result["name"] == "Test Job"
        assert result["status"] == "pending"

    @pytest.mark.asyncio
    async def test_job_status_transition(self, db_conn, clean_test_data):
        """Test updating job status through its lifecycle."""
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"
        thread_id = f"test_thread_{uuid.uuid4().hex[:8]}"

        # Create worker and job
        worker_result = await db_conn.fetchrow(
            """INSERT INTO workers (user_id, thread_id, name, tools, prompt)
               VALUES ($1, $2, $3, $4, $5) RETURNING id""",
            user_id, thread_id, "Test Worker", ["web_search"], "Test prompt"
        )

        job_result = await db_conn.fetchrow(
            """INSERT INTO scheduled_jobs
               (user_id, thread_id, worker_id, name, task, flow, due_time)
               VALUES ($1, $2, $3, $4, $5, $6, NOW() + INTERVAL '1 hour')
               RETURNING id""",
            user_id, thread_id, worker_result["id"],
            "Test Job", "Test task", "Flow"
        )
        job_id = job_result["id"]

        # Transition to running
        await db_conn.execute(
            """UPDATE scheduled_jobs
               SET status = 'running', started_at = NOW()
               WHERE id = $1""",
            job_id
        )

        # Transition to completed
        await db_conn.execute(
            """UPDATE scheduled_jobs
               SET status = 'completed', completed_at = NOW(), result = 'Done'
               WHERE id = $1""",
            job_id
        )

        # Verify final state
        result = await db_conn.fetchrow(
            "SELECT * FROM scheduled_jobs WHERE id = $1",
            job_id
        )
        assert result["status"] == "completed"
        assert result["result"] == "Done"
        assert result["started_at"] is not None
        assert result["completed_at"] is not None


# =============================================================================
# Reminder Tests
# =============================================================================

@pytest.mark.postgres
class TestReminders:
    """Test reminder operations."""

    @pytest.mark.asyncio
    async def test_create_reminder(self, db_conn, clean_test_data):
        """Test creating a reminder."""
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"
        thread_id = f"test_thread_{uuid.uuid4().hex[:8]}"

        await db_conn.execute(
            """INSERT INTO reminders (user_id, thread_ids, message, due_time)
               VALUES ($1, $2, $3, NOW() + INTERVAL '1 day')""",
            user_id, [thread_id], "Test reminder"
        )

        # Verify reminder
        result = await db_conn.fetchrow(
            "SELECT * FROM reminders WHERE user_id = $1",
            user_id
        )
        assert result is not None
        assert result["message"] == "Test reminder"
        assert result["status"] == "pending"

    @pytest.mark.asyncio
    async def test_reminder_with_recurrence(self, db_conn, clean_test_data):
        """Test creating a recurring reminder."""
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"

        await db_conn.execute(
            """INSERT INTO reminders (user_id, thread_ids, message, due_time, recurrence)
               VALUES ($1, $2, $3, NOW() + INTERVAL '1 hour', $4)""",
            user_id, ["thread1"], "Daily check-in", "0 9 * * *"
        )

        # Verify reminder
        result = await db_conn.fetchrow(
            "SELECT * FROM reminders WHERE user_id = $1",
            user_id
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
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"

        await db_conn.execute(
            """INSERT INTO file_paths (thread_id, user_id, channel)
               VALUES ($1, $2, $3)""",
            thread_id, user_id, "telegram"
        )

        # Verify entry
        result = await db_conn.fetchrow(
            "SELECT * FROM file_paths WHERE thread_id = $1",
            thread_id
        )
        assert result is not None
        assert result["user_id"] == user_id
        assert result["channel"] == "telegram"


@pytest.mark.postgres
class TestDBPaths:
    """Test database path ownership tracking."""

    @pytest.mark.asyncio
    async def test_create_db_path(self, db_conn, clean_test_data):
        """Test creating a DB path entry."""
        thread_id = f"test_thread_{uuid.uuid4().hex[:8]}"
        db_path = "/data/db/test_thread.db"

        await db_conn.execute(
            """INSERT INTO db_paths (thread_id, db_path, channel)
               VALUES ($1, $2, $3)""",
            thread_id, db_path, "telegram"
        )

        # Verify entry
        result = await db_conn.fetchrow(
            "SELECT * FROM db_paths WHERE thread_id = $1",
            thread_id
        )
        assert result is not None
        assert result["db_path"] == db_path


# =============================================================================
# Cascade Delete Tests
# =============================================================================

@pytest.mark.postgres
class TestCascadeDeletes:
    """Test foreign key cascade delete behavior."""

    @pytest.mark.asyncio
    async def test_delete_user_cascades_to_aliases(self, db_conn, clean_test_data):
        """Test that deleting a user cascades to their aliases."""
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"
        alias_id = f"anon:{uuid.uuid4().hex}"

        # Create user with alias
        await db_conn.execute("INSERT INTO users (user_id) VALUES ($1)", user_id)
        await db_conn.execute(
            "INSERT INTO user_aliases (alias_id, user_id) VALUES ($1, $2)",
            alias_id, user_id
        )

        # Delete user
        await db_conn.execute("DELETE FROM users WHERE user_id = $1", user_id)

        # Verify alias is also deleted
        result = await db_conn.fetchval(
            "SELECT COUNT(*) FROM user_aliases WHERE alias_id = $1",
            alias_id
        )
        assert result == 0
