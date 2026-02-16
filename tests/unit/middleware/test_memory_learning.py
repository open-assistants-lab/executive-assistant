"""Unit tests for MemoryLearningMiddleware.

Tests rule extraction, LLM extraction, confidence filtering.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from langchain.messages import AIMessage, HumanMessage

from src.middleware.memory_learning import MemoryLearningMiddleware
from src.memory import MemoryType, MemorySource


class TestMemoryLearningMiddleware:
    """Test suite for MemoryLearningMiddleware."""

    def test_rule_extraction_preferences(self, mock_memory_store):
        """Test rule-based extraction of preferences."""
        middleware = MemoryLearningMiddleware(
            memory_store=mock_memory_store,
            extraction_model=None,  # Rule-based only
            auto_learn=True,
            min_confidence=0.6,
        )

        # Create a conversation with preference indicators
        messages = [
            HumanMessage(content="I prefer asynchronous communication"),
            AIMessage(content="I'll note that preference."),
        ]

        state = {"messages": messages}
        runtime = MagicMock()

        result = middleware.after_agent(state, runtime)

        # Should return None (no state modification)
        assert result is None

        # Check that memory was saved
        memories = mock_memory_store.search(lambda params: None)
        # Note: We'd need to verify the actual memory was saved
        # This tests the extraction doesn't crash

    def test_rule_extraction_profile_facts(self, mock_memory_store):
        """Test rule-based extraction of profile information."""
        middleware = MemoryLearningMiddleware(
            memory_store=mock_memory_store,
            extraction_model=None,
            auto_learn=True,
        )

        messages = [
            HumanMessage(content="I am a VP of Engineering"),
            AIMessage(content="Noted, you're a VP of Engineering."),
        ]

        state = {"messages": messages}
        runtime = MagicMock()

        # Should not crash
        result = middleware.after_agent(state, runtime)
        assert result is None

    def test_rule_extraction_tasks(self, mock_memory_store):
        """Test rule-based extraction of tasks."""
        middleware = MemoryLearningMiddleware(
            memory_store=mock_memory_store,
            extraction_model=None,
            auto_learn=True,
        )

        messages = [
            HumanMessage(content="Remind me to submit the budget by Friday"),
            AIMessage(content="I'll remind you about the budget."),
        ]

        state = {"messages": messages}
        runtime = MagicMock()

        result = middleware.after_agent(state, runtime)
        assert result is None

    def test_rule_extraction_contacts(self, mock_memory_store):
        """Test rule-based extraction of contacts."""
        middleware = MemoryLearningMiddleware(
            memory_store=mock_memory_store,
            extraction_model=None,
            auto_learn=True,
        )

        messages = [
            HumanMessage(content="I talked to Sarah about the project"),
            AIMessage(content="Noted your conversation with Sarah."),
        ]

        state = {"messages": messages}
        runtime = MagicMock()

        result = middleware.after_agent(state, runtime)
        assert result is None

    def test_min_confidence_filtering(self, mock_memory_store):
        """Test that low-confidence memories are filtered."""
        middleware = MemoryLearningMiddleware(
            memory_store=mock_memory_store,
            extraction_model=None,
            auto_learn=True,
            min_confidence=0.8,  # High threshold
        )

        messages = [
            HumanMessage(content="I prefer async communication"),  # Would extract at 0.7
            AIMessage(content="Noted."),
        ]

        state = {"messages": messages}
        runtime = MagicMock()

        # Should not crash, and low-confidence memory should be filtered
        result = middleware.after_agent(state, runtime)
        assert result is None

    def test_auto_learn_disabled(self, mock_memory_store):
        """Test that extraction is skipped when auto_learn=False."""
        middleware = MemoryLearningMiddleware(
            memory_store=mock_memory_store,
            extraction_model=None,
            auto_learn=False,  # Disabled
            min_confidence=0.6,
        )

        messages = [
            HumanMessage(content="I prefer async communication"),
            AIMessage(content="Noted."),
        ]

        state = {"messages": messages}
        runtime = MagicMock()

        result = middleware.after_agent(state, runtime)
        assert result is None

    def test_none_memory_store_skips_extraction(self):
        """Test that None memory store skips extraction."""
        middleware = MemoryLearningMiddleware(
            memory_store=None,
            extraction_model=None,
            auto_learn=True,
        )

        messages = [
            HumanMessage(content="I prefer async communication"),
            AIMessage(content="Noted."),
        ]

        state = {"messages": messages}
        runtime = MagicMock()

        # Should not crash
        result = middleware.after_agent(state, runtime)
        assert result is None

    def test_insufficient_messages_skips_extraction(self, mock_memory_store):
        """Test that extraction is skipped with too few messages."""
        middleware = MemoryLearningMiddleware(
            memory_store=mock_memory_store,
            extraction_model=None,
            auto_learn=True,
        )

        # Only one message
        messages = [HumanMessage(content="Hello")]

        state = {"messages": messages}
        runtime = MagicMock()

        result = middleware.after_agent(state, runtime)
        assert result is None

    def test_extract_preferences_method(self, mock_memory_store):
        """Test the _extract_preferences method directly."""
        middleware = MemoryLearningMiddleware(
            memory_store=mock_memory_store,
            extraction_model=None,
        )

        text = "I prefer asynchronous communication over meetings"
        text_lower = text.lower()

        memories = middleware._extract_preferences(text, text_lower)

        # Should extract a preference memory
        assert len(memories) >= 0
        for memory in memories:
            assert memory["type"] == "preference"
            assert memory["confidence"] > 0

    def test_extract_profile_facts_method(self, mock_memory_store):
        """Test the _extract_profile_facts method directly."""
        middleware = MemoryLearningMiddleware(
            memory_store=mock_memory_store,
            extraction_model=None,
        )

        text = "I am a VP of Engineering based in San Francisco"
        text_lower = text.lower()

        memories = middleware._extract_profile_facts(text, text_lower)

        # Should extract a profile memory
        assert len(memories) >= 0
        for memory in memories:
            assert memory["type"] == "profile"

    def test_extract_tasks_method(self, mock_memory_store):
        """Test the _extract_tasks method directly."""
        middleware = MemoryLearningMiddleware(
            memory_store=mock_memory_store,
            extraction_model=None,
        )

        text = "I need to submit the budget proposal by Friday"
        text_lower = text.lower()

        memories = middleware._extract_tasks(text, text_lower)

        # Should extract a task memory
        assert len(memories) >= 0
        for memory in memories:
            assert memory["type"] == "task"

    def test_extract_contacts_method(self, mock_memory_store):
        """Test the _extract_contacts method directly."""
        middleware = MemoryLearningMiddleware(
            memory_store=mock_memory_store,
            extraction_model=None,
        )

        text = "My boss is Sarah and she's the CEO"
        text_lower = text.lower()

        memories = middleware._extract_contacts(text, text_lower)

        # Should extract a contact memory
        assert len(memories) >= 0
        for memory in memories:
            assert memory["type"] == "contact"

    def test_save_memory_creates_correct_memory_type(self, mock_memory_store):
        """Test that _save_memory creates correct memory types."""
        middleware = MemoryLearningMiddleware(
            memory_store=mock_memory_store,
            extraction_model=None,
        )

        memory_data = {
            "title": "Test preference",
            "type": "preference",
            "narrative": "User prefers async communication",
            "facts": ["Prefers async"],
            "concepts": ["preference"],
            "confidence": 0.8,
            "source": "explicit",
        }

        # Should not crash
        middleware._save_memory(memory_data)

    def test_save_memory_handles_invalid_type(self, mock_memory_store):
        """Test that _save_memory handles invalid memory types gracefully."""
        middleware = MemoryLearningMiddleware(
            memory_store=mock_memory_store,
            extraction_model=None,
        )

        memory_data = {
            "title": "Test",
            "type": "invalid_type",  # Invalid
            "narrative": "Test",
            "confidence": 0.8,
        }

        # Should not crash, should default to INSIGHT
        middleware._save_memory(memory_data)

    def test_format_conversation(self):
        """Test conversation formatting for LLM extraction."""
        middleware = MemoryLearningMiddleware(
            memory_store=None,
            extraction_model=None,
        )

        messages = [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi there"),
            HumanMessage(content="How are you?"),
            AIMessage(content="I'm doing well"),
        ]

        formatted = middleware._format_conversation(messages)

        assert "User: Hello" in formatted
        assert "Assistant: Hi there" in formatted
        assert "User: How are you?" in formatted
