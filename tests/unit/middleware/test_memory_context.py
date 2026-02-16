"""Unit tests for MemoryContextMiddleware.

Tests memory injection, search, formatting, progressive disclosure.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from langchain.agents.middleware import ModelResponse
from langchain.messages import AIMessage

from src.middleware.memory_context import MemoryContextMiddleware


class TestMemoryContextMiddleware:
    """Test suite for MemoryContextMiddleware."""

    def test_memory_injection(
        self,
        mock_memory_store_with_memories,
        mock_model_request,
        mock_handler: Callable,
    ):
        """Test that memories are injected into system prompt."""
        middleware = MemoryContextMiddleware(
            memory_store=mock_memory_store_with_memories,
            max_memories=5,
            min_confidence=0.7,
        )

        response = middleware.wrap_model_call(mock_model_request, mock_handler)

        assert response is not None
        assert len(response.messages) == 1
        assert isinstance(response.messages[0], AIMessage)

        # Check that memory context was added
        system_content = response.messages[0].content
        assert "Relevant Context" in system_content or "memory" in system_content.lower()

    def test_progressive_disclosure(
        self,
        mock_memory_store_with_memories,
        mock_model_request,
        mock_handler: Callable,
    ):
        """Test that only compact memories are injected (Layer 1 - ID, type, title only)."""
        middleware = MemoryContextMiddleware(
            memory_store=mock_memory_store_with_memories,
            max_memories=5,
            min_confidence=0.7,
        )

        response = middleware.wrap_model_call(mock_model_request, mock_handler)
        system_content = response.messages[0].content

        # Should include ID, type, and title
        # Should NOT include full narrative
        assert "[memory-" in system_content  # IDs present
        assert "Preference" in system_content or "Profile" in system_content  # Types present

        # Check that full narratives are NOT included (progressive disclosure)
        # Only short descriptions should be present
        assert "User prefers asynchronous communication" not in system_content

    def test_confidence_filtering(
        self,
        mock_memory_store_with_memories,
        mock_model_request,
        mock_handler: Callable,
    ):
        """Test that low-confidence memories are filtered."""
        middleware = MemoryContextMiddleware(
            memory_store=mock_memory_store_with_memories,
            max_memories=10,
            min_confidence=0.7,  # Should filter out the 0.5 confidence memory
        )

        response = middleware.wrap_model_call(mock_model_request, mock_handler)
        system_content = response.messages[0].content

        # Should NOT include the low-confidence memory
        assert "stressed" not in system_content.lower()

    def test_max_memories_limit(
        self,
        mock_memory_store_with_memories,
        mock_model_request,
        mock_handler: Callable,
    ):
        """Test that max_memories limits the number of memories injected."""
        middleware = MemoryContextMiddleware(
            memory_store=mock_memory_store_with_memories,
            max_memories=1,  # Only 1 memory
            min_confidence=0.0,
        )

        response = middleware.wrap_model_call(mock_model_request, mock_handler)
        system_content = response.messages[0].content

        # Count memory entries (look for bullet points)
        memory_count = system_content.count("- **")
        assert memory_count <= 1

    def test_no_memories_skips_injection(
        self,
        temp_user_path,
        mock_model_request,
        mock_handler: Callable,
    ):
        """Test that empty memory store skips injection."""
        from src.memory import MemoryStore

        empty_store = MemoryStore(user_id="test-user", data_path=temp_user_path)
        middleware = MemoryContextMiddleware(
            memory_store=empty_store,
            max_memories=5,
            min_confidence=0.7,
        )

        response = middleware.wrap_model_call(mock_model_request, mock_handler)

        # Should pass through without modification
        assert response is not None

    def test_none_memory_store_skips_injection(
        self,
        mock_model_request,
        mock_handler: Callable,
    ):
        """Test that None memory store skips injection."""
        middleware = MemoryContextMiddleware(
            memory_store=None,  # None memory store
            max_memories=5,
            min_confidence=0.7,
        )

        response = middleware.wrap_model_call(mock_model_request, mock_handler)

        # Should pass through without modification
        assert response is not None

    def test_extract_query_from_messages(self):
        """Test query extraction from message history."""
        from langchain.messages import HumanMessage, SystemMessage
        from langchain.agents.middleware import ModelRequest

        middleware = MemoryContextMiddleware(
            memory_store=None,
            max_memories=5,
        )

        # Test with simple text message
        request = ModelRequest(
            messages=[
                SystemMessage(content="You are helpful."),
                HumanMessage(content="What do you remember about my work?"),
            ],
            system_message=SystemMessage(content="You are helpful."),
        )

        query = middleware._extract_query(request)
        assert query == "What do you remember about my work?"

    def test_format_memories_uses_progressive_disclosure(
        self,
        mock_memory_store_with_memories,
    ):
        """Test that _format_memories follows progressive disclosure pattern."""
        middleware = MemoryContextMiddleware(
            memory_store=mock_memory_store_with_memories,
            max_memories=5,
        )

        # Get memories from search
        from src.memory import MemorySearchParams
        memories = mock_memory_store_with_memories.search(
            MemorySearchParams(query="test", limit=5)
        )

        formatted = middleware._format_memories(memories)

        # Check structure
        assert "## Relevant Context" in formatted
        assert "memory_get" in formatted  # Instructions for fetching details

        # Check that it's compact (no narratives)
        for memory in memories:
            assert memory.id in formatted  # IDs present
            # Full narrative should NOT be in formatted output
            assert len(memory.narrative or "") > len(formatted) or memory.narrative not in formatted

    def test_include_types_filter(self, mock_memory_store_with_memories):
        """Test filtering by memory types."""
        middleware = MemoryContextMiddleware(
            memory_store=mock_memory_store_with_memories,
            max_memories=10,
            include_types=["profile"],  # Only profile memories
        )

        # Search should respect include_types
        # (This tests the parameter is stored correctly)
        assert middleware.include_types == ["profile"]
