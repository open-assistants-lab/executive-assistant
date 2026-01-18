"""Tests for scheduled jobs storage and management.

Tests the ScheduledJobStorage class and ScheduledJob dataclass.
"""

import uuid
from datetime import datetime, timedelta

import pytest

from cassey.storage.scheduled_jobs import (
    ScheduledJob,
    ScheduledJobStorage,
    get_scheduled_job_storage,
)


# =============================================================================
# ScheduledJob Dataclass Tests
# =============================================================================

class TestScheduledJob:
    """Test ScheduledJob dataclass properties and methods."""

    def test_job_properties(self):
        """Test job status property methods."""
        job = ScheduledJob(
            id=1,
            user_id="test_user",
            thread_id="test_thread",
            worker_id=None,
            name="Test Job",
            task="Test task",
            flow="Simple flow",
            due_time=datetime.now(),
            status="pending",
            cron=None,
            created_at=datetime.now(),
            started_at=None,
            completed_at=None,
            error_message=None,
            result=None,
        )

        assert job.is_pending is True
        assert job.is_running is False
        assert job.is_completed is False
        assert job.is_failed is False
        assert job.is_recurring is False

    def test_job_status_running(self):
        """Test running status property."""
        job = ScheduledJob(
            id=1,
            user_id="test_user",
            thread_id="test_thread",
            worker_id=None,
            name="Test Job",
            task="Test task",
            flow="Simple flow",
            due_time=datetime.now(),
            status="running",
            cron=None,
            created_at=datetime.now(),
            started_at=datetime.now(),
            completed_at=None,
            error_message=None,
            result=None,
        )

        assert job.is_pending is False
        assert job.is_running is True
        assert job.is_completed is False
        assert job.is_failed is False

    def test_job_status_completed(self):
        """Test completed status property."""
        job = ScheduledJob(
            id=1,
            user_id="test_user",
            thread_id="test_thread",
            worker_id=None,
            name="Test Job",
            task="Test task",
            flow="Simple flow",
            due_time=datetime.now(),
            status="completed",
            cron=None,
            created_at=datetime.now(),
            started_at=datetime.now(),
            completed_at=datetime.now(),
            error_message=None,
            result="Success",
        )

        assert job.is_pending is False
        assert job.is_running is False
        assert job.is_completed is True
        assert job.is_failed is False

    def test_job_status_failed(self):
        """Test failed status property."""
        job = ScheduledJob(
            id=1,
            user_id="test_user",
            thread_id="test_thread",
            worker_id=None,
            name="Test Job",
            task="Test task",
            flow="Simple flow",
            due_time=datetime.now(),
            status="failed",
            cron=None,
            created_at=datetime.now(),
            started_at=datetime.now(),
            completed_at=datetime.now(),
            error_message="Something went wrong",
            result=None,
        )

        assert job.is_pending is False
        assert job.is_running is False
        assert job.is_completed is False
        assert job.is_failed is True

    def test_recurring_job(self):
        """Test recurring job property."""
        job = ScheduledJob(
            id=1,
            user_id="test_user",
            thread_id="test_thread",
            worker_id=None,
            name="Daily Job",
            task="Test task",
            flow="Simple flow",
            due_time=datetime.now(),
            status="pending",
            cron="0 9 * * *",  # Daily at 9 AM
            created_at=datetime.now(),
            started_at=None,
            completed_at=None,
            error_message=None,
            result=None,
        )

        assert job.is_recurring is True
        assert job.cron == "0 9 * * *"

    def test_non_recurring_job(self):
        """Test non-recurring job property."""
        job = ScheduledJob(
            id=1,
            user_id="test_user",
            thread_id="test_thread",
            worker_id=None,
            name="One-time Job",
            task="Test task",
            flow="Simple flow",
            due_time=datetime.now(),
            status="pending",
            cron=None,
            created_at=datetime.now(),
            started_at=None,
            completed_at=None,
            error_message=None,
            result=None,
        )

        assert job.is_recurring is False

    def test_non_recurring_job_with_empty_cron(self):
        """Test that empty cron string is not considered recurring."""
        job = ScheduledJob(
            id=1,
            user_id="test_user",
            thread_id="test_thread",
            worker_id=None,
            name="Job",
            task="Test task",
            flow="Simple flow",
            due_time=datetime.now(),
            status="pending",
            cron="",  # Empty string
            created_at=datetime.now(),
            started_at=None,
            completed_at=None,
            error_message=None,
            result=None,
        )

        assert job.is_recurring is False


# =============================================================================
# ScheduledJobStorage Tests (with mocked DB)
# =============================================================================

class TestScheduledJobStorageUnit:
    """Unit tests for ScheduledJobStorage with mocked database."""

    @pytest.fixture
    def storage(self):
        """Create a ScheduledJobStorage instance."""
        return ScheduledJobStorage()

    def test_storage_init(self, storage):
        """Test storage initialization."""
        assert storage._conn_string is not None

    def test_storage_init_custom_conn_string(self):
        """Test storage initialization with custom connection string."""
        custom_conn = "postgresql://user:pass@localhost/db"
        storage = ScheduledJobStorage(conn_string=custom_conn)
        assert storage._conn_string == custom_conn


# =============================================================================
# ScheduledJobStorage Integration Tests
# =============================================================================

@pytest.mark.postgres
class TestScheduledJobStorageIntegration:
    """Integration tests with real database."""

    @pytest.fixture
    def storage(self):
        """Create storage instance for testing."""
        return ScheduledJobStorage()

    @pytest.mark.asyncio
    async def test_create_job(self, storage, db_conn, clean_test_data):
        """Test creating a new scheduled job."""
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"
        thread_id = f"test_thread_{uuid.uuid4().hex[:8]}"
        due_time = datetime.now() + timedelta(hours=1)

        job = await storage.create(
            user_id=user_id,
            thread_id=thread_id,
            task="Check the weather",
            flow="fetch weather → report result",
            due_time=due_time,
            name="Weather Check",
        )

        assert job.id is not None
        assert job.user_id == user_id
        assert job.thread_id == thread_id
        assert job.task == "Check the weather"
        assert job.flow == "fetch weather → report result"
        assert job.name == "Weather Check"
        assert job.status == "pending"
        assert job.worker_id is None
        assert job.cron is None

    @pytest.mark.asyncio
    async def test_create_job_with_worker(self, storage, db_conn, clean_test_data):
        """Test creating a job with an associated worker."""
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"
        thread_id = f"test_thread_{uuid.uuid4().hex[:8]}"
        due_time = datetime.now() + timedelta(hours=1)

        # Create a worker first
        worker_result = await db_conn.fetchrow(
            """INSERT INTO workers (user_id, thread_id, name, tools, prompt)
               VALUES ($1, $2, $3, $4, $5) RETURNING id""",
            user_id, thread_id, "Test Worker", ["web_search"], "Test prompt"
        )
        worker_id = worker_result["id"]

        job = await storage.create(
            user_id=user_id,
            thread_id=thread_id,
            task="Execute task",
            flow="Simple flow",
            due_time=due_time,
            worker_id=worker_id,
        )

        assert job.worker_id == worker_id

    @pytest.mark.asyncio
    async def test_create_recurring_job(self, storage, db_conn, clean_test_data):
        """Test creating a recurring job with cron expression."""
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"
        thread_id = f"test_thread_{uuid.uuid4().hex[:8]}"
        due_time = datetime.now() + timedelta(hours=1)

        job = await storage.create(
            user_id=user_id,
            thread_id=thread_id,
            task="Daily backup",
            flow="backup → verify",
            due_time=due_time,
            name="Daily Backup",
            cron="0 2 * * *",  # Daily at 2 AM
        )

        assert job.is_recurring is True
        assert job.cron == "0 2 * * *"

    @pytest.mark.asyncio
    async def test_get_by_id(self, storage, db_conn, clean_test_data):
        """Test retrieving a job by ID."""
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"
        thread_id = f"test_thread_{uuid.uuid4().hex[:8]}"
        due_time = datetime.now() + timedelta(hours=1)

        # Create a job
        created_job = await storage.create(
            user_id=user_id,
            thread_id=thread_id,
            task="Test task",
            flow="Simple flow",
            due_time=due_time,
        )

        # Retrieve by ID
        retrieved_job = await storage.get_by_id(created_job.id)

        assert retrieved_job is not None
        assert retrieved_job.id == created_job.id
        assert retrieved_job.task == "Test task"

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, storage):
        """Test retrieving a non-existent job."""
        job = await storage.get_by_id(99999)
        assert job is None

    @pytest.mark.asyncio
    async def test_get_due_jobs(self, storage, db_conn, clean_test_data):
        """Test retrieving jobs due before a given time."""
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"
        thread_id = f"test_thread_{uuid.uuid4().hex[:8]}"
        now = datetime.now()

        # Create multiple jobs at different times
        await storage.create(
            user_id=user_id,
            thread_id=thread_id,
            task="Past job",
            flow="flow",
            due_time=now - timedelta(hours=1),  # Past
        )

        await storage.create(
            user_id=user_id,
            thread_id=thread_id,
            task="Future job",
            flow="flow",
            due_time=now + timedelta(hours=1),  # Future
        )

        await storage.create(
            user_id=user_id,
            thread_id=thread_id,
            task="Now job",
            flow="flow",
            due_time=now,  # Now
        )

        # Get due jobs (should return past and now jobs)
        due_jobs = await storage.get_due_jobs(now)
        assert len(due_jobs) >= 2

        task_list = [job.task for job in due_jobs]
        assert "Past job" in task_list
        assert "Now job" in task_list
        assert "Future job" not in task_list

    @pytest.mark.asyncio
    async def test_list_by_user(self, storage, db_conn, clean_test_data):
        """Test listing jobs for a specific user."""
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"
        thread_id = f"test_thread_{uuid.uuid4().hex[:8]}"

        # Create multiple jobs for the same user
        await storage.create(
            user_id=user_id,
            thread_id=thread_id,
            task="Task 1",
            flow="flow1",
            due_time=datetime.now() + timedelta(hours=1),
        )

        await storage.create(
            user_id=user_id,
            thread_id=thread_id,
            task="Task 2",
            flow="flow2",
            due_time=datetime.now() + timedelta(hours=2),
        )

        # List jobs for user
        jobs = await storage.list_by_user(user_id)
        assert len(jobs) >= 2

        task_list = [job.task for job in jobs]
        assert "Task 1" in task_list
        assert "Task 2" in task_list

    @pytest.mark.asyncio
    async def test_list_by_user_with_status_filter(self, storage, db_conn, clean_test_data):
        """Test listing jobs for a user with status filter."""
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"
        thread_id = f"test_thread_{uuid.uuid4().hex[:8]}"

        # Create jobs with different statuses
        job1 = await storage.create(
            user_id=user_id,
            thread_id=thread_id,
            task="Pending job",
            flow="flow",
            due_time=datetime.now() + timedelta(hours=1),
        )

        job2 = await storage.create(
            user_id=user_id,
            thread_id=thread_id,
            task="Another pending",
            flow="flow",
            due_time=datetime.now() + timedelta(hours=1),
        )

        # Mark one as completed
        await storage.mark_completed(job1.id, "Done")

        # List only pending jobs
        pending_jobs = await storage.list_by_user(user_id, status="pending")
        assert len(pending_jobs) >= 1

        task_list = [job.task for job in pending_jobs]
        assert "Another pending" in task_list
        assert "Pending job" not in task_list

    @pytest.mark.asyncio
    async def test_list_by_thread(self, storage, db_conn, clean_test_data):
        """Test listing jobs for a specific thread."""
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"
        thread_id = f"test_thread_{uuid.uuid4().hex[:8]}"

        # Create jobs for the thread
        await storage.create(
            user_id=user_id,
            thread_id=thread_id,
            task="Thread job 1",
            flow="flow",
            due_time=datetime.now() + timedelta(hours=1),
        )

        await storage.create(
            user_id=user_id,
            thread_id=thread_id,
            task="Thread job 2",
            flow="flow",
            due_time=datetime.now() + timedelta(hours=1),
        )

        # List jobs for thread
        jobs = await storage.list_by_thread(thread_id)
        assert len(jobs) >= 2

        task_list = [job.task for job in jobs]
        assert "Thread job 1" in task_list
        assert "Thread job 2" in task_list

    @pytest.mark.asyncio
    async def test_mark_started(self, storage, db_conn, clean_test_data):
        """Test marking a job as started."""
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"
        thread_id = f"test_thread_{uuid.uuid4().hex[:8]}"

        job = await storage.create(
            user_id=user_id,
            thread_id=thread_id,
            task="Test task",
            flow="flow",
            due_time=datetime.now() + timedelta(hours=1),
        )

        # Mark as started
        result = await storage.mark_started(job.id)

        assert result is True

        # Verify status changed
        updated_job = await storage.get_by_id(job.id)
        assert updated_job.is_running is True
        assert updated_job.started_at is not None

    @pytest.mark.asyncio
    async def test_mark_started_not_found(self, storage):
        """Test marking a non-existent job as started."""
        result = await storage.mark_started(99999)
        assert result is False

    @pytest.mark.asyncio
    async def test_mark_completed(self, storage, db_conn, clean_test_data):
        """Test marking a job as completed."""
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"
        thread_id = f"test_thread_{uuid.uuid4().hex[:8]}"

        job = await storage.create(
            user_id=user_id,
            thread_id=thread_id,
            task="Test task",
            flow="flow",
            due_time=datetime.now() + timedelta(hours=1),
        )

        # First mark as started
        await storage.mark_started(job.id)

        # Then mark as completed
        result = await storage.mark_completed(job.id, result="Job completed successfully")

        assert result is True

        # Verify status changed
        updated_job = await storage.get_by_id(job.id)
        assert updated_job.is_completed is True
        assert updated_job.completed_at is not None
        assert updated_job.result == "Job completed successfully"

    @pytest.mark.asyncio
    async def test_mark_failed(self, storage, db_conn, clean_test_data):
        """Test marking a job as failed."""
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"
        thread_id = f"test_thread_{uuid.uuid4().hex[:8]}"

        job = await storage.create(
            user_id=user_id,
            thread_id=thread_id,
            task="Test task",
            flow="flow",
            due_time=datetime.now() + timedelta(hours=1),
        )

        # Mark as started then failed
        await storage.mark_started(job.id)
        result = await storage.mark_failed(job.id, error_message="Network timeout")

        assert result is True

        # Verify status changed
        updated_job = await storage.get_by_id(job.id)
        assert updated_job.is_failed is True
        assert updated_job.completed_at is not None
        assert updated_job.error_message == "Network timeout"

    @pytest.mark.asyncio
    async def test_cancel(self, storage, db_conn, clean_test_data):
        """Test cancelling a pending job."""
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"
        thread_id = f"test_thread_{uuid.uuid4().hex[:8]}"

        job = await storage.create(
            user_id=user_id,
            thread_id=thread_id,
            task="Test task",
            flow="flow",
            due_time=datetime.now() + timedelta(hours=1),
        )

        # Cancel the job
        result = await storage.cancel(job.id)

        assert result is True

        # Verify status changed
        updated_job = await storage.get_by_id(job.id)
        assert updated_job.status == "cancelled"

    @pytest.mark.asyncio
    async def test_cancel_running_job_fails(self, storage, db_conn, clean_test_data):
        """Test that cancelling a running job has no effect."""
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"
        thread_id = f"test_thread_{uuid.uuid4().hex[:8]}"

        job = await storage.create(
            user_id=user_id,
            thread_id=thread_id,
            task="Test task",
            flow="flow",
            due_time=datetime.now() + timedelta(hours=1),
        )

        # Mark as running
        await storage.mark_started(job.id)

        # Try to cancel (should fail)
        result = await storage.cancel(job.id)

        assert result is False

        # Verify job is still running
        updated_job = await storage.get_by_id(job.id)
        assert updated_job.is_running is True

    @pytest.mark.asyncio
    async def test_create_next_instance(self, storage, db_conn, clean_test_data):
        """Test creating the next instance of a recurring job."""
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"
        thread_id = f"test_thread_{uuid.uuid4().hex[:8]}"
        now = datetime.now()

        # Create a recurring job
        parent_job = await storage.create(
            user_id=user_id,
            thread_id=thread_id,
            task="Daily check",
            flow="check → report",
            due_time=now,
            cron="0 9 * * *",
            name="Daily Check",
        )

        # Complete the parent job
        await storage.mark_started(parent_job.id)
        await storage.mark_completed(parent_job.id, result="Success")

        # Create next instance
        next_due = now + timedelta(days=1)
        next_job = await storage.create_next_instance(parent_job, next_due)

        assert next_job is not None
        assert next_job.task == parent_job.task
        assert next_job.cron == parent_job.cron
        assert next_job.name == parent_job.name
        assert next_job.status == "pending"

    @pytest.mark.asyncio
    async def test_create_next_instance_non_recurring(self, storage, db_conn, clean_test_data):
        """Test that next instance is None for non-recurring jobs."""
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"
        thread_id = f"test_thread_{uuid.uuid4().hex[:8]}"
        now = datetime.now()

        # Create a non-recurring job
        parent_job = await storage.create(
            user_id=user_id,
            thread_id=thread_id,
            task="One-time task",
            flow="flow",
            due_time=now,
            cron=None,
        )

        # Try to create next instance
        next_job = await storage.create_next_instance(parent_job, now + timedelta(days=1))

        assert next_job is None

    @pytest.mark.asyncio
    async def test_job_lifecycle(self, storage, db_conn, clean_test_data):
        """Test complete job lifecycle: create -> start -> complete -> next."""
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"
        thread_id = f"test_thread_{uuid.uuid4().hex[:8]}"
        now = datetime.now()

        # Create recurring job
        job = await storage.create(
            user_id=user_id,
            thread_id=thread_id,
            task="Recurring task",
            flow="execute → log",
            due_time=now,
            cron="0 * * * *",  # Hourly
            name="Hourly Task",
        )

        assert job.is_pending is True

        # Mark as started
        await storage.mark_started(job.id)
        started_job = await storage.get_by_id(job.id)
        assert started_job.is_running is True

        # Mark as completed with result
        await storage.mark_completed(job.id, result="Task completed")
        completed_job = await storage.get_by_id(job.id)
        assert completed_job.is_completed is True
        assert completed_job.result == "Task completed"

        # Create next instance
        next_due = now + timedelta(hours=1)
        next_job = await storage.create_next_instance(completed_job, next_due)
        assert next_job is not None
        assert next_job.id != job.id  # Different job


# =============================================================================
# Global Storage Tests
# =============================================================================

class TestGlobalStorage:
    """Test global scheduled job storage instance."""

    @pytest.mark.asyncio
    async def test_get_scheduled_job_storage_singleton(self):
        """Test that get_scheduled_job_storage returns same instance."""
        storage1 = await get_scheduled_job_storage()
        storage2 = await get_scheduled_job_storage()
        assert storage1 is storage2
