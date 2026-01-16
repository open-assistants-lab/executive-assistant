"""Unit tests for ScheduledJob storage."""

import pytest
from datetime import datetime, timedelta

from cassey.storage.scheduled_jobs import (
    ScheduledJob,
    ScheduledJobStorage,
    get_scheduled_job_storage,
)
from cassey.utils.cron import parse_cron_next


@pytest.fixture
async def clean_db():
    """Provide a clean database state for each test."""
    storage = ScheduledJobStorage()
    yield storage


class TestParseCronNext:
    """Test cron expression parsing."""

    def test_cron_hourly(self):
        """Test @hourly shortcut."""
        now = datetime(2025, 1, 15, 10, 30, 0)
        next_time = parse_cron_next("hourly", now)
        expected = datetime(2025, 1, 15, 11, 30, 0)
        assert next_time == expected

    def test_cron_at_hourly(self):
        """Test @hourly shortcut."""
        now = datetime(2025, 1, 15, 10, 30, 0)
        next_time = parse_cron_next("@hourly", now)
        expected = datetime(2025, 1, 15, 11, 30, 0)
        assert next_time == expected

    def test_cron_daily(self):
        """Test @daily shortcut."""
        now = datetime(2025, 1, 15, 10, 30, 0)
        next_time = parse_cron_next("daily", now)
        expected = datetime(2025, 1, 16, 0, 0, 0)
        assert next_time == expected

    def test_cron_at_daily(self):
        """Test @daily shortcut."""
        now = datetime(2025, 1, 15, 10, 30, 0)
        next_time = parse_cron_next("@daily", now)
        expected = datetime(2025, 1, 16, 0, 0, 0)
        assert next_time == expected

    def test_cron_weekly(self):
        """Test @weekly shortcut."""
        now = datetime(2025, 1, 15, 10, 30, 0)  # Wednesday
        next_time = parse_cron_next("weekly", now)
        # Should be next Sunday at midnight
        assert next_time.weekday() == 6  # Sunday
        assert next_time.hour == 0
        assert next_time.minute == 0

    def test_cron_monthly(self):
        """Test @monthly shortcut."""
        now = datetime(2025, 1, 15, 10, 30, 0)
        next_time = parse_cron_next("monthly", now)
        expected = datetime(2025, 2, 1, 0, 0, 0)
        assert next_time == expected

    def test_cron_daily_at_9am(self):
        """Test 'daily at 9am' format."""
        now = datetime(2025, 1, 15, 10, 0, 0)
        next_time = parse_cron_next("daily at 9am", now)
        expected = datetime(2025, 1, 16, 9, 0, 0)
        assert next_time == expected

    def test_cron_daily_at_9pm(self):
        """Test 'daily at 9pm' format."""
        now = datetime(2025, 1, 15, 10, 0, 0)
        next_time = parse_cron_next("daily at 9pm", now)
        expected = datetime(2025, 1, 15, 21, 0, 0)
        assert next_time == expected

    def test_cron_standard_daily_9am(self):
        """Test standard cron '0 9 * * *' (daily at 9am)."""
        now = datetime(2025, 1, 15, 8, 0, 0)
        next_time = parse_cron_next("0 9 * * *", now)
        expected = datetime(2025, 1, 15, 9, 0, 0)
        assert next_time == expected

    def test_cron_standard_daily_after_hour(self):
        """Test standard cron when current time is past the hour."""
        now = datetime(2025, 1, 15, 10, 0, 0)
        next_time = parse_cron_next("0 9 * * *", now)
        expected = datetime(2025, 1, 16, 9, 0, 0)
        assert next_time == expected

    def test_cron_every_6_hours(self):
        """Test '0 */6 * * *' (every 6 hours)."""
        now = datetime(2025, 1, 15, 8, 0, 0)
        next_time = parse_cron_next("0 */6 * * *", now)
        expected = datetime(2025, 1, 15, 12, 0, 0)
        assert next_time == expected

    def test_cron_every_30_minutes(self):
        """Test '*/30 * * * *' (every 30 minutes)."""
        now = datetime(2025, 1, 15, 10, 15, 0)
        next_time = parse_cron_next("*/30 * * * *", now)
        expected = datetime(2025, 1, 15, 10, 30, 0)
        assert next_time == expected

    def test_cron_invalid(self):
        """Test invalid cron expression raises ValueError."""
        with pytest.raises(ValueError):
            parse_cron_next("invalid cron", datetime.now())


class TestScheduledJobStorage:
    """Test ScheduledJobStorage CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_job(self, clean_db):
        """Test creating a new scheduled job."""
        due_time = datetime.now() + timedelta(hours=1)

        job = await clean_db.create(
            user_id="test_user",
            thread_id="telegram:test_thread",
            task="Test task",
            flow="Test flow",
            due_time=due_time,
        )

        assert job.id > 0
        assert job.user_id == "test_user"
        assert job.thread_id == "telegram:test_thread"
        assert job.task == "Test task"
        assert job.flow == "Test flow"
        assert job.status == "pending"
        assert job.is_pending

    @pytest.mark.asyncio
    async def test_create_job_with_worker(self, clean_db):
        """Test creating a job with a worker."""
        due_time = datetime.now() + timedelta(hours=1)

        job = await clean_db.create(
            user_id="test_user",
            thread_id="telegram:test_thread",
            task="Test task",
            flow="Test flow",
            due_time=due_time,
            worker_id=123,
            name="test_job",
        )

        assert job.worker_id == 123
        assert job.name == "test_job"

    @pytest.mark.asyncio
    async def test_create_job_with_cron(self, clean_db):
        """Test creating a recurring job."""
        due_time = datetime.now() + timedelta(hours=1)

        job = await clean_db.create(
            user_id="test_user",
            thread_id="telegram:test_thread",
            task="Test task",
            flow="Test flow",
            due_time=due_time,
            cron="0 9 * * *",
        )

        assert job.cron == "0 9 * * *"
        assert job.is_recurring

    @pytest.mark.asyncio
    async def test_get_job_by_id(self, clean_db):
        """Test retrieving a job by ID."""
        due_time = datetime.now() + timedelta(hours=1)

        created = await clean_db.create(
            user_id="test_user",
            thread_id="telegram:test_thread",
            task="Test task",
            flow="Test flow",
            due_time=due_time,
        )

        retrieved = await clean_db.get_by_id(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.task == "Test task"

    @pytest.mark.asyncio
    async def test_get_job_by_id_not_found(self, clean_db):
        """Test retrieving non-existent job returns None."""
        job = await clean_db.get_by_id(99999)
        assert job is None

    @pytest.mark.asyncio
    async def test_get_due_jobs(self, clean_db):
        """Test getting jobs due before a time."""
        now = datetime.now()

        # Create a due job
        await clean_db.create(
            user_id="test_user",
            thread_id="telegram:test_thread",
            task="Due task",
            flow="Flow",
            due_time=now - timedelta(minutes=5),  # Past due
        )

        # Create a future job
        await clean_db.create(
            user_id="test_user",
            thread_id="telegram:test_thread",
            task="Future task",
            flow="Flow",
            due_time=now + timedelta(hours=1),
        )

        due_jobs = await clean_db.get_due_jobs(now)

        assert len(due_jobs) == 1
        assert due_jobs[0].task == "Due task"

    @pytest.mark.asyncio
    async def test_list_jobs_by_user(self, clean_db):
        """Test listing jobs filtered by user."""
        user_id = "test_user_list"

        await clean_db.create(
            user_id=user_id,
            thread_id="telegram:thread1",
            task="Task 1",
            flow="Flow 1",
            due_time=datetime.now() + timedelta(hours=1),
        )
        await clean_db.create(
            user_id=user_id,
            thread_id="telegram:thread2",
            task="Task 2",
            flow="Flow 2",
            due_time=datetime.now() + timedelta(hours=2),
        )
        await clean_db.create(
            user_id="other_user",
            thread_id="telegram:thread3",
            task="Task 3",
            flow="Flow 3",
            due_time=datetime.now() + timedelta(hours=1),
        )

        jobs = await clean_db.list_by_user(user_id)

        assert len(jobs) == 2
        assert all(j.user_id == user_id for j in jobs)

    @pytest.mark.asyncio
    async def test_list_jobs_by_status(self, clean_db):
        """Test listing jobs filtered by status."""
        user_id = "test_user_status"

        job1 = await clean_db.create(
            user_id=user_id,
            thread_id="telegram:thread1",
            task="Task 1",
            flow="Flow 1",
            due_time=datetime.now() + timedelta(hours=1),
        )
        await clean_db.mark_started(job1.id)

        jobs_pending = await clean_db.list_by_user(user_id, status="pending")
        jobs_running = await clean_db.list_by_user(user_id, status="running")

        assert len(jobs_running) == 1
        assert jobs_running[0].status == "running"

        # job1 is no longer pending
        assert job1.id not in [j.id for j in jobs_pending]

    @pytest.mark.asyncio
    async def test_mark_started(self, clean_db):
        """Test marking a job as started."""
        job = await clean_db.create(
            user_id="test_user",
            thread_id="telegram:test_thread",
            task="Test task",
            flow="Flow",
            due_time=datetime.now() - timedelta(minutes=5),
        )

        success = await clean_db.mark_started(job.id)

        assert success is True

        updated = await clean_db.get_by_id(job.id)
        assert updated.status == "running"
        assert updated.is_running
        assert updated.started_at is not None

    @pytest.mark.asyncio
    async def test_mark_completed(self, clean_db):
        """Test marking a job as completed."""
        job = await clean_db.create(
            user_id="test_user",
            thread_id="telegram:test_thread",
            task="Test task",
            flow="Flow",
            due_time=datetime.now() - timedelta(minutes=5),
        )
        await clean_db.mark_started(job.id)

        result = "Task completed successfully"
        success = await clean_db.mark_completed(job.id, result)

        assert success is True

        updated = await clean_db.get_by_id(job.id)
        assert updated.status == "completed"
        assert updated.is_completed
        assert updated.completed_at is not None
        assert updated.result == result

    @pytest.mark.asyncio
    async def test_mark_failed(self, clean_db):
        """Test marking a job as failed."""
        job = await clean_db.create(
            user_id="test_user",
            thread_id="telegram:test_thread",
            task="Test task",
            flow="Flow",
            due_time=datetime.now() - timedelta(minutes=5),
        )

        error = "Something went wrong"
        success = await clean_db.mark_failed(job.id, error)

        assert success is True

        updated = await clean_db.get_by_id(job.id)
        assert updated.status == "failed"
        assert updated.is_failed
        assert updated.completed_at is not None
        assert updated.error_message == error

    @pytest.mark.asyncio
    async def test_cancel_job(self, clean_db):
        """Test cancelling a pending job."""
        job = await clean_db.create(
            user_id="test_user",
            thread_id="telegram:test_thread",
            task="Test task",
            flow="Flow",
            due_time=datetime.now() + timedelta(hours=1),
        )

        success = await clean_db.cancel(job.id)

        assert success is True

        updated = await clean_db.get_by_id(job.id)
        assert updated.status == "cancelled"

    @pytest.mark.asyncio
    async def test_cancel_running_job_fails(self, clean_db):
        """Test that cancelling a running job returns False."""
        job = await clean_db.create(
            user_id="test_user",
            thread_id="telegram:test_thread",
            task="Test task",
            flow="Flow",
            due_time=datetime.now() - timedelta(minutes=5),
        )
        await clean_db.mark_started(job.id)

        success = await clean_db.cancel(job.id)

        # Cannot cancel a running job
        assert success is False

    @pytest.mark.asyncio
    async def test_create_next_instance_for_recurring_job(self, clean_db):
        """Test creating next instance of a recurring job."""
        now = datetime.now()
        due_time = now - timedelta(minutes=5)  # Already past

        parent_job = await clean_db.create(
            user_id="test_user",
            thread_id="telegram:test_thread",
            task="Recurring task",
            flow="Flow",
            due_time=due_time,
            cron="0 9 * * *",
            name="daily_job",
        )
        await clean_db.mark_started(parent_job.id)
        await clean_db.mark_completed(parent_job.id, "Done")

        next_due = parse_cron_next(parent_job.cron, now)
        next_job = await clean_db.create_next_instance(parent_job, next_due)

        assert next_job is not None
        assert next_job.id != parent_job.id
        assert next_job.task == parent_job.task
        assert next_job.flow == parent_job.flow
        assert next_job.cron == parent_job.cron
        assert next_job.name == parent_job.name
        assert next_job.status == "pending"

    @pytest.mark.asyncio
    async def test_create_next_instance_for_non_recurring_job(self, clean_db):
        """Test that next instance is None for non-recurring job."""
        job = await clean_db.create(
            user_id="test_user",
            thread_id="telegram:test_thread",
            task="One-time task",
            flow="Flow",
            due_time=datetime.now() - timedelta(minutes=5),
            cron=None,  # No recurrence
        )

        next_job = await clean_db.create_next_instance(job, datetime.now())

        assert next_job is None


class TestScheduledJobDataclass:
    """Test ScheduledJob dataclass properties."""

    def test_job_is_pending(self):
        """Test is_pending property."""
        job = ScheduledJob(
            id=1,
            user_id="user",
            thread_id="thread",
            worker_id=None,
            name=None,
            task="Task",
            flow="Flow",
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

    def test_job_is_running(self):
        """Test is_running property."""
        job = ScheduledJob(
            id=1,
            user_id="user",
            thread_id="thread",
            worker_id=None,
            name=None,
            task="Task",
            flow="Flow",
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

    def test_job_is_recurring(self):
        """Test is_recurring property."""
        job = ScheduledJob(
            id=1,
            user_id="user",
            thread_id="thread",
            worker_id=None,
            name=None,
            task="Task",
            flow="Flow",
            due_time=datetime.now(),
            status="pending",
            cron="0 9 * * *",
            created_at=datetime.now(),
            started_at=None,
            completed_at=None,
            error_message=None,
            result=None,
        )
        assert job.is_recurring is True


@pytest.mark.asyncio
async def test_get_scheduled_job_storage_singleton():
    """Test that get_scheduled_job_storage returns a singleton instance."""
    storage1 = await get_scheduled_job_storage()
    storage2 = await get_scheduled_job_storage()

    assert storage1 is storage2
