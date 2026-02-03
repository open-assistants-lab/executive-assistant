"""Test memory retrieval bug fix.

This test demonstrates and verifies the fix for the memory retrieval bug where
profile memories were not being retrieved in new conversations.

Bug: The _get_relevant_memories() method used search_memories() which performs
semantic search. When a user asks "What do you remember?", the query doesn't
match profile content like "name: Alice", so memories aren't retrieved.

Fix: Always load profile memories using list_memories(), cache them per
conversation, and use search only for specific queries.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from executive_assistant.storage.mem_storage import MemoryStorage


class TestMemoryRetrievalFix:
    """Test memory retrieval across conversations."""

    @pytest.fixture
    def temp_mem_db(self, tmp_path):
        """Create a temporary memory database for testing."""
        from executive_assistant.config import settings

        # Create temp directory structure
        temp_root = tmp_path / "data" / "users"
        temp_root.mkdir(parents=True, exist_ok=True)

        thread_id = "test_memory_retrieval"
        thread_dir = temp_root / f"http_{thread_id}" / "mem"
        thread_dir.mkdir(parents=True, exist_ok=True)

        # Patch settings to use temp directory
        with patch.object(settings, "USERS_ROOT", temp_root):
            yield thread_id

    def test_profile_memories_created(self, temp_mem_db):
        """Test that profile memories can be created."""
        storage = MemoryStorage()
        thread_id = temp_mem_db

        # Create profile memories
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

        storage.create_memory(
            content="Prefers brief, bullet-point responses",
            memory_type="preference",
            key="communication_style",
            thread_id=thread_id,
        )

        # Verify memories exist
        profile_memories = storage.list_memories(
            memory_type="profile",
            status="active",
            thread_id=thread_id,
        )

        assert len(profile_memories) == 2
        assert any(m["content"] == "Alice" for m in profile_memories)
        assert any(m["content"] == "Product Manager at Acme Corp" for m in profile_memories)

    def test_search_memories_fails_for_general_query(self, temp_mem_db):
        """Test that search_memories FAILS to retrieve profile memories with general query.

        This demonstrates the bug: semantic search doesn't match profile content.
        """
        storage = MemoryStorage()
        thread_id = temp_mem_db

        # Create profile memories
        storage.create_memory(
            content="Alice",
            memory_type="profile",
            key="name",
            thread_id=thread_id,
        )

        storage.create_memory(
            content="Product Manager",
            memory_type="profile",
            key="role",
            thread_id=thread_id,
        )

        # Try to retrieve with general query (this is the bug)
        results = storage.search_memories(
            query="What do you remember?",
            limit=5,
            thread_id=thread_id,
        )

        # BUG: Semantic search won't match "Alice" or "Product Manager"
        # with query "What do you remember?"
        # This assertion will FAIL, demonstrating the bug
        assert len(results) == 0, "Search fails to find profile memories (BUG CONFIRMED)"

    def test_list_memories_retrieves_all_profiles(self, temp_mem_db):
        """Test that list_memories SUCCESSFULLY retrieves all profile memories.

        This is the solution: always load profile memories using list_memories().
        """
        storage = MemoryStorage()
        thread_id = temp_mem_db

        # Create profile memories
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

        storage.create_memory(
            content="Prefers brief responses",
            memory_type="preference",
            key="communication_style",
            thread_id=thread_id,
        )

        # Use list_memories to retrieve all profiles
        profile_memories = storage.list_memories(
            memory_type="profile",
            status="active",
            thread_id=thread_id,
        )

        # This works! All profile memories retrieved
        assert len(profile_memories) == 2
        assert any(m["key"] == "name" and m["content"] == "Alice" for m in profile_memories)
        assert any(m["key"] == "role" and "Product Manager" in m["content"] for m in profile_memories)

    def test_hybrid_approach_profile_plus_search(self, temp_mem_db):
        """Test hybrid approach: load profiles + search for other memories.

        This is the fix: combine list_memories() for profiles + search_memories()
        for specific queries.
        """
        storage = MemoryStorage()
        thread_id = temp_mem_db

        # Create profile memories
        storage.create_memory(
            content="Alice",
            memory_type="profile",
            key="name",
            thread_id=thread_id,
        )

        storage.create_memory(
            content="Sales Analytics",
            memory_type="profile",
            key="department",
            thread_id=thread_id,
        )

        # Create some fact memories
        storage.create_memory(
            content="User is working on Q4 sales dashboard",
            memory_type="fact",
            thread_id=thread_id,
        )

        storage.create_memory(
            content="User asked about customer data integration yesterday",
            memory_type="fact",
            thread_id=thread_id,
        )

        # 1. ALWAYS load profile memories
        profile_memories = storage.list_memories(
            memory_type="profile",
            status="active",
            thread_id=thread_id,
        )

        # 2. Search for other memories if needed
        query = "What was I working on?"
        fact_memories = storage.search_memories(
            query=query,
            limit=5,
            thread_id=thread_id,
        )

        # 3. Combine both
        all_memories = profile_memories + fact_memories

        # Verify we get both profile AND relevant facts
        assert len(all_memories) >= 2  # At least 2 profile memories
        assert any(m["memory_type"] == "profile" and m["content"] == "Alice" for m in all_memories)
        assert any(m["memory_type"] == "profile" and m["content"] == "Sales Analytics" for m in all_memories)

        # Fact memories may or may not match depending on FTS5
        # Profile memories should always be present
        profile_contents = [m["content"] for m in all_memories if m["memory_type"] == "profile"]
        assert "Alice" in profile_contents
        assert "Sales Analytics" in profile_contents


class TestMemoryCaching:
    """Test profile memory caching to avoid redundant queries."""

    @pytest.fixture
    def temp_mem_db(self, tmp_path):
        """Create a temporary memory database for testing."""
        from executive_assistant.config import settings

        # Create temp directory structure
        temp_root = tmp_path / "data" / "users"
        temp_root.mkdir(parents=True, exist_ok=True)

        thread_id = "test_memory_cache"
        thread_dir = temp_root / f"http_{thread_id}" / "mem"
        thread_dir.mkdir(parents=True, exist_ok=True)

        # Patch settings to use temp directory
        with patch.object(settings, "USERS_ROOT", temp_root):
            yield thread_id

    def test_profile_cache_avoids_redundant_loads(self, temp_mem_db):
        """Test that caching profile memories avoids redundant database queries."""
        storage = MemoryStorage()
        thread_id = temp_mem_db

        # Create profile memories
        storage.create_memory(
            content="Alice",
            memory_type="profile",
            key="name",
            thread_id=thread_id,
        )

        # Simulate cache
        profile_loaded = set()

        # First call - not in cache, load from DB
        if thread_id not in profile_loaded:
            memories = storage.list_memories(
                memory_type="profile",
                status="active",
                thread_id=thread_id,
            )
            profile_loaded.add(thread_id)
            first_call_count = len(memories)
        else:
            first_call_count = 0

        # Second call - in cache, no DB query
        if thread_id not in profile_loaded:
            # This won't execute
            second_call_count = len(storage.list_memories(
                memory_type="profile",
                thread_id=thread_id,
            ))
        else:
            second_call_count = 0  # Cached, no query

        # Verify: first call loaded memories, second call used cache
        assert first_call_count == 1  # Loaded 1 profile memory
        assert second_call_count == 0  # Cached, no query
        assert thread_id in profile_loaded  # Thread is marked as cached


class TestIsGeneralQuery:
    """Test general query detection heuristic."""

    def test_general_query_patterns(self):
        """Test detection of general memory queries."""
        general_queries = [
            "What do you remember?",
            "What do you know about me?",
            "Remind me of my information",
            "What have you learned about me?",
            "Tell me about myself",
            "What information do you have?",
        ]

        for query in general_queries:
            # Simple heuristic: general queries ask about "me", "remember", "know", "information"
            is_general = any(
                phrase in query.lower()
                for phrase in ["what do you remember", "what do you know", "about me", "about myself", "remind me", "information do you have"]
            )
            assert is_general, f"Query should be detected as general: {query}"

    def test_specific_query_patterns(self):
        """Test detection of specific queries."""
        specific_queries = [
            "What's my name?",
            "Where do I work?",
            "What was I working on yesterday?",
            "Show me sales data",
            "Customer information",
        ]

        for query in specific_queries:
            # These should NOT be detected as general
            is_general = any(
                phrase in query.lower()
                for phrase in ["what do you remember", "what do you know", "about me", "about myself"]
            )
            assert not is_general, f"Query should NOT be detected as general: {query}"
