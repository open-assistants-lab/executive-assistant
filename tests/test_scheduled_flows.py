"""Tests for scheduled flows storage and management.

Tests the ScheduledFlowStorage class and ScheduledFlow dataclass.
"""

import uuid
from datetime import datetime, timedelta

import pytest

from executive_assistant.storage.scheduled_flows import (
    ScheduledFlow,
    ScheduledFlowStorage,
    get_scheduled_flow_storage,
)


# =============================================================================
# ScheduledFlow Dataclass Tests
# =============================================================================

class TestScheduledFlow:
    """Test ScheduledFlow dataclass properties and methods."""

    def test_flow_properties(self):
        """Test flow status property methods."""
        flow = ScheduledFlow(
            id=1,
            thread_id="test_thread",
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

        assert flow.is_pending is True
        assert flow.is_running is False
        assert flow.is_completed is False
        assert flow.is_failed is False
        assert flow.is_recurring is False

    def test_flow_status_running(self):
        """Test running status property."""
        flow = ScheduledFlow(
            id=1,
            thread_id="test_thread",
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

        assert flow.is_pending is False
        assert flow.is_running is True
        assert flow.is_completed is False
        assert flow.is_failed is False

    def test_flow_status_completed(self):
        """Test completed status property."""
        flow = ScheduledFlow(
            id=1,
            thread_id="test_thread",
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

        assert flow.is_pending is False
        assert flow.is_running is False
        assert flow.is_completed is True
        assert flow.is_failed is False

    def test_flow_status_failed(self):
        """Test failed status property."""
        flow = ScheduledFlow(
            id=1,
            thread_id="test_thread",
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

        assert flow.is_pending is False
        assert flow.is_running is False
        assert flow.is_completed is False
        assert flow.is_failed is True

    def test_recurring_flow(self):
        """Test recurring flow property."""
        flow = ScheduledFlow(
            id=1,
            thread_id="test_thread",
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

        assert flow.is_recurring is True
        assert flow.cron == "0 9 * * *"

    def test_non_recurring_flow(self):
        """Test non-recurring flow property."""
        flow = ScheduledFlow(
            id=1,
            thread_id="test_thread",
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

        assert flow.is_recurring is False

    def test_non_recurring_flow_with_empty_cron(self):
        """Test that empty cron string is not considered recurring."""
        flow = ScheduledFlow(
            id=1,
            thread_id="test_thread",
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

        assert flow.is_recurring is False


# =============================================================================
# ScheduledFlowStorage Tests (with mocked DB)
# =============================================================================

class TestScheduledFlowStorageUnit:
    """Unit tests for ScheduledFlowStorage with mocked database."""

    @pytest.fixture
    def storage(self):
        """Create a ScheduledFlowStorage instance."""
        return ScheduledFlowStorage()

    def test_storage_init(self, storage):
        """Test storage initialization."""
        assert storage._conn_string is not None

    def test_storage_init_custom_conn_string(self):
        """Test storage initialization with custom connection string."""
        custom_conn = "postgresql://user:pass@localhost/db"
        storage = ScheduledFlowStorage(conn_string=custom_conn)
        assert storage._conn_string == custom_conn


# =============================================================================
# ScheduledFlowStorage Integration Tests
# =============================================================================

@pytest.mark.postgres
class TestScheduledFlowStorageIntegration:
    """Integration tests with real database."""

    @pytest.fixture
    def storage(self):
        """Create storage instance for testing."""
        return ScheduledFlowStorage()

    @pytest.mark.asyncio
    async def test_create_flow(self, storage, db_conn, clean_test_data):
        """Test creating a new scheduled flow."""
        thread_id = f"test_thread_{uuid.uuid4().hex[:8]}"
        due_time = datetime.now() + timedelta(hours=1)

        flow = await storage.create(
            thread_id=thread_id,
            task="Check the weather",
            flow="fetch weather → report result",
            due_time=due_time,
            name="Weather Check",
        )

        assert flow.id is not None
        assert flow.thread_id == thread_id
        assert flow.task == "Check the weather"
        assert flow.flow == "fetch weather → report result"
        assert flow.name == "Weather Check"
        assert flow.status == "pending"
        assert flow.cron is None

    @pytest.mark.asyncio
    async def test_create_recurring_flow(self, storage, db_conn, clean_test_data):
        """Test creating a recurring flow with cron expression."""
        thread_id = f"test_thread_{uuid.uuid4().hex[:8]}"
        due_time = datetime.now() + timedelta(hours=1)

        flow = await storage.create(
            thread_id=thread_id,
            task="Daily backup",
            flow="backup → verify",
            due_time=due_time,
            name="Daily Backup",
            cron="0 2 * * *",  # Daily at 2 AM
        )

        assert flow.is_recurring is True
        assert flow.cron == "0 2 * * *"

    @pytest.mark.asyncio
    async def test_get_by_id(self, storage, db_conn, clean_test_data):
        """Test retrieving a flow by ID."""
        thread_id = f"test_thread_{uuid.uuid4().hex[:8]}"
        due_time = datetime.now() + timedelta(hours=1)

        # Create a flow
        created_flow = await storage.create(
            thread_id=thread_id,
            task="Test task",
            flow="Simple flow",
            due_time=due_time,
        )

        # Retrieve by ID
        retrieved_flow = await storage.get_by_id(created_flow.id)

        assert retrieved_flow is not None
        assert retrieved_flow.id == created_flow.id
        assert retrieved_flow.task == "Test task"

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, storage):
        """Test retrieving a non-existent flow."""
        flow = await storage.get_by_id(99999)
        assert flow is None

    @pytest.mark.asyncio
    async def test_get_due_flows(self, storage, db_conn, clean_test_data):
        """Test retrieving flows due before a given time."""
        thread_id = f"test_thread_{uuid.uuid4().hex[:8]}"
        now = datetime.now()

        # Create multiple flows at different times
        await storage.create(
            thread_id=thread_id,
            task="Past flow",
            flow="flow",
            due_time=now - timedelta(hours=1),  # Past
        )

        await storage.create(
            thread_id=thread_id,
            task="Future flow",
            flow="flow",
            due_time=now + timedelta(hours=1),  # Future
        )

        await storage.create(
            thread_id=thread_id,
            task="Now flow",
            flow="flow",
            due_time=now,  # Now
        )

        # Get due flows (should return past and now flows)
        due_flows = await storage.get_due_flows(now)
        assert len(due_flows) >= 2

        task_list = [flow.task for flow in due_flows]
        assert "Past flow" in task_list
        assert "Now flow" in task_list
        assert "Future flow" not in task_list

    @pytest.mark.asyncio
    async def test_list_by_thread(self, storage, db_conn, clean_test_data):
        """Test listing flows for a specific user."""
        thread_id = f"test_thread_{uuid.uuid4().hex[:8]}"

        # Create multiple flows for the same user
        await storage.create(
            thread_id=thread_id,
            task="Task 1",
            flow="flow1",
            due_time=datetime.now() + timedelta(hours=1),
        )

        await storage.create(
            thread_id=thread_id,
            task="Task 2",
            flow="flow2",
            due_time=datetime.now() + timedelta(hours=2),
        )

        # List flows for user
        flows = await storage.list_by_thread(thread_id)
        assert len(flows) >= 2

        task_list = [flow.task for flow in flows]
        assert "Task 1" in task_list
        assert "Task 2" in task_list

    @pytest.mark.asyncio
    async def test_list_by_thread_with_status_filter(self, storage, db_conn, clean_test_data):
        """Test listing flows for a user with status filter."""
        thread_id = f"test_thread_{uuid.uuid4().hex[:8]}"

        # Create flows with different statuses
        flow1 = await storage.create(
            thread_id=thread_id,
            task="Pending flow",
            flow="flow",
            due_time=datetime.now() + timedelta(hours=1),
        )

        flow2 = await storage.create(
            thread_id=thread_id,
            task="Another pending",
            flow="flow",
            due_time=datetime.now() + timedelta(hours=1),
        )

        # Mark one as completed
        await storage.mark_started(flow1.id)
        await storage.mark_completed(flow1.id, "Done")

        # List only pending flows
        pending_flows = await storage.list_by_thread(thread_id, status="pending")
        assert len(pending_flows) >= 1

        task_list = [flow.task for flow in pending_flows]
        assert "Another pending" in task_list
        assert "Pending flow" not in task_list

    @pytest.mark.asyncio
    async def test_list_by_thread(self, storage, db_conn, clean_test_data):
        """Test listing flows for a specific thread."""
        thread_id = f"test_thread_{uuid.uuid4().hex[:8]}"

        # Create flows for the thread
        await storage.create(
            thread_id=thread_id,
            task="Thread flow 1",
            flow="flow",
            due_time=datetime.now() + timedelta(hours=1),
        )

        await storage.create(
            thread_id=thread_id,
            task="Thread flow 2",
            flow="flow",
            due_time=datetime.now() + timedelta(hours=1),
        )

        # List flows for thread
        flows = await storage.list_by_thread(thread_id)
        assert len(flows) >= 2

        task_list = [flow.task for flow in flows]
        assert "Thread flow 1" in task_list
        assert "Thread flow 2" in task_list

    @pytest.mark.asyncio
    async def test_mark_started(self, storage, db_conn, clean_test_data):
        """Test marking a flow as started."""
        thread_id = f"test_thread_{uuid.uuid4().hex[:8]}"

        flow = await storage.create(
            thread_id=thread_id,
            task="Test task",
            flow="flow",
            due_time=datetime.now() + timedelta(hours=1),
        )

        # Mark as started
        result = await storage.mark_started(flow.id)

        assert result is True

        # Verify status changed
        updated_flow = await storage.get_by_id(flow.id)
        assert updated_flow.is_running is True
        assert updated_flow.started_at is not None

    @pytest.mark.asyncio
    async def test_mark_started_not_found(self, storage):
        """Test marking a non-existent flow as started."""
        result = await storage.mark_started(99999)
        assert result is False

    @pytest.mark.asyncio
    async def test_mark_completed(self, storage, db_conn, clean_test_data):
        """Test marking a flow as completed."""
        thread_id = f"test_thread_{uuid.uuid4().hex[:8]}"

        flow = await storage.create(
            thread_id=thread_id,
            task="Test task",
            flow="flow",
            due_time=datetime.now() + timedelta(hours=1),
        )

        # First mark as started
        await storage.mark_started(flow.id)

        # Then mark as completed
        result = await storage.mark_completed(flow.id, result="Job completed successfully")

        assert result is True

        # Verify status changed
        updated_flow = await storage.get_by_id(flow.id)
        assert updated_flow.is_completed is True
        assert updated_flow.completed_at is not None
        assert updated_flow.result == "Job completed successfully"

    @pytest.mark.asyncio
    async def test_mark_failed(self, storage, db_conn, clean_test_data):
        """Test marking a flow as failed."""
        thread_id = f"test_thread_{uuid.uuid4().hex[:8]}"

        flow = await storage.create(
            thread_id=thread_id,
            task="Test task",
            flow="flow",
            due_time=datetime.now() + timedelta(hours=1),
        )

        # Mark as started then failed
        await storage.mark_started(flow.id)
        result = await storage.mark_failed(flow.id, error_message="Network timeout")

        assert result is True

        # Verify status changed
        updated_flow = await storage.get_by_id(flow.id)
        assert updated_flow.is_failed is True
        assert updated_flow.completed_at is not None
        assert updated_flow.error_message == "Network timeout"

    @pytest.mark.asyncio
    async def test_cancel(self, storage, db_conn, clean_test_data):
        """Test cancelling a pending flow."""
        thread_id = f"test_thread_{uuid.uuid4().hex[:8]}"

        flow = await storage.create(
            thread_id=thread_id,
            task="Test task",
            flow="flow",
            due_time=datetime.now() + timedelta(hours=1),
        )

        # Cancel the flow
        result = await storage.cancel(flow.id)

        assert result is True

        # Verify status changed
        updated_flow = await storage.get_by_id(flow.id)
        assert updated_flow.status == "cancelled"

    @pytest.mark.asyncio
    async def test_cancel_running_flow_fails(self, storage, db_conn, clean_test_data):
        """Test that cancelling a running flow has no effect."""
        thread_id = f"test_thread_{uuid.uuid4().hex[:8]}"

        flow = await storage.create(
            thread_id=thread_id,
            task="Test task",
            flow="flow",
            due_time=datetime.now() + timedelta(hours=1),
        )

        # Mark as running
        await storage.mark_started(flow.id)

        # Try to cancel (should fail)
        result = await storage.cancel(flow.id)

        assert result is False

        # Verify flow is still running
        updated_flow = await storage.get_by_id(flow.id)
        assert updated_flow.is_running is True

    @pytest.mark.asyncio
    async def test_create_next_instance(self, storage, db_conn, clean_test_data):
        """Test creating the next instance of a recurring flow."""
        thread_id = f"test_thread_{uuid.uuid4().hex[:8]}"
        now = datetime.now()

        # Create a recurring flow
        parent_flow = await storage.create(
            thread_id=thread_id,
            task="Daily check",
            flow="check → report",
            due_time=now,
            cron="0 9 * * *",
            name="Daily Check",
        )

        # Complete the parent flow
        await storage.mark_started(parent_flow.id)
        await storage.mark_completed(parent_flow.id, result="Success")

        # Create next instance
        next_due = now + timedelta(days=1)
        next_flow = await storage.create_next_instance(parent_flow, next_due)

        assert next_flow is not None
        assert next_flow.task == parent_flow.task
        assert next_flow.cron == parent_flow.cron
        assert next_flow.name == parent_flow.name
        assert next_flow.status == "pending"

    @pytest.mark.asyncio
    async def test_create_next_instance_non_recurring(self, storage, db_conn, clean_test_data):
        """Test that next instance is None for non-recurring flows."""
        thread_id = f"test_thread_{uuid.uuid4().hex[:8]}"
        now = datetime.now()

        # Create a non-recurring flow
        parent_flow = await storage.create(
            thread_id=thread_id,
            task="One-time task",
            flow="flow",
            due_time=now,
            cron=None,
        )

        # Try to create next instance
        next_flow = await storage.create_next_instance(parent_flow, now + timedelta(days=1))

        assert next_flow is None

    @pytest.mark.asyncio
    async def test_flow_lifecycle(self, storage, db_conn, clean_test_data):
        """Test complete flow lifecycle: create -> start -> complete -> next."""
        thread_id = f"test_thread_{uuid.uuid4().hex[:8]}"
        now = datetime.now()

        # Create recurring flow
        flow = await storage.create(
            thread_id=thread_id,
            task="Recurring task",
            flow="execute → log",
            due_time=now,
            cron="0 * * * *",  # Hourly
            name="Hourly Task",
        )

        assert flow.is_pending is True

        # Mark as started
        await storage.mark_started(flow.id)
        started_flow = await storage.get_by_id(flow.id)
        assert started_flow.is_running is True

        # Mark as completed with result
        await storage.mark_completed(flow.id, result="Task completed")
        completed_flow = await storage.get_by_id(flow.id)
        assert completed_flow.is_completed is True
        assert completed_flow.result == "Task completed"

        # Create next instance
        next_due = now + timedelta(hours=1)
        next_flow = await storage.create_next_instance(completed_flow, next_due)
        assert next_flow is not None
        assert next_flow.id != flow.id  # Different flow


# =============================================================================
# Global Storage Tests
# =============================================================================

class TestGlobalStorage:
    """Test global scheduled flow storage instance."""

    @pytest.mark.asyncio
    async def test_get_scheduled_flow_storage_singleton(self):
        """Test that get_scheduled_flow_storage returns same instance."""
        storage1 = await get_scheduled_flow_storage()
        storage2 = await get_scheduled_flow_storage()
        assert storage1 is storage2
