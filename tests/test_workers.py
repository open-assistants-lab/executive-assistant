"""Unit tests for Worker storage."""

import asyncio
import pytest

pytest.skip("Worker agents are archived.", allow_module_level=True)

from datetime import datetime

from cassey.storage.workers import Worker, WorkerStorage, get_worker_storage


@pytest.fixture
async def clean_db():
    """Provide a clean database state for each test."""
    storage = WorkerStorage()
    # Note: This would require actual database cleanup in a real setup
    # For now, tests will use unique identifiers
    yield storage


class TestWorkerStorage:
    """Test WorkerStorage CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_worker(self, clean_db):
        """Test creating a new worker."""
        worker = await clean_db.create(
            user_id="test_user",
            thread_id="telegram:test_thread",
            name="test_worker",
            tools=["execute_python", "read_file"],
            prompt="You are a test worker.",
        )

        assert worker.id > 0
        assert worker.user_id == "test_user"
        assert worker.thread_id == "telegram:test_thread"
        assert worker.name == "test_worker"
        assert worker.tools == ["execute_python", "read_file"]
        assert worker.prompt == "You are a test worker."
        assert worker.status == "active"
        assert worker.is_active

    @pytest.mark.asyncio
    async def test_get_worker_by_id(self, clean_db):
        """Test retrieving a worker by ID."""
        created = await clean_db.create(
            user_id="test_user",
            thread_id="telegram:test_thread",
            name="test_worker",
            tools=["execute_python"],
            prompt="Test prompt",
        )

        retrieved = await clean_db.get_by_id(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.name == "test_worker"

    @pytest.mark.asyncio
    async def test_get_worker_by_id_not_found(self, clean_db):
        """Test retrieving non-existent worker returns None."""
        worker = await clean_db.get_by_id(99999)
        assert worker is None

    @pytest.mark.asyncio
    async def test_list_workers_by_user(self, clean_db):
        """Test listing workers filtered by user."""
        user_id = "test_user_list"

        # Create multiple workers
        await clean_db.create(
            user_id=user_id,
            thread_id="telegram:thread1",
            name="worker1",
            tools=["execute_python"],
            prompt="Prompt 1",
        )
        await clean_db.create(
            user_id=user_id,
            thread_id="telegram:thread2",
            name="worker2",
            tools=["read_file"],
            prompt="Prompt 2",
        )
        # Worker for different user
        await clean_db.create(
            user_id="other_user",
            thread_id="telegram:thread3",
            name="worker3",
            tools=["write_file"],
            prompt="Prompt 3",
        )

        workers = await clean_db.list_by_user(user_id)

        assert len(workers) == 2
        assert all(w.user_id == user_id for w in workers)
        names = [w.name for w in workers]
        assert "worker1" in names
        assert "worker2" in names
        assert "worker3" not in names

    @pytest.mark.asyncio
    async def test_list_workers_by_user_with_status(self, clean_db):
        """Test listing workers filtered by user and status."""
        user_id = "test_user_status"

        await clean_db.create(
            user_id=user_id,
            thread_id="telegram:thread1",
            name="active_worker",
            tools=["execute_python"],
            prompt="Active worker",
        )
        worker2 = await clean_db.create(
            user_id=user_id,
            thread_id="telegram:thread2",
            name="archived_worker",
            tools=["read_file"],
            prompt="Archived worker",
        )
        await clean_db.archive(worker2.id)

        active_workers = await clean_db.list_by_user(user_id, status="active")
        archived_workers = await clean_db.list_by_user(user_id, status="archived")

        assert len(active_workers) == 1
        assert active_workers[0].name == "active_worker"
        assert len(archived_workers) == 1
        assert archived_workers[0].name == "archived_worker"

    @pytest.mark.asyncio
    async def test_list_workers_by_thread(self, clean_db):
        """Test listing workers filtered by thread."""
        thread_id = "telegram:test_thread_list"

        await clean_db.create(
            user_id="user1",
            thread_id=thread_id,
            name="worker1",
            tools=["execute_python"],
            prompt="Prompt 1",
        )
        await clean_db.create(
            user_id="user1",
            thread_id=thread_id,
            name="worker2",
            tools=["read_file"],
            prompt="Prompt 2",
        )
        await clean_db.create(
            user_id="user1",
            thread_id="telegram:other_thread",
            name="worker3",
            tools=["write_file"],
            prompt="Prompt 3",
        )

        workers = await clean_db.list_by_thread(thread_id)

        assert len(workers) == 2
        assert all(w.thread_id == thread_id for w in workers)

    @pytest.mark.asyncio
    async def test_archive_worker(self, clean_db):
        """Test archiving a worker."""
        worker = await clean_db.create(
            user_id="test_user",
            thread_id="telegram:test_thread",
            name="test_worker",
            tools=["execute_python"],
            prompt="Test prompt",
        )

        success = await clean_db.archive(worker.id)

        assert success is True

        archived = await clean_db.get_by_id(worker.id)
        assert archived is not None
        assert archived.status == "archived"
        assert archived.is_active is False
        assert archived.archived_at is not None

    @pytest.mark.asyncio
    async def test_archive_already_archived_worker(self, clean_db):
        """Test archiving an already archived worker."""
        worker = await clean_db.create(
            user_id="test_user",
            thread_id="telegram:test_thread",
            name="test_worker",
            tools=["execute_python"],
            prompt="Test prompt",
        )
        await clean_db.archive(worker.id)

        # Try to archive again
        success = await clean_db.archive(worker.id)

        # Should return False because worker is no longer active
        assert success is False

    @pytest.mark.asyncio
    async def test_delete_worker(self, clean_db):
        """Test hard deleting a worker."""
        worker = await clean_db.create(
            user_id="test_user",
            thread_id="telegram:test_thread",
            name="test_worker",
            tools=["execute_python"],
            prompt="Test prompt",
        )

        success = await clean_db.delete(worker.id)

        assert success is True

        deleted = await clean_db.get_by_id(worker.id)
        assert deleted is None

    @pytest.mark.asyncio
    async def test_delete_non_existent_worker(self, clean_db):
        """Test deleting a non-existent worker."""
        success = await clean_db.delete(99999)
        assert success is False


class TestWorkerDataclass:
    """Test Worker dataclass properties."""

    def test_worker_is_active(self):
        """Test is_active property."""
        worker = Worker(
            id=1,
            user_id="user",
            thread_id="thread",
            name="worker",
            tools=["execute_python"],
            prompt="Prompt",
            status="active",
            created_at=datetime.now(),
            archived_at=None,
        )
        assert worker.is_active is True

    def test_worker_is_not_active(self):
        """Test is_active property for non-active status."""
        worker = Worker(
            id=1,
            user_id="user",
            thread_id="thread",
            name="worker",
            tools=["execute_python"],
            prompt="Prompt",
            status="archived",
            created_at=datetime.now(),
            archived_at=datetime.now(),
        )
        assert worker.is_active is False


@pytest.mark.asyncio
async def test_get_worker_storage_singleton():
    """Test that get_worker_storage returns a singleton instance."""
    storage1 = await get_worker_storage()
    storage2 = await get_worker_storage()

    assert storage1 is storage2
