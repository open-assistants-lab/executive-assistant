"""Tests for temporal memory functionality (versioning and point-in-time queries).

This test suite covers temporal memory features:
1. get_memory_at_time - Query memory at specific point in time
2. get_memory_history - Get full version history
3. Automatic versioning when updating keyed memories
4. Temporal data integrity
"""

import pytest
from datetime import datetime, timezone, timedelta
from typing import Generator

from executive_assistant.storage.thread_storage import set_thread_id
from executive_assistant.tools.mem_tools import (
    create_memory,
    normalize_or_create_memory,
    get_memory_by_key,
    get_memory_at_time,
    get_memory_history,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def test_thread_id() -> str:
    """Provide a test thread ID for isolated storage."""
    return "test_temporal_memory"


@pytest.fixture
def setup_thread_context(test_thread_id: str) -> Generator[None, None, None]:
    """Set up thread context for memory operations."""
    set_thread_id(test_thread_id)
    yield
    # Cleanup: delete all memories for this test thread
    import shutil
    from executive_assistant.config import settings
    mem_path = settings.get_thread_mem_path(test_thread_id)
    if mem_path.exists():
        mem_path.unlink()  # Delete the database file


# =============================================================================
# Test: get_memory_at_time
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

        # Add small delay to ensure memory is created before timestamp capture
        import time
        time.sleep(0.01)

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
        create_memory.invoke({
            "content": "User lives in Sydney",
            "memory_type": "fact",
            "key": "location"
        })

        # Ensure memory is committed, then capture timestamp
        import time
        time.sleep(0.01)
        timestamp_before_update = datetime.now(timezone.utc).isoformat()

        time.sleep(0.1)

        # Update memory (creates new version)
        normalize_or_create_memory.invoke({
            "key": "location",
            "content": "User lives in Tokyo"
        })

        # Query at time before update should return Sydney
        result = get_memory_at_time.invoke({"key": "location", "time": timestamp_before_update})
        assert "sydney" in result.lower()
        assert "tokyo" not in result.lower()

    def test_get_future_memory(
        self, setup_thread_context: None
    ) -> None:
        """Test querying memory at future time returns current."""
        # Create memory
        create_memory.invoke({
            "content": "User lives in Paris",
            "memory_type": "fact",
            "key": "location"
        })

        # Query at future time should return current value
        future_time = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()

        result = get_memory_at_time.invoke({"key": "location", "time": future_time})
        assert "paris" in result.lower()

    def test_get_nonexistent_key_at_time(
        self, setup_thread_context: None
    ) -> None:
        """Test querying a key that never existed."""
        now = datetime.now(timezone.utc).isoformat()

        result = get_memory_at_time.invoke({"key": "nonexistent_key", "time": now})
        assert "not found" in result.lower()

    def test_temporal_workflow_sydney_to_tokyo(
        self, setup_thread_context: None
    ) -> None:
        """Test the classic Sydney → Tokyo migration scenario."""
        # Phase 1: User lives in Sydney
        create_memory.invoke({
            "content": "User lives in Sydney",
            "memory_type": "fact",
            "key": "location"
        })

        # Ensure committed, then verify current location is Sydney
        import time
        time.sleep(0.01)
        result = get_memory_by_key.invoke({"key": "location"})
        assert "sydney" in result.lower()

        # Capture timestamp while still in Sydney
        timestamp_sydney = datetime.now(timezone.utc).isoformat()

        time.sleep(0.1)

        # Phase 2: User moves to Tokyo (time passes)
        normalize_or_create_memory.invoke({
            "key": "location",
            "content": "User lives in Tokyo"
        })

        # Verify current location is now Tokyo
        result = get_memory_by_key.invoke({"key": "location"})
        assert "tokyo" in result.lower()

        # Query at Sydney timestamp should show Sydney
        result = get_memory_at_time.invoke({"key": "location", "time": timestamp_sydney})
        assert "sydney" in result.lower()


# =============================================================================
# Test: get_memory_history
# =============================================================================

class TestGetMemoryHistory:
    """Tests for get_memory_history tool (version history)."""

    def test_get_history_of_new_memory(
        self, setup_thread_context: None
    ) -> None:
        """Test getting history of a newly created memory."""
        create_memory.invoke({
            "content": "Initial version",
            "memory_type": "fact",
            "key": "test_history"
        })

        result = get_memory_history.invoke({"key": "test_history"})
        assert "version 1" in result.lower()
        assert "initial version" in result.lower()
        assert "create" in result.lower()

    def test_get_history_after_update(
        self, setup_thread_context: None
    ) -> None:
        """Test getting history after updating memory."""
        # Create memory
        create_memory.invoke({
            "content": "Version 1",
            "memory_type": "fact",
            "key": "versioned_key"
        })

        # Update memory
        normalize_or_create_memory.invoke({
            "key": "versioned_key",
            "content": "Version 2"
        })

        # Get history
        result = get_memory_history.invoke({"key": "versioned_key"})

        # Should show both versions
        assert "version 1" in result.lower()
        assert "version 2" in result.lower()
        assert "update" in result.lower() or "superseded" in result.lower()

    def test_get_history_of_nonexistent_key(
        self, setup_thread_context: None
    ) -> None:
        """Test getting history of a key that doesn't exist."""
        result = get_memory_history.invoke({"key": "nonexistent_key"})
        assert "not found" in result.lower() or "no memory history" in result.lower()

    def test_multiple_updates_history(
        self, setup_thread_context: None
    ) -> None:
        """Test history with multiple updates."""
        # Create initial memory
        create_memory.invoke({
            "content": "State 1",
            "memory_type": "fact",
            "key": "multi_update"
        })

        # Update multiple times
        normalize_or_create_memory.invoke({"key": "multi_update", "content": "State 2"})
        normalize_or_create_memory.invoke({"key": "multi_update", "content": "State 3"})
        normalize_or_create_memory.invoke({"key": "multi_update", "content": "State 4"})

        # Get history
        result = get_memory_history.invoke({"key": "multi_update"})

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
        create_memory.invoke({
            "content": "Time-based memory",
            "memory_type": "fact",
            "key": "time_test"
        })

        result = get_memory_history.invoke({"key": "time_test"})

        # Should include timestamp information
        assert "valid" in result.lower() or "from" in result.lower()


# =============================================================================
# Integration Tests: Temporal Workflows
# =============================================================================

class TestTemporalMemoryWorkflows:
    """Integration tests for temporal memory workflows."""

    def test_complete_temporal_lifecycle(
        self, setup_thread_context: None
    ) -> None:
        """Test complete lifecycle: create → update → query history → query at time."""
        # 1. Create initial memory
        create_memory.invoke({
            "content": "User prefers Python",
            "memory_type": "preference",
            "key": "language_preference"
        })

        # Ensure committed and capture timestamp
        import time
        time.sleep(0.01)
        timestamp_python = datetime.now(timezone.utc).isoformat()

        time.sleep(0.1)

        # 2. Update to create new version
        normalize_or_create_memory.invoke({
            "key": "language_preference",
            "content": "User prefers Rust"
        })

        # 3. Verify current state
        current = get_memory_by_key.invoke({"key": "language_preference"})
        assert "rust" in current.lower()

        # 4. Get full history
        history = get_memory_history.invoke({"key": "language_preference"})
        assert "version 1" in history.lower()
        assert "version 2" in history.lower()
        assert "python" in history.lower()
        assert "rust" in history.lower()

        # 5. Query historical state
        historical = get_memory_at_time.invoke({"key": "language_preference", "time": timestamp_python})
        assert "python" in historical.lower()

    def test_facts_change_over_time(
        self, setup_thread_context: None
    ) -> None:
        """Test tracking facts that change over time."""
        # Simulate user job changes
        create_memory.invoke({
            "content": "User works at Company A as Engineer",
            "memory_type": "fact",
            "key": "job_title"
        })

        import time
        time.sleep(0.1)

        # Promotion
        normalize_or_create_memory.invoke({
            "key": "job_title",
            "content": "User works at Company A as Senior Engineer"
        })

        time.sleep(0.1)

        # Job change
        normalize_or_create_memory.invoke({
            "key": "job_title",
            "content": "User works at Company B as Tech Lead"
        })

        # Current job should be Company B
        current = get_memory_by_key.invoke({"key": "job_title"})
        assert "company b" in current.lower()
        assert "tech lead" in current.lower()

        # History should show all three positions
        history = get_memory_history.invoke({"key": "job_title"})
        assert "company a" in history.lower()
        assert "engineer" in history.lower()
        assert "senior engineer" in history.lower()
        assert "company b" in history.lower()
        assert "tech lead" in history.lower()

    def test_temporal_data_integrity(
        self, setup_thread_context: None
    ) -> None:
        """Test that temporal queries maintain data integrity."""
        # Create memory
        create_memory.invoke({
            "content": "Original value",
            "memory_type": "fact",
            "key": "integrity_test"
        })

        # Ensure committed before capturing timestamp
        import time
        time.sleep(0.01)
        timestamp_before = datetime.now(timezone.utc).isoformat()

        time.sleep(0.1)

        # Update memory
        normalize_or_create_memory.invoke({
            "key": "integrity_test",
            "content": "Updated value"
        })

        # Ensure committed before capturing timestamp
        time.sleep(0.01)
        timestamp_after = datetime.now(timezone.utc).isoformat()

        # Query before update should return original
        result_before = get_memory_at_time.invoke({"key": "integrity_test", "time": timestamp_before})
        assert "original" in result_before.lower()
        assert "updated" not in result_before.lower()

        # Query after update should return updated
        result_after = get_memory_at_time.invoke({"key": "integrity_test", "time": timestamp_after})
        assert "updated" in result_after.lower()

    def test_version_confidence_tracking(
        self, setup_thread_context: None
    ) -> None:
        """Test that confidence scores are tracked per version."""
        # Create with low confidence
        create_memory.invoke({
            "content": "Unverified fact",
            "memory_type": "fact",
            "key": "confidence_test",
            "confidence": 0.5
        })

        # Update with higher confidence
        normalize_or_create_memory.invoke({
            "key": "confidence_test",
            "content": "Verified fact",
            "confidence": 0.95
        })

        # History should show confidence changes
        history = get_memory_history.invoke({"key": "confidence_test"})
        assert "confidence" in history.lower()

    def test_temporal_query_accuracy(
        self, setup_thread_context: None
    ) -> None:
        """Test temporal queries return accurate historical states."""
        import time

        # Create initial memory
        create_memory.invoke({
            "content": "Value A",
            "memory_type": "fact",
            "key": "temporal_accuracy"
        })

        # Ensure memory is committed before capturing timestamp
        time.sleep(0.01)
        timestamp_a = datetime.now(timezone.utc).isoformat()

        time.sleep(0.1)

        # First update
        normalize_or_create_memory.invoke({
            "key": "temporal_accuracy",
            "content": "Value B"
        })

        # Ensure update is committed before capturing timestamp
        time.sleep(0.01)
        timestamp_b = datetime.now(timezone.utc).isoformat()

        time.sleep(0.1)

        # Second update
        normalize_or_create_memory.invoke({
            "key": "temporal_accuracy",
            "content": "Value C"
        })

        # Query at timestamp A should return Value A
        result_a = get_memory_at_time.invoke({"key": "temporal_accuracy", "time": timestamp_a})
        assert "value a" in result_a.lower()
        assert "value b" not in result_a.lower()

        # Query at timestamp B should return Value B
        result_b = get_memory_at_time.invoke({"key": "temporal_accuracy", "time": timestamp_b})
        assert "value b" in result_b.lower()
        assert "value a" not in result_b.lower()

        # Current value should be Value C
        result_current = get_memory_by_key.invoke({"key": "temporal_accuracy"})
        assert "value c" in result_current.lower()
