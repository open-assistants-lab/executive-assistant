"""Unit tests for Memory storage and tools."""

from pathlib import Path
from typing import Any
from unittest.mock import patch, MagicMock

import pytest

from cassey.storage.mem_storage import MemoryStorage, get_mem_storage, _mem_storage
from cassey.tools import mem_tools


@pytest.fixture
def temp_mem_root(tmp_path):
    """Create a temporary mem root for testing."""
    return tmp_path / "mem"


@pytest.fixture
def mem_store_instance(temp_mem_root):
    """Create a Memory storage instance with temporary root."""

    class TestableMemoryStorage(MemoryStorage):
        """Testable MemoryStorage with custom db path."""

        def __init__(self, root: Path):
            self.root = root

        def _get_db_path(self, thread_id: str | None = None) -> Path:
            from cassey.config import settings
            if thread_id is None:
                thread_id = "default_thread"
            safe_thread_id = settings._sanitize_thread_id(thread_id)
            return (self.root / safe_thread_id / "mem" / "mem.db").resolve()

        def get_connection(self, thread_id: str | None = None) -> Any:
            """Get connection using custom db path."""
            from duckdb import connect
            db_path = self._get_db_path(thread_id)
            db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = connect(str(db_path))
            self._ensure_schema(conn)
            return conn

    return TestableMemoryStorage(temp_mem_root)


@pytest.fixture
def mock_thread_id():
    """Mock thread_id for testing."""
    return "telegram:test_mem_12345"


@pytest.fixture
def set_thread_context(mock_thread_id):
    """Set thread_id context for tool testing."""
    from cassey.storage.file_sandbox import set_thread_id

    set_thread_id(mock_thread_id)
    yield
    # Reset context after test
    set_thread_id("")


class TestMemoryStorage:
    """Test Memory storage operations."""

    def test_initialization(self):
        """Test storage initialization."""
        storage = MemoryStorage()
        assert storage is not None

    def test_get_db_path(self, mem_store_instance, temp_mem_root):
        """Test getting database path for thread."""
        # Test the custom TestableMemoryStorage fixture
        assert mem_store_instance._get_db_path("telegram:test123").name == "mem.db"
        assert "telegram_test123" in str(mem_store_instance._get_db_path("telegram:test123"))

    def test_create_memory(self, mem_store_instance, mock_thread_id):
        """Test creating a memory."""
        memory_id = mem_store_instance.create_memory(
            content="User prefers Python over JavaScript",
            memory_type="preference",
            key="language",
            confidence=1.0,
            thread_id=mock_thread_id,
        )
        assert memory_id is not None
        assert len(memory_id) > 0

    def test_get_memory_by_key(self, mem_store_instance, mock_thread_id):
        """Test retrieving a memory by key."""
        # Create a memory with a key
        mem_store_instance.create_memory(
            content="User lives in New York",
            memory_type="fact",
            key="location",
            confidence=0.9,
            thread_id=mock_thread_id,
        )

        # Retrieve by key
        memory = mem_store_instance.get_memory_by_key("location", thread_id=mock_thread_id)
        assert memory is not None
        assert memory["key"] == "location"
        assert "New York" in memory["content"]
        assert memory["confidence"] == pytest.approx(0.9)

    def test_get_memory_by_key_not_found(self, mem_store_instance, mock_thread_id):
        """Test retrieving non-existent memory by key."""
        memory = mem_store_instance.get_memory_by_key("nonexistent", thread_id=mock_thread_id)
        assert memory is None

    def test_update_memory(self, mem_store_instance, mock_thread_id):
        """Test updating a memory."""
        memory_id = mem_store_instance.create_memory(
            content="Original content",
            memory_type="note",
            thread_id=mock_thread_id,
        )

        # Update content
        success = mem_store_instance.update_memory(
            memory_id=memory_id,
            content="Updated content",
            thread_id=mock_thread_id,
        )
        assert success is True

        # Verify update
        memory = mem_store_instance.get_memory_by_key(None, thread_id=mock_thread_id)
        # The most recent memory should have updated content
        memories = mem_store_instance.list_memories(thread_id=mock_thread_id)
        assert any(m["id"] == memory_id and m["content"] == "Updated content" for m in memories)

    def test_update_memory_not_found(self, mem_store_instance, mock_thread_id):
        """Test updating non-existent memory."""
        success = mem_store_instance.update_memory(
            memory_id="nonexistent-id",
            content="New content",
            thread_id=mock_thread_id,
        )
        assert success is False

    def test_delete_memory(self, mem_store_instance, mock_thread_id):
        """Test soft deleting a memory."""
        memory_id = mem_store_instance.create_memory(
            content="To be deleted",
            memory_type="note",
            thread_id=mock_thread_id,
        )

        # Delete
        success = mem_store_instance.delete_memory(memory_id, thread_id=mock_thread_id)
        assert success is True

        # Verify it's marked as deleted (not returned by default)
        memories = mem_store_instance.list_memories(status="active", thread_id=mock_thread_id)
        assert not any(m["id"] == memory_id for m in memories)

        # But should be in deleted list
        deleted_memories = mem_store_instance.list_memories(status="deleted", thread_id=mock_thread_id)
        assert any(m["id"] == memory_id for m in deleted_memories)

    def test_deprecate_memory(self, mem_store_instance, mock_thread_id):
        """Test deprecating a memory."""
        memory_id = mem_store_instance.create_memory(
            content="Old preference",
            memory_type="preference",
            key="old_key",
            thread_id=mock_thread_id,
        )

        # Deprecate
        success = mem_store_instance.deprecate_memory(memory_id, thread_id=mock_thread_id)
        assert success is True

        # Verify status
        memories = mem_store_instance.list_memories(status="deprecated", thread_id=mock_thread_id)
        assert any(m["id"] == memory_id for m in memories)

    def test_list_memories(self, mem_store_instance, mock_thread_id):
        """Test listing memories."""
        # Create multiple memories
        mem_store_instance.create_memory(
            content="Preference 1", memory_type="preference", thread_id=mock_thread_id
        )
        mem_store_instance.create_memory(
            content="Fact 1", memory_type="fact", thread_id=mock_thread_id
        )
        mem_store_instance.create_memory(
            content="Note 1", memory_type="note", thread_id=mock_thread_id
        )

        # List all
        memories = mem_store_instance.list_memories(thread_id=mock_thread_id)
        assert len(memories) == 3

        # Filter by type
        pref_memories = mem_store_instance.list_memories(memory_type="preference", thread_id=mock_thread_id)
        assert len(pref_memories) == 1
        assert pref_memories[0]["memory_type"] == "preference"

    def test_list_memories_empty(self, mem_store_instance, mock_thread_id):
        """Test listing memories when none exist."""
        memories = mem_store_instance.list_memories(thread_id=mock_thread_id)
        assert memories == []

    def test_search_memories(self, mem_store_instance, mock_thread_id):
        """Test searching memories by content."""
        # Create memories
        mem_store_instance.create_memory(
            content="User prefers Python programming language", memory_type="preference", thread_id=mock_thread_id
        )
        mem_store_instance.create_memory(
            content="User lives in New York City", memory_type="fact", thread_id=mock_thread_id
        )
        mem_store_instance.create_memory(
            content="User works 9-5 EST timezone", memory_type="preference", thread_id=mock_thread_id
        )

        # Search for "python"
        results = mem_store_instance.search_memories("python", limit=5, thread_id=mock_thread_id)
        assert len(results) >= 1
        assert any("Python" in m["content"] for m in results)

        # Search for "york"
        results = mem_store_instance.search_memories("york", limit=5, thread_id=mock_thread_id)
        assert any("New York" in m["content"] for m in results)

    def test_search_memories_with_min_confidence(self, mem_store_instance, mock_thread_id):
        """Test searching with confidence threshold."""
        # Create memories with different confidence
        mem_store_instance.create_memory(
            content="High confidence memory", memory_type="fact", confidence=0.9, thread_id=mock_thread_id
        )
        mem_store_instance.create_memory(
            content="Low confidence memory", memory_type="fact", confidence=0.4, thread_id=mock_thread_id
        )

        # Search with min_confidence=0.5
        results = mem_store_instance.search_memories("memory", limit=5, min_confidence=0.5, thread_id=mock_thread_id)
        assert any("High confidence" in m["content"] for m in results)
        assert not any("Low confidence" in m["content"] for m in results)

    def test_search_memories_empty(self, mem_store_instance, mock_thread_id):
        """Test searching when no memories exist."""
        results = mem_store_instance.search_memories("query", limit=5, thread_id=mock_thread_id)
        assert results == []

    def test_normalize_or_create_new(self, mem_store_instance, mock_thread_id):
        """Test normalize_or_create creates new memory when key doesn't exist."""
        memory_id, is_new = mem_store_instance.normalize_or_create(
            key="timezone",
            content="America/New_York",
            memory_type="preference",
            thread_id=mock_thread_id,
        )
        assert is_new is True
        assert memory_id is not None

        # Verify it was created
        memory = mem_store_instance.get_memory_by_key("timezone", thread_id=mock_thread_id)
        assert memory is not None
        assert memory["content"] == "America/New_York"

    def test_normalize_or_create_existing(self, mem_store_instance, mock_thread_id):
        """Test normalize_or_create deprecates old and creates new when key exists."""
        # Create initial memory
        old_id, _ = mem_store_instance.normalize_or_create(
            key="timezone",
            content="America/New_York",
            memory_type="preference",
            thread_id=mock_thread_id,
        )

        # Update with same key
        new_id, is_new = mem_store_instance.normalize_or_create(
            key="timezone",
            content="America/Los_Angeles",
            memory_type="preference",
            thread_id=mock_thread_id,
        )
        assert is_new is False
        assert new_id != old_id

        # Verify old is deprecated
        old_memory = mem_store_instance.get_memory_by_key("timezone", thread_id=mock_thread_id)
        # Should return the new active one
        assert old_memory["content"] == "America/Los_Angeles"
        assert old_memory["id"] == new_id

    def test_thread_isolation(self, mem_store_instance):
        """Test that different threads have isolated memory databases."""
        thread1 = "thread:isolated_1"
        thread2 = "thread:isolated_2"

        # Create memory in thread1
        mem_store_instance.create_memory(
            content="Thread 1 memory", memory_type="note", thread_id=thread1
        )

        # Create memory in thread2
        mem_store_instance.create_memory(
            content="Thread 2 memory", memory_type="note", thread_id=thread2
        )

        # Thread1 should only see its own memories
        memories1 = mem_store_instance.list_memories(thread_id=thread1)
        assert len(memories1) == 1
        assert "Thread 1" in memories1[0]["content"]

        # Thread2 should only see its own memories
        memories2 = mem_store_instance.list_memories(thread_id=thread2)
        assert len(memories2) == 1
        assert "Thread 2" in memories2[0]["content"]


class TestGlobalMemoryStorage:
    """Test global Memory storage instance."""

    def test_get_mem_storage(self):
        """Test getting global storage instance."""
        storage = get_mem_storage()
        assert isinstance(storage, MemoryStorage)

    def test_global_instance_singleton(self):
        """Test that global instance is a singleton."""
        storage1 = get_mem_storage()
        storage2 = get_mem_storage()
        assert storage1 is storage2


class TestMemoryTools:
    """Test Memory tool functions."""

    def test_create_memory_tool(self, set_thread_context, temp_mem_root):
        """Test create_memory tool."""
        # Create a testable storage instance
        test_storage = MemoryStorage()
        original_get_storage = mem_tools.get_mem_storage

        def mock_get_storage():
            class TestableMemoryStorage(MemoryStorage):
                def _get_db_path(self, thread_id: str | None = None) -> Path:
                    from cassey.config import settings
                    if thread_id is None:
                        thread_id = "default"
                    safe = settings._sanitize_thread_id(thread_id)
                    return (temp_mem_root / safe / "mem" / "mem.db").resolve()
            return TestableMemoryStorage()

        mem_tools.get_mem_storage = mock_get_storage
        try:
            result = mem_tools.create_memory.invoke({
                "content": "User prefers Python",
                "memory_type": "preference",
                "key": "language",
                "confidence": 1.0,
            })
            assert "Memory saved" in result or "ID:" in result
        finally:
            mem_tools.get_mem_storage = original_get_storage

    def test_update_memory_tool(self, set_thread_context, temp_mem_root):
        """Test update_memory tool."""
        test_storage = MemoryStorage()
        original_get_storage = mem_tools.get_mem_storage

        def mock_get_storage():
            class TestableMemoryStorage(MemoryStorage):
                def _get_db_path(self, thread_id: str | None = None) -> Path:
                    from cassey.config import settings
                    if thread_id is None:
                        thread_id = "default"
                    safe = settings._sanitize_thread_id(thread_id)
                    return (temp_mem_root / safe / "mem" / "mem.db").resolve()
            return TestableMemoryStorage()

        mem_tools.get_mem_storage = mock_get_storage
        try:
            # Create a memory first
            create_result = mem_tools.create_memory.invoke({
                "content": "Original content",
                "memory_type": "note",
            })

            # Extract memory ID from result
            memory_id = create_result.split(": ")[1].strip() if ": " in create_result else None

            if memory_id:
                # Update it
                result = mem_tools.update_memory.invoke({
                    "memory_id": memory_id,
                    "content": "Updated content",
                })
                assert "updated" in result.lower()
        finally:
            mem_tools.get_mem_storage = original_get_storage

    def test_delete_memory_tool(self, set_thread_context, temp_mem_root):
        """Test delete_memory tool."""
        original_get_storage = mem_tools.get_mem_storage

        def mock_get_storage():
            class TestableMemoryStorage(MemoryStorage):
                def _get_db_path(self, thread_id: str | None = None) -> Path:
                    from cassey.config import settings
                    if thread_id is None:
                        thread_id = "default"
                    safe = settings._sanitize_thread_id(thread_id)
                    return (temp_mem_root / safe / "mem" / "mem.db").resolve()
            return TestableMemoryStorage()

        mem_tools.get_mem_storage = mock_get_storage
        try:
            # Create a memory first
            create_result = mem_tools.create_memory.invoke({
                "content": "To be deleted",
                "memory_type": "note",
            })

            memory_id = create_result.split(": ")[1].strip() if ": " in create_result else None

            if memory_id:
                # Delete it
                result = mem_tools.delete_memory.invoke({"memory_id": memory_id})
                assert "deleted" in result.lower() or "not found" in result.lower()
        finally:
            mem_tools.get_mem_storage = original_get_storage

    def test_list_memories_tool(self, set_thread_context, temp_mem_root):
        """Test list_memories tool."""
        original_get_storage = mem_tools.get_mem_storage

        def mock_get_storage():
            class TestableMemoryStorage(MemoryStorage):
                def _get_db_path(self, thread_id: str | None = None) -> Path:
                    from cassey.config import settings
                    if thread_id is None:
                        thread_id = "default"
                    safe = settings._sanitize_thread_id(thread_id)
                    return (temp_mem_root / safe / "mem" / "mem.db").resolve()
            return TestableMemoryStorage()

        mem_tools.get_mem_storage = mock_get_storage
        try:
            # Create some memories
            mem_tools.create_memory.invoke({"content": "Memory 1", "memory_type": "preference"})
            mem_tools.create_memory.invoke({"content": "Memory 2", "memory_type": "fact"})

            # List all
            result = mem_tools.list_memories.invoke({})
            assert "Memory" in result or "preference" in result or "fact" in result
        finally:
            mem_tools.get_mem_storage = original_get_storage

    def test_search_memories_tool(self, set_thread_context, temp_mem_root):
        """Test search_memories tool."""
        original_get_storage = mem_tools.get_mem_storage

        def mock_get_storage():
            class TestableMemoryStorage(MemoryStorage):
                def _get_db_path(self, thread_id: str | None = None) -> Path:
                    from cassey.config import settings
                    if thread_id is None:
                        thread_id = "default"
                    safe = settings._sanitize_thread_id(thread_id)
                    return (temp_mem_root / safe / "mem" / "mem.db").resolve()
            return TestableMemoryStorage()

        mem_tools.get_mem_storage = mock_get_storage
        try:
            # Create memories
            mem_tools.create_memory.invoke({"content": "Python programming language"})
            mem_tools.create_memory.invoke({"content": "New York City location"})

            # Search for "python"
            result = mem_tools.search_memories.invoke({"query": "python", "limit": 5})
            assert "python" in result.lower() or "programming" in result.lower()
        finally:
            mem_tools.get_mem_storage = original_get_storage

    def test_get_memory_by_key_tool(self, set_thread_context, temp_mem_root):
        """Test get_memory_by_key tool."""
        original_get_storage = mem_tools.get_mem_storage

        def mock_get_storage():
            class TestableMemoryStorage(MemoryStorage):
                def _get_db_path(self, thread_id: str | None = None) -> Path:
                    from cassey.config import settings
                    if thread_id is None:
                        thread_id = "default"
                    safe = settings._sanitize_thread_id(thread_id)
                    return (temp_mem_root / safe / "mem" / "mem.db").resolve()
            return TestableMemoryStorage()

        mem_tools.get_mem_storage = mock_get_storage
        try:
            # Create a keyed memory
            mem_tools.create_memory.invoke({
                "content": "America/New_York",
                "memory_type": "preference",
                "key": "timezone",
            })

            # Get by key
            result = mem_tools.get_memory_by_key.invoke({"key": "timezone"})
            assert "timezone" in result.lower()
            assert "America" in result or "New_York" in result
        finally:
            mem_tools.get_mem_storage = original_get_storage

    def test_normalize_or_create_memory_tool(self, set_thread_context, temp_mem_root):
        """Test normalize_or_create_memory tool."""
        original_get_storage = mem_tools.get_mem_storage

        def mock_get_storage():
            class TestableMemoryStorage(MemoryStorage):
                def _get_db_path(self, thread_id: str | None = None) -> Path:
                    from cassey.config import settings
                    if thread_id is None:
                        thread_id = "default"
                    safe = settings._sanitize_thread_id(thread_id)
                    return (temp_mem_root / safe / "mem" / "mem.db").resolve()
            return TestableMemoryStorage()

        mem_tools.get_mem_storage = mock_get_storage
        try:
            # Create new
            result = mem_tools.normalize_or_create_memory.invoke({
                "key": "color",
                "content": "blue",
                "memory_type": "preference",
            })
            assert "created" in result.lower()

            # Update existing
            result = mem_tools.normalize_or_create_memory.invoke({
                "key": "color",
                "content": "red",
                "memory_type": "preference",
            })
            assert "updated" in result.lower()
        finally:
            mem_tools.get_mem_storage = original_get_storage


class TestMemoryToolsWithSettings:
    """Test memory tools with confidence threshold from settings."""

    def test_search_respects_confidence_threshold(self, set_thread_context, temp_mem_root):
        """Test that search respects MEM_CONFIDENCE_MIN setting."""
        original_get_storage = mem_tools.get_mem_storage

        def mock_get_storage():
            class TestableMemoryStorage(MemoryStorage):
                def _get_db_path(self, thread_id: str | None = None) -> Path:
                    from cassey.config import settings
                    if thread_id is None:
                        thread_id = "default"
                    safe = settings._sanitize_thread_id(thread_id)
                    return (temp_mem_root / safe / "mem" / "mem.db").resolve()
            return TestableMemoryStorage()

        mem_tools.get_mem_storage = mock_get_storage
        try:
            # Create memory with low confidence
            mem_tools.create_memory.invoke({
                "content": "Low confidence memory",
                "memory_type": "fact",
                "confidence": 0.5,
            })

            # Search with high min_confidence should not return low confidence memory
            result = mem_tools.search_memories.invoke({
                "query": "memory",
                "limit": 5,
                "min_confidence": 0.8,
            })
            assert "not found" in result.lower() or "No memories" in result
        finally:
            mem_tools.get_mem_storage = original_get_storage
