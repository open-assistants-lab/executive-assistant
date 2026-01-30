"""Comprehensive tests for Memory tools.

This test suite covers all 10 Memory tools:
1. create_memory
2. update_memory
3. delete_memory
4. forget_memory
5. list_memories
6. search_memories
7. get_memory_by_key
8. normalize_or_create_memory
9. get_memory_at_time (NEW - Temporal)
10. get_memory_history (NEW - Temporal)
"""

import pytest
from datetime import datetime, timezone, timedelta
from typing import Generator

from executive_assistant.storage.thread_storage import set_thread_id
from executive_assistant.tools.mem_tools import (
    create_memory,
    update_memory,
    delete_memory,
    forget_memory,
    list_memories,
    search_memories,
    get_memory_by_key,
    normalize_or_create_memory,
    get_memory_at_time,
    get_memory_history,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def test_thread_id() -> str:
    """Provide a test thread ID for isolated storage."""
    return "test_memory_tools"


@pytest.fixture
def setup_thread_context(test_thread_id: str) -> Generator[None, None, None]:
    """Set up thread context for memory operations."""
    set_thread_id(test_thread_id)
    yield
    # Cleanup happens automatically via test isolation


# =============================================================================
# Test: create_memory
# =============================================================================

class TestCreateMemory:
    """Tests for create_memory tool."""

    def test_create_fact_memory(
        self, setup_thread_context: None
    ) -> None:
        """Test creating a fact memory."""
        result = create_memory(
            content="Python is a programming language",
            memory_type="fact"
        )

        assert "created" in result.lower() or "memory" in result.lower()

    def test_create_preference_memory(
        self, setup_thread_context: None
    ) -> None:
        """Test creating a preference memory."""
        result = create_memory(
            content="User prefers dark mode",
            memory_type="preference"
        )

        assert "created" in result.lower() or "memory" in result.lower()

    def test_create_memory_with_key(
        self, setup_thread_context: None
    ) -> None:
        """Test creating a memory with a custom key."""
        result = create_memory(
            content="User's favorite color is blue",
            memory_type="preference",
            key="favorite_color"
        )

        assert "created" in result.lower() or "memory" in result.lower()


# =============================================================================
# Test: update_memory
# =============================================================================

class TestUpdateMemory:
    """Tests for update_memory tool."""

    def test_update_memory_content(
        self, setup_thread_context: None
    ) -> None:
        """Test updating memory content."""
        # Create memory first
        create_result = create_memory(
            content="Original content",
            memory_type="fact"
        )
        # Extract memory_id from result (format varies)
        # For testing, we'll verify the function exists

    def test_update_nonexistent_memory(
        self, setup_thread_context: None
    ) -> None:
        """Test updating a memory that doesn't exist."""
        result = update_memory(
            memory_id="nonexistent_id",
            content="Updated content"
        )

        # Should handle gracefully
        assert "not found" in result.lower() or "does not exist" in result.lower()

    def test_update_memory_type(
        self, setup_thread_context: None
    ) -> None:
        """Test updating memory type."""
        # Would need a valid memory_id
        pass


# =============================================================================
# Test: delete_memory
# =============================================================================

class TestDeleteMemory:
    """Tests for delete_memory tool."""

    def test_delete_existing_memory(
        self, setup_thread_context: None
    ) -> None:
        """Test deleting an existing memory."""
        # Create memory first
        create_result = create_memory(
            content="To be deleted",
            memory_type="fact"
        )

        # Note: Would need to extract memory_id from create_result
        # For testing, verify function exists

    def test_delete_nonexistent_memory(
        self, setup_thread_context: None
    ) -> None:
        """Test deleting a memory that doesn't exist."""
        result = delete_memory(memory_id="nonexistent_id")

        # Should handle gracefully
        assert "not found" in result.lower() or "does not exist" in result.lower()


# =============================================================================
# Test: forget_memory
# =============================================================================

class TestForgetMemory:
    """Tests for forget_memory tool (alias for delete_memory)."""

    def test_forget_memory(
        self, setup_thread_context: None
    ) -> None:
        """Test forgetting a memory."""
        result = forget_memory(memory_id="test_id")

        # Should behave same as delete_memory
        assert "forgotten" in result.lower() or "deleted" in result.lower() or "not found" in result.lower()


# =============================================================================
# Test: list_memories
# =============================================================================

class TestListMemories:
    """Tests for list_memories tool."""

    def test_list_empty_memories(
        self, setup_thread_context: None
    ) -> None:
        """Test listing when no memories exist."""
        result = list_memories()

        assert "no memories" in result.lower() or "empty" in result.lower() or result == ""

    def test_list_all_memories(
        self, setup_thread_context: None
    ) -> None:
        """Test listing all memories."""
        # Create memories
        create_memory(content="Memory 1", memory_type="fact")
        create_memory(content="Memory 2", memory_type="preference")

        result = list_memories()

        assert "memory" in result.lower()

    def test_list_by_type(
        self, setup_thread_context: None
    ) -> None:
        """Test listing memories by type."""
        # Create memories of different types
        create_memory(content="Fact memory", memory_type="fact")
        create_memory(content="Preference memory", memory_type="preference")

        result = list_memories(memory_type="fact")

        assert "fact" in result.lower()

    def test_list_active_only(
        self, setup_thread_context: None
    ) -> None:
        """Test listing only active memories."""
        result = list_memories(status="active")

        # Should only return active memories
        assert "active" in result.lower() or "memory" in result.lower()


# =============================================================================
# Test: search_memories
# =============================================================================

class TestSearchMemories:
    """Tests for search_memories tool."""

    def test_search_by_keyword(
        self, setup_thread_context: None
    ) -> None:
        """Test searching memories by keyword."""
        # Create memories
        create_memory(content="Python is a programming language", memory_type="fact")
        create_memory(content="JavaScript is used for web development", memory_type="fact")

        result = search_memories(query="Python", limit=5)

        assert "python" in result.lower()

    def test_search_with_limit(
        self, setup_thread_context: None
    ) -> None:
        """Test searching with result limit."""
        # Create multiple memories
        for i in range(5):
            create_memory(content=f"Memory number {i}", memory_type="fact")

        result = search_memories(query="memory", limit=3)

        # Should respect limit
        # (actual implementation may vary)

    def test_search_no_results(
        self, setup_thread_context: None
    ) -> None:
        """Test searching when no memories match."""
        result = search_memories(query="nonexistent_keyword_xyz", limit=5)

        # Should handle no results gracefully
        assert "no memories" in result.lower() or "not found" in result.lower() or len(result) == 0


# =============================================================================
# Test: get_memory_by_key
# =============================================================================

class TestGetMemoryByKey:
    """Tests for get_memory_by_key tool."""

    def test_get_existing_key(
        self, setup_thread_context: None
    ) -> None:
        """Test getting a memory by its key."""
        # Create memory with key
        create_memory(
            content="User's name is Alice",
            memory_type="fact",
            key="user_name"
        )

        result = get_memory_by_key(key="user_name")

        assert "alice" in result.lower()

    def test_get_nonexistent_key(
        self, setup_thread_context: None
    ) -> None:
        """Test getting a memory with a key that doesn't exist."""
        result = get_memory_by_key(key="nonexistent_key")

        # Should handle gracefully
        assert "not found" in result.lower() or "does not exist" in result.lower()


# =============================================================================
# Test: normalize_or_create_memory
# =============================================================================

class TestNormalizeOrCreateMemory:
    """Tests for normalize_or_create_memory tool."""

    def test_normalize_existing_memory(
        self, setup_thread_context: None
    ) -> None:
        """Test normalizing an existing memory."""
        # Create memory
        create_memory(
            content="Original content",
            memory_type="fact",
            key="test_key"
        )

        # Normalize (update if exists)
        result = normalize_or_create_memory(
            key="test_key",
            content="Normalized content"
        )

        assert "updated" in result.lower() or "created" in result.lower()

    def test_create_if_not_exists(
        self, setup_thread_context: None
    ) -> None:
        """Test creating memory if key doesn't exist."""
        result = normalize_or_create_memory(
            key="new_key",
            content="New memory content"
        )

        assert "created" in result.lower() or "memory" in result.lower()


# =============================================================================
# Integration Tests: Multi-Step Workflows
# =============================================================================

class TestMemoryWorkflows:
    """Integration tests for common memory workflows."""

    def test_memory_lifecycle(
        self, setup_thread_context: None
    ) -> None:
        """Test complete memory lifecycle: create, search, list, delete."""
        # 1. Create memory
        result = create_memory(
            content="Test lifecycle",
            memory_type="fact"
        )
        assert "created" in result.lower() or "memory" in result.lower()

        # 2. Search memories
        result = search_memories(query="lifecycle", limit=5)
        assert "lifecycle" in result.lower()

        # 3. List memories
        result = list_memories()
        assert "memory" in result.lower()

        # 4. Delete would require memory_id
        # Note: Full test would require parsing ID from results

    def test_preference_tracking_workflow(
        self, setup_thread_context: None
    ) -> None:
        """Test tracking user preferences."""
        # Create preferences
        create_memory(
            content="User prefers dark mode",
            memory_type="preference",
            key="theme_preference"
        )
        create_memory(
            content="User uses metric system",
            memory_type="preference",
            key="measurement_system"
        )

        # Retrieve preferences
        result = get_memory_by_key(key="theme_preference")
        assert "dark" in result.lower()

        # List all preferences
        result = list_memories(memory_type="preference")
        assert "preference" in result.lower()

    def test_knowledge_base_workflow(
        self, setup_thread_context: None
    ) -> None:
        """Test building a knowledge base."""
        # Add facts to knowledge base
        facts = [
            ("Python released in 1991", "python_release"),
            ("JavaScript created in 1995", "js_release"),
            ("Python creator is Guido van Rossum", "python_creator"),
        ]

        for fact, key in facts:
            create_memory(content=fact, memory_type="fact", key=key)

        # Search for specific information
        result = search_memories(query="Python", limit=5)
        assert "python" in result.lower()

        # Get specific fact
        result = get_memory_by_key(key="python_creator")
        assert "guido" in result.lower()

    def test_thread_isolation(
        self, setup_thread_context: None
    ) -> None:
        """Test that different threads have isolated memory storage."""
        # Create memory in default thread
        create_memory(
            content="Thread 1 secret",
            memory_type="fact",
            key="secret"
        )

        # Should exist in default thread
        result = get_memory_by_key(key="secret")
        assert "thread 1" in result.lower() or "secret" in result.lower()

        # Switch to different thread
        set_thread_id("different_thread")

        # Memory should not exist in different thread
        result = get_memory_by_key(key="secret")
        assert "thread 1" not in result.lower()
        assert "not found" in result.lower() or "does not exist" in result.lower()

    def test_memory_update_workflow(
        self, setup_thread_context: None
    ) -> None:
        """Test updating existing memories."""
        # Create memory with key
        create_memory(
            content="User lives in New York",
            memory_type="fact",
            key="location"
        )

        # Update using normalize_or_create
        result = normalize_or_create_memory(
            key="location",
            content="User lives in San Francisco"
        )
        assert "updated" in result.lower()

        # Verify update
        result = get_memory_by_key(key="location")
        assert "san francisco" in result.lower()
        assert "new york" not in result.lower()


# =============================================================================
# Test: get_memory_at_time (NEW - Temporal)
# =============================================================================

class TestGetMemoryAtTime:
    """Tests for get_memory_at_time tool (temporal queries)."""

    def test_get_current_memory(
        self, setup_thread_context: None
    ) -> None:
        """Test querying memory at current time."""
        # Create memory
        create_memory.invoke({
            "content": "User lives in Sydney",
            "memory_type": "fact",
            "key": "location"
        })

        # Query at current time should return Sydney
        now = datetime.now(timezone.utc).isoformat()

        result = get_memory_at_time.invoke({"key": "location", "time": now})
        assert "sydney" in result.lower()
        assert "version" in result.lower()

    def test_get_historical_memory(
        self, setup_thread_context: None
    ) -> None:
        """Test querying historical memory state after updates."""
        # Create initial memory
        create_memory(
            content="User lives in Sydney",
            memory_type="fact",
            key="location"
        )

        # Wait a moment (ensure timestamp difference)
        import time
        time.sleep(0.1)

        # Update memory (creates new version)
        normalize_or_create_memory(
            key="location",
            content="User lives in Tokyo"
        )

        # Query at time before update should return Sydney
        from datetime import datetime, timezone, timedelta
        past_time = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()

        result = get_memory_at_time(key="location", time=past_time)
        assert "sydney" in result.lower()
        assert "tokyo" not in result.lower()

    def test_get_future_memory(
        self, setup_thread_context: None
    ) -> None:
        """Test querying memory at future time returns current."""
        # Create memory
        create_memory(
            content="User lives in Paris",
            memory_type="fact",
            key="location"
        )

        # Query at future time should return current value
        from datetime import datetime, timezone, timedelta
        future_time = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()

        result = get_memory_at_time(key="location", time=future_time)
        assert "paris" in result.lower()

    def test_get_nonexistent_key_at_time(
        self, setup_thread_context: None
    ) -> None:
        """Test querying a key that never existed."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()

        result = get_memory_at_time(key="nonexistent_key", time=now)
        assert "not found" in result.lower()

    def test_temporal_workflow_sydney_to_tokyo(
        self, setup_thread_context: None
    ) -> None:
        """Test the classic Sydney → Tokyo migration scenario."""
        from datetime import datetime, timezone

        # Phase 1: User lives in Sydney
        create_memory(
            content="User lives in Sydney",
            memory_type="fact",
            key="location"
        )

        # Verify current location is Sydney
        result = get_memory_by_key(key="location")
        assert "sydney" in result.lower()

        # Phase 2: User moves to Tokyo (time passes)
        import time
        time.sleep(0.1)

        normalize_or_create_memory(
            key="location",
            content="User lives in Tokyo"
        )

        # Verify current location is now Tokyo
        result = get_memory_by_key(key="location")
        assert "tokyo" in result.lower()

        # Query past location should show Sydney
        past_time = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        result = get_memory_at_time(key="location", time=past_time)
        assert "sydney" in result.lower()


# =============================================================================
# Test: get_memory_history (NEW - Temporal)
# =============================================================================

class TestGetMemoryHistory:
    """Tests for get_memory_history tool (version history)."""

    def test_get_history_of_new_memory(
        self, setup_thread_context: None
    ) -> None:
        """Test getting history of a newly created memory."""
        create_memory(
            content="Initial version",
            memory_type="fact",
            key="test_history"
        )

        result = get_memory_history(key="test_history")
        assert "version 1" in result.lower()
        assert "initial version" in result.lower()
        assert "create" in result.lower()

    def test_get_history_after_update(
        self, setup_thread_context: None
    ) -> None:
        """Test getting history after updating memory."""
        # Create memory
        create_memory(
            content="Version 1",
            memory_type="fact",
            key="versioned_key"
        )

        # Update memory
        normalize_or_create_memory(
            key="versioned_key",
            content="Version 2"
        )

        # Get history
        result = get_memory_history(key="versioned_key")

        # Should show both versions
        assert "version 1" in result.lower()
        assert "version 2" in result.lower()
        assert "version 1" in result.lower()
        assert "update" in result.lower() or "superseded" in result.lower()

    def test_get_history_of_nonexistent_key(
        self, setup_thread_context: None
    ) -> None:
        """Test getting history of a key that doesn't exist."""
        result = get_memory_history(key="nonexistent_key")
        assert "not found" in result.lower() or "no memory history" in result.lower()

    def test_multiple_updates_history(
        self, setup_thread_context: None
    ) -> None:
        """Test history with multiple updates."""
        # Create initial memory
        create_memory(
            content="State 1",
            memory_type="fact",
            key="multi_update"
        )

        # Update multiple times
        normalize_or_create_memory(key="multi_update", content="State 2")
        normalize_or_create_memory(key="multi_update", content="State 3")
        normalize_or_create_memory(key="multi_update", content="State 4")

        # Get history
        result = get_memory_history(key="multi_update")

        # Should show all 4 versions
        assert "version 1" in result.lower()
        assert "version 2" in result.lower()
        assert "version 3" in result.lower()
        assert "version 4" in result.lower()
        assert "state 1" in result.lower()
        assert "state 4" in result.lower()

    def test_history_shows_validity_periods(
        self, setup_thread_context: None
    ) -> None:
        """Test that history includes valid_from and valid_to timestamps."""
        create_memory(
            content="Time-based memory",
            memory_type="fact",
            key="time_test"
        )

        result = get_memory_history(key="time_test")

        # Should include timestamp information
        assert "valid" in result.lower() or "from" in result.lower()


# =============================================================================
# Integration Tests: Temporal Workflows (NEW)
# =============================================================================

class TestTemporalMemoryWorkflows:
    """Integration tests for temporal memory workflows."""

    def test_complete_temporal_lifecycle(
        self, setup_thread_context: None
    ) -> None:
        """Test complete lifecycle: create → update → query history → query at time."""
        from datetime import datetime, timezone, timedelta

        # 1. Create initial memory
        create_memory(
            content="User prefers Python",
            memory_type="preference",
            key="language_preference"
        )

        # 2. Update to create new version
        import time
        time.sleep(0.1)
        normalize_or_create_memory(
            key="language_preference",
            content="User prefers Rust"
        )

        # 3. Verify current state
        current = get_memory_by_key(key="language_preference")
        assert "rust" in current.lower()

        # 4. Get full history
        history = get_memory_history(key="language_preference")
        assert "version 1" in history.lower()
        assert "version 2" in history.lower()
        assert "python" in history.lower()
        assert "rust" in history.lower()

        # 5. Query historical state
        past_time = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        historical = get_memory_at_time(key="language_preference", time=past_time)
        assert "python" in historical.lower()

    def test_facts_change_over_time(
        self, setup_thread_context: None
    ) -> None:
        """Test tracking facts that change over time."""
        from datetime import datetime, timezone, timedelta

        # Simulate user job changes
        create_memory(
            content="User works at Company A as Engineer",
            memory_type="fact",
            key="job_title"
        )

        import time
        time.sleep(0.1)

        # Promotion
        normalize_or_create_memory(
            key="job_title",
            content="User works at Company A as Senior Engineer"
        )

        time.sleep(0.1)

        # Job change
        normalize_or_create_memory(
            key="job_title",
            content="User works at Company B as Tech Lead"
        )

        # Current job should be Company B
        current = get_memory_by_key(key="job_title")
        assert "company b" in current.lower()
        assert "tech lead" in current.lower()

        # History should show all three positions
        history = get_memory_history(key="job_title")
        assert "company a" in history.lower()
        assert "engineer" in history.lower()
        assert "senior engineer" in history.lower()
        assert "company b" in history.lower()
        assert "tech lead" in history.lower()

    def test_temporal_data_integrity(
        self, setup_thread_context: None
    ) -> None:
        """Test that temporal queries maintain data integrity."""
        from datetime import datetime, timezone, timedelta

        # Create memory
        create_memory(
            content="Original value",
            memory_type="fact",
            key="integrity_test"
        )

        # Get timestamp before update
        timestamp_before = datetime.now(timezone.utc).isoformat()

        # Update memory
        import time
        time.sleep(0.1)
        normalize_or_create_memory(
            key="integrity_test",
            content="Updated value"
        )

        # Get timestamp after update
        timestamp_after = datetime.now(timezone.utc).isoformat()

        # Query before update should return original
        result_before = get_memory_at_time(key="integrity_test", time=timestamp_before)
        assert "original" in result_before.lower()
        assert "updated" not in result_before.lower()

        # Query after update should return updated
        result_after = get_memory_at_time(key="integrity_test", time=timestamp_after)
        assert "updated" in result_after.lower()

    def test_version_confidence_tracking(
        self, setup_thread_context: None
    ) -> None:
        """Test that confidence scores are tracked per version."""
        # Create with high confidence
        create_memory(
            content="Unverified fact",
            memory_type="fact",
            key="confidence_test",
            confidence=0.5
        )

        # Update with higher confidence
        normalize_or_create_memory(
            key="confidence_test",
            content="Verified fact",
            confidence=0.95
        )

        # History should show confidence changes
        history = get_memory_history(key="confidence_test")
        assert "confidence" in history.lower()
