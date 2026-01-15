"""Unit tests for summarization threshold logic."""

from unittest.mock import patch, MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.graph import END

from cassey.agent.graph import route_agent
from cassey.agent.state import AgentState


class TestSummarizationThreshold:
    """Test summarization threshold and routing logic."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings with test threshold values."""
        with patch("cassey.agent.graph.settings") as mock:
            mock.ENABLE_SUMMARIZATION = True
            mock.SUMMARY_THRESHOLD = 5  # Low threshold for testing
            mock.MAX_ITERATIONS = 20  # Max iterations before giving up
            yield mock

    def create_ai_message_with_tools(self, content=""):
        """Create an AIMessage with tool calls."""
        msg = AIMessage(content=content)
        msg.tool_calls = [
            {"name": "test_tool", "args": {"query": "test"}, "id": "call_123"}
        ]
        return msg

    def create_ai_message_without_tools(self, content="Response"):
        """Create an AIMessage without tool calls."""
        msg = AIMessage(content=content)
        msg.tool_calls = []
        return msg

    def create_message_sequence(self, human_count, ai_count, with_tools=False):
        """Create a sequence of messages for testing.

        Args:
            human_count: Number of HumanMessages to create
            ai_count: Number of AIMessages to create
            with_tools: Whether AI messages should have tool calls

        Returns:
            List of messages
        """
        messages = []
        for i in range(human_count):
            messages.append(HumanMessage(content=f"User message {i+1}"))
        for i in range(ai_count):
            if with_tools:
                messages.append(self.create_ai_message_with_tools(f"Thinking {i+1}"))
            else:
                messages.append(self.create_ai_message_without_tools(f"Response {i+1}"))
        return messages

    def test_below_threshold_routes_to_end(self, mock_settings):
        """Test that below threshold routes to END."""
        # Create state with 4 messages (below threshold of 5)
        messages = self.create_message_sequence(human_count=2, ai_count=2, with_tools=False)
        state: AgentState = {
            "messages": messages,
            "iterations": 0,
            "summary": "",
            "structured_summary": None,
            "user_id": "test_user",
            "channel": "test",
        }

        result = route_agent(state)
        assert result == END, "Below threshold should route to END"

    def test_at_threshold_without_tools_routes_to_summarize(self, mock_settings):
        """Test that at threshold without tool calls routes to summarize."""
        # Create state with 5 messages (at threshold) - no tool calls
        messages = self.create_message_sequence(human_count=3, ai_count=2, with_tools=False)
        state: AgentState = {
            "messages": messages,
            "iterations": 0,
            "summary": "",
            "structured_summary": None,
            "user_id": "test_user",
            "channel": "test",
        }

        result = route_agent(state)
        assert result == "summarize", "At threshold without tools should summarize"

    def test_at_threshold_with_tools_routes_to_tools(self, mock_settings):
        """Test that tool calls take priority over summarization at threshold."""
        # Create state with 5 messages (at threshold) - last AI has tool calls
        messages = self.create_message_sequence(human_count=3, ai_count=2, with_tools=False)
        messages.append(self.create_ai_message_with_tools("Need to search"))  # Now 6 messages
        state: AgentState = {
            "messages": messages,
            "iterations": 0,
            "summary": "",
            "structured_summary": None,
            "user_id": "test_user",
            "channel": "test",
        }

        result = route_agent(state)
        assert result == "tools", "Tool calls should take priority at threshold"

    def test_urgent_threshold_forces_summarize_even_with_tools(self, mock_settings):
        """Test that 2x threshold with pending tools routes to tools (safety first).

        Note: After the checkpoint corruption fix, we prioritize completing
        pending tool calls over urgent summarization to prevent state corruption.
        """
        # Create state with 10 messages (2x threshold of 5) - with tool calls
        messages = self.create_message_sequence(human_count=5, ai_count=5, with_tools=True)
        state: AgentState = {
            "messages": messages,
            "iterations": 0,
            "summary": "",
            "structured_summary": None,
            "user_id": "test_user",
            "channel": "test",
        }

        result = route_agent(state)
        # With pending tool calls, we route to tools first (safety over urgency)
        assert result == "tools", "Pending tool calls take priority over urgent summarization"

    def test_urgent_threshold_with_mixed_messages(self, mock_settings):
        """Test urgent threshold with mixed human/ai/tool messages."""
        messages = []
        for i in range(5):  # 5 exchanges = 10 messages at threshold
            messages.append(HumanMessage(content=f"Query {i+1}"))
            messages.append(self.create_ai_message_with_tools(f"Thinking {i+1}"))
            # Add tool messages (should not be counted in threshold)
            messages.append(ToolMessage(
                content="Tool result",
                name="test_tool",
                tool_call_id=f"call_{i}"
            ))

        state: AgentState = {
            "messages": messages,
            "iterations": 0,
            "summary": "",
            "structured_summary": None,
            "user_id": "test_user",
            "channel": "test",
        }

        result = route_agent(state)
        assert result == "summarize", "Urgent threshold with mixed messages should summarize"

    def test_disabled_summarization_routes_to_end(self, mock_settings):
        """Test that disabled summarization routes to END regardless of count."""
        mock_settings.ENABLE_SUMMARIZATION = False

        # Create state with many messages
        messages = self.create_message_sequence(human_count=10, ai_count=10, with_tools=False)
        state: AgentState = {
            "messages": messages,
            "iterations": 0,
            "summary": "",
            "structured_summary": None,
            "user_id": "test_user",
            "channel": "test",
        }

        result = route_agent(state)
        assert result == END, "Disabled summarization should route to END"

    def test_max_iterations_with_tools_at_threshold(self, mock_settings):
        """Test behavior at max iterations with tool calls."""
        # Create state at threshold with tool calls, at max iterations
        messages = self.create_message_sequence(human_count=3, ai_count=2, with_tools=False)
        messages.append(self.create_ai_message_with_tools("Need to search"))

        state: AgentState = {
            "messages": messages,
            "iterations": mock_settings.MAX_ITERATIONS,  # At max iterations
            "summary": "",
            "structured_summary": None,
            "user_id": "test_user",
            "channel": "test",
        }

        result = route_agent(state)
        # Should still check summarization since tools aren't processed at max iterations
        assert result == "summarize", "At max iterations and threshold should summarize"

    def test_message_count_only_counts_human_and_ai(self, mock_settings):
        """Test that only HumanMessage and AIMessage count toward threshold."""
        messages = []

        # Add 3 human messages and 2 AI messages (5 total = at threshold)
        for i in range(3):
            messages.append(HumanMessage(content=f"Query {i+1}"))
        for i in range(2):
            messages.append(self.create_ai_message_without_tools(f"Response {i+1}"))

        # Add many ToolMessage (should not count)
        for i in range(10):
            messages.append(ToolMessage(
                content="Tool result",
                name="test_tool",
                tool_call_id=f"call_{i}"
            ))

        state: AgentState = {
            "messages": messages,
            "iterations": 0,
            "summary": "",
            "structured_summary": None,
            "user_id": "test_user",
            "channel": "test",
        }

        result = route_agent(state)
        assert result == "summarize", "Only human/AI messages should count toward threshold"

    def test_exactly_urgent_threshold(self, mock_settings):
        """Test behavior exactly at 2x threshold with pending tools.

        Note: After the checkpoint corruption fix, pending tool calls take priority.
        """
        # 5 human + 5 ai = 10 messages (exactly 2x threshold of 5)
        # All AI messages have tool calls
        messages = []
        for i in range(5):  # 5 human + 5 ai = 10 messages
            messages.append(HumanMessage(content=f"Query {i+1}"))
            messages.append(self.create_ai_message_with_tools(f"Response {i+1}"))

        state: AgentState = {
            "messages": messages,
            "iterations": 0,
            "summary": "",
            "structured_summary": None,
            "user_id": "test_user",
            "channel": "test",
        }

        result = route_agent(state)
        # With pending tool calls at the last message, route to tools first
        assert result == "tools", "Exactly at urgent threshold with tools routes to tools (safety first)"
