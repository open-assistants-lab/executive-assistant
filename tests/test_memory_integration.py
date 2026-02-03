"""Integration test for memory retrieval fix.

This test demonstrates that profile memories are now correctly retrieved
in new conversations, fixing the bug where semantic search failed to match
profile content with general queries.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from executive_assistant.channels.base import BaseChannel
from executive_assistant.storage.mem_storage import MemoryStorage


class MockChannel(BaseChannel):
    """Mock channel for testing."""

    async def start(self):
        pass

    async def stop(self):
        pass

    async def send_message(self, conversation_id: str, content: str, **kwargs):
        pass

    async def handle_message(self, message):
        """Mock handle_message implementation."""
        pass


class TestMemoryIntegration:
    """Integration tests for memory retrieval fix."""

    @pytest.fixture
    def temp_mem_db(self, tmp_path):
        """Create a temporary memory database for testing."""
        from executive_assistant.config import settings

        # Create temp directory structure
        temp_root = tmp_path / "data" / "users"
        temp_root.mkdir(parents=True, exist_ok=True)

        thread_id = "test_memory_integration"
        thread_dir = temp_root / f"http_{thread_id}" / "mem"
        thread_dir.mkdir(parents=True, exist_ok=True)

        # Patch settings to use temp directory
        with patch.object(settings, "USERS_ROOT", temp_root):
            yield thread_id

    @pytest.fixture
    def mock_agent(self):
        """Create a mock agent."""
        agent = MagicMock()
        agent.ainvoke = AsyncMock(return_value={"messages": []})
        agent.astream = AsyncMock()
        return agent

    def test_is_general_query_detection(self, mock_agent):
        """Test general query detection in BaseChannel."""
        channel = MockChannel(agent=mock_agent)

        # General queries
        assert channel._is_general_query("What do you remember?")
        assert channel._is_general_query("What do you know about me?")
        assert channel._is_general_query("Tell me about myself")
        assert channel._is_general_query("Remind me of my information")

        # Specific queries
        assert not channel._is_general_query("What's my name?")
        assert not channel._is_general_query("Where do I work?")
        assert not channel._is_general_query("Show me sales data")

    def test_get_relevant_memories_loads_profiles(self, mock_agent, temp_mem_db):
        """Test that _get_relevant_memories always loads profile memories."""
        from executive_assistant.config import settings

        # Create profile memories
        storage = MemoryStorage()
        thread_id = temp_mem_db

        storage.create_memory(
            content="Alice",
            memory_type="profile",
            key="name",
            thread_id=thread_id,
        )

        storage.create_memory(
            content="Product Manager at Acme Corp",
            memory_type="profile",
            key="role",
            thread_id=thread_id,
        )

        # Create channel and test
        channel = MockChannel(agent=mock_agent)

        # Call _get_relevant_memories with a general query
        memories = channel._get_relevant_memories(
            thread_id=thread_id,
            query="What do you remember?",
            limit=5,
        )

        # Verify profile memories are retrieved
        assert len(memories) >= 2  # At least 2 profile memories

        profile_contents = [m["content"] for m in memories if m.get("memory_type") == "profile"]
        assert "Alice" in profile_contents
        assert "Product Manager at Acme Corp" in profile_contents

    def test_profile_loaded_on_every_call(self, mock_agent, temp_mem_db):
        """Test that profile memories are loaded on every call (not cached)."""
        storage = MemoryStorage()
        thread_id = temp_mem_db

        # Create profile memories
        storage.create_memory(
            content="Bob",
            memory_type="profile",
            key="name",
            thread_id=thread_id,
        )

        channel = MockChannel(agent=mock_agent)

        # First call - should load from DB
        memories_1 = channel._get_relevant_memories(
            thread_id=thread_id,
            query="What do you remember?",
            limit=5,
        )

        # Second call - should also load from DB (no caching at this level)
        memories_2 = channel._get_relevant_memories(
            thread_id=thread_id,
            query="What do you know about me?",
            limit=5,
        )

        # Both should return the same profile memories
        assert len(memories_1) >= 1
        assert len(memories_2) >= 1

        contents_1 = [m["content"] for m in memories_1 if m.get("memory_type") == "profile"]
        contents_2 = [m["content"] for m in memories_2 if m.get("memory_type") == "profile"]

        assert "Bob" in contents_1
        assert "Bob" in contents_2

    def test_specific_query_combines_profiles_and_search(self, mock_agent, temp_mem_db):
        """Test that specific queries combine profile + search results."""
        storage = MemoryStorage()
        thread_id = temp_mem_db

        # Create profile memories
        storage.create_memory(
            content="Charlie",
            memory_type="profile",
            key="name",
            thread_id=thread_id,
        )

        # Create fact memories
        storage.create_memory(
            content="User is working on Q4 sales dashboard project",
            memory_type="fact",
            thread_id=thread_id,
        )

        channel = MockChannel(agent=mock_agent)

        # Call with specific query
        memories = channel._get_relevant_memories(
            thread_id=thread_id,
            query="sales dashboard project",  # Specific query about project
            limit=5,
        )

        # Should include profile memories (always loaded)
        profile_memories = [m for m in memories if m.get("memory_type") == "profile"]
        assert len(profile_memories) >= 1
        assert any(m["content"] == "Charlie" for m in profile_memories)

        # May include search results (depends on FTS5 matching)
        # But profile should always be present
        assert "Charlie" in [m["content"] for m in memories]

    def test_multiple_threads_dont_mix_memories(self, mock_agent, tmp_path):
        """Test that different threads don't mix their memories."""
        from executive_assistant.config import settings

        # Create temp directory
        temp_root = tmp_path / "data" / "users"
        temp_root.mkdir(parents=True, exist_ok=True)

        storage = MemoryStorage()

        # Create memories for thread 1
        thread_id_1 = "test_thread_1"
        thread_dir_1 = temp_root / f"http_{thread_id_1}" / "mem"
        thread_dir_1.mkdir(parents=True, exist_ok=True)

        with patch.object(settings, "USERS_ROOT", temp_root):
            storage.create_memory(
                content="Alice",
                memory_type="profile",
                key="name",
                thread_id=thread_id_1,
            )

        # Create memories for thread 2
        thread_id_2 = "test_thread_2"
        thread_dir_2 = temp_root / f"http_{thread_id_2}" / "mem"
        thread_dir_2.mkdir(parents=True, exist_ok=True)

        with patch.object(settings, "USERS_ROOT", temp_root):
            storage.create_memory(
                content="Bob",
                memory_type="profile",
                key="name",
                thread_id=thread_id_2,
            )

        channel = MockChannel(agent=mock_agent)

        # Load thread 1
        with patch.object(settings, "USERS_ROOT", temp_root):
            memories_1 = channel._get_relevant_memories(
                thread_id=thread_id_1,
                query="What do you remember?",
                limit=5,
            )

        # Load thread 2
        with patch.object(settings, "USERS_ROOT", temp_root):
            memories_2 = channel._get_relevant_memories(
                thread_id=thread_id_2,
                query="What do you remember?",
                limit=5,
            )

        # Verify different content (no cross-contamination)
        with patch.object(settings, "USERS_ROOT", temp_root):
            contents_1 = [m["content"] for m in memories_1 if m.get("memory_type") == "profile"]
            contents_2 = [m["content"] for m in memories_2 if m.get("memory_type") == "profile"]

        assert "Alice" in contents_1
        assert "Bob" in contents_2
        assert "Alice" not in contents_2  # No cross-contamination
        assert "Bob" not in contents_1  # No cross-contamination
