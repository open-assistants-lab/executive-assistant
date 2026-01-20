"""Tests for LangChain/LangGraph agent components.

Tests the agent state, router, nodes, and graph creation functions.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from executive_assistant.agent.state import AgentState
from executive_assistant.agent.router import should_continue
from executive_assistant.agent.nodes import call_model, call_tools


# =============================================================================
# AgentState Tests
# =============================================================================

class TestAgentState:
    """Test AgentState TypedDict definition."""

    def test_agent_state_structure(self):
        """Test that AgentState has expected structure."""
        state = AgentState(
            messages=[HumanMessage(content="Hello")],
            structured_summary=None,
            user_id="test_user",
            channel="test",
        )

        assert len(state["messages"]) == 1
        assert state["messages"][0].content == "Hello"
        assert state["structured_summary"] is None
        assert state["user_id"] == "test_user"
        assert state["channel"] == "test"

    def test_agent_state_with_summary(self):
        """Test AgentState with structured summary."""
        summary = {
            "topics": [{"name": "test", "status": "active"}],
            "active_request": {"text": "test request"},
        }

        state = AgentState(
            messages=[],
            structured_summary=summary,
            user_id="test_user",
            channel="test",
        )

        assert state["structured_summary"] == summary
        assert len(state["structured_summary"]["topics"]) == 1


# =============================================================================
# Router Tests
# =============================================================================

class TestShouldContinue:
    """Test should_continue routing logic."""

    def test_continue_with_tool_calls(self):
        """Test routing to tools when AI message has tool calls."""
        from langchain_core.messages.tool import ToolCall

        tool_call = ToolCall(name="test_tool", args={}, id="1", type="tool_call")
        ai_msg = AIMessage(content="", tool_calls=[tool_call])

        state = AgentState(
            messages=[ai_msg],
            structured_summary=None,
            user_id="test_user",
            channel="test",
        )

        result = should_continue(state)
        assert result == "tools"

    def test_continue_without_tool_calls(self):
        """Test continuing to next step when no tool calls."""
        ai_msg = AIMessage(content="I'm done")

        state = AgentState(
            messages=[ai_msg],
            structured_summary=None,
            user_id="test_user",
            channel="test",
        )

        result = should_continue(state)
        assert result == "continue"

    def test_continue_with_human_message(self):
        """Test that human message doesn't route to tools."""
        human_msg = HumanMessage(content="Hello")

        state = AgentState(
            messages=[human_msg],
            structured_summary=None,
            user_id="test_user",
            channel="test",
        )

        result = should_continue(state)
        assert result == "continue"


# =============================================================================
# Node Tests
# =============================================================================

class TestCallModel:
    """Test call_model node."""

    @pytest.fixture
    def mock_model(self):
        """Create a mock chat model."""
        model = AsyncMock(spec=BaseChatModel)
        model.bind_tools = MagicMock(return_value=model)
        model.ainvoke = AsyncMock(return_value=AIMessage(content="Test response"))
        return model

    @pytest.fixture
    def mock_tools(self):
        """Create mock tools."""
        tool = MagicMock(spec=BaseTool)
        tool.name = "test_tool"
        return [tool]

    @pytest.mark.asyncio
    async def test_call_model_basic(self, mock_model, mock_tools):
        """Test basic model invocation."""
        state = AgentState(
            messages=[HumanMessage(content="Hello")],
            structured_summary=None,
            user_id="test_user",
            channel="test",
        )

        result = await call_model(state, {}, mock_model, mock_tools)

        assert "messages" in result
        assert len(result["messages"]) == 1
        assert result["messages"][0].content == "Test response"

    @pytest.mark.asyncio
    async def test_call_model_with_summary(self, mock_model, mock_tools):
        """Test model invocation with structured summary."""
        summary = {
            "topics": [{"name": "test", "status": "active", "intent": "conversational"}],
            "active_request": {"text": "Current request"},
        }

        state = AgentState(
            messages=[HumanMessage(content="Hello")],
            structured_summary=summary,
            user_id="test_user",
            channel="test",
        )

        with patch("executive_assistant.agent.nodes.get_system_prompt", return_value="System prompt"):
            result = await call_model(state, {}, mock_model, mock_tools, system_prompt="Custom prompt")

            assert "messages" in result


class TestCallTools:
    """Test call_tools node."""

    @pytest.fixture
    def mock_tools(self):
        """Create mock tools."""
        async_tool = AsyncMock(spec=BaseTool)
        async_tool.name = "async_tool"
        async_tool._arun = AsyncMock(return_value="async result")
        async_tool.ainvoke = AsyncMock(return_value="async result")

        sync_tool = MagicMock(spec=BaseTool)
        sync_tool.name = "sync_tool"
        sync_tool.invoke = MagicMock(return_value="sync result")
        sync_tool._arun = None

        return {
            "async_tool": async_tool,
            "sync_tool": sync_tool,
        }

    @pytest.mark.asyncio
    async def test_call_tools_single(self, mock_tools):
        """Test calling a single tool."""
        from langchain_core.messages.tool import ToolCall

        tool_call = ToolCall(name="async_tool", args={"input": "test"}, id="call_1", type="tool_call")
        ai_msg = AIMessage(content="", tool_calls=[tool_call])

        state = AgentState(
            messages=[ai_msg],
            structured_summary=None,
            user_id="test_user",
            channel="test",
        )

        result = await call_tools(state, mock_tools)

        assert "messages" in result
        assert len(result["messages"]) == 1
        assert isinstance(result["messages"][0], ToolMessage)
        assert result["messages"][0].name == "async_tool"
        assert "async result" in result["messages"][0].content

    @pytest.mark.asyncio
    async def test_call_tools_multiple(self, mock_tools):
        """Test calling multiple tools."""
        from langchain_core.messages.tool import ToolCall

        tool_call1 = ToolCall(name="async_tool", args={"input": "test1"}, id="call_1", type="tool_call")
        tool_call2 = ToolCall(name="sync_tool", args={"input": "test2"}, id="call_2", type="tool_call")
        ai_msg = AIMessage(content="", tool_calls=[tool_call1, tool_call2])

        state = AgentState(
            messages=[ai_msg],
            structured_summary=None,
            user_id="test_user",
            channel="test",
        )

        result = await call_tools(state, mock_tools)

        assert len(result["messages"]) == 2

    @pytest.mark.asyncio
    async def test_call_tools_not_found(self, mock_tools):
        """Test calling a tool that doesn't exist."""
        from langchain_core.messages.tool import ToolCall

        tool_call = ToolCall(name="missing_tool", args={}, id="call_1", type="tool_call")
        ai_msg = AIMessage(content="", tool_calls=[tool_call])

        state = AgentState(
            messages=[ai_msg],
            structured_summary=None,
            user_id="test_user",
            channel="test",
        )

        result = await call_tools(state, mock_tools)

        assert len(result["messages"]) == 1
        assert "not found" in result["messages"][0].content.lower()

    @pytest.mark.asyncio
    async def test_call_tools_no_tool_calls(self, mock_tools):
        """Test call_tools when message has no tool calls."""
        ai_msg = AIMessage(content="No tools needed")

        state = AgentState(
            messages=[ai_msg],
            structured_summary=None,
            user_id="test_user",
            channel="test",
        )

        result = await call_tools(state, mock_tools)

        assert result["messages"] == []

    @pytest.mark.asyncio
    async def test_call_tools_with_error(self, mock_tools):
        """Test tool that raises an exception."""
        from langchain_core.messages.tool import ToolCall

        error_tool = AsyncMock(spec=BaseTool)
        error_tool.name = "error_tool"
        error_tool._arun = AsyncMock(side_effect=RuntimeError("Tool failed"))

        tools_with_error = {**mock_tools, "error_tool": error_tool}

        tool_call = ToolCall(name="error_tool", args={}, id="call_1", type="tool_call")
        ai_msg = AIMessage(content="", tool_calls=[tool_call])

        state = AgentState(
            messages=[ai_msg],
            structured_summary=None,
            user_id="test_user",
            channel="test",
        )

        result = await call_tools(state, tools_with_error)

        assert len(result["messages"]) == 1
        assert "error" in result["messages"][0].content.lower()



# =============================================================================
# Graph Creation Tests
# =============================================================================

class TestGraphCreation:
    """Test graph creation functions."""

    def test_create_graph_imports(self):
        """Test that create_graph can be imported."""
        from executive_assistant.agent.graph import create_graph
        assert create_graph is not None

    def test_create_react_graph_imports(self):
        """Test that create_react_graph can be imported."""
        from executive_assistant.agent.graph import create_react_graph
        assert create_react_graph is not None


# =============================================================================
# Topic Classifier Tests
# =============================================================================

class TestTopicClassifier:
    """Test topic classifier components."""

    def test_topic_classifier_imports(self):
        """Test that topic classifier can be imported."""
        from executive_assistant.agent.topic_classifier import StructuredSummaryBuilder
        assert StructuredSummaryBuilder is not None

    def test_structured_summary_builder_render(self):
        """Test rendering structured summary for prompt."""
        from executive_assistant.agent.topic_classifier import StructuredSummaryBuilder

        summary = {
            "topics": [
                {"topic_id": "Weather", "status": "active", "summary": "User asked about weather"},
                {"topic_id": "Sports", "status": "inactive", "summary": "Previous discussion"},
            ],
            "active_request": {"text": "What's the weather like?"},
        }

        rendered = StructuredSummaryBuilder.render_for_prompt(summary)

        # Only active topic should be rendered
        assert "Weather" in rendered
        assert "active" in rendered.lower()
        assert "What's the weather" in rendered


# =============================================================================
# Prompts Tests
# =============================================================================

class TestPrompts:
    """Test prompt generation functions."""

    def test_get_system_prompt(self):
        """Test getting system prompt for a channel."""
        from executive_assistant.agent.prompts import get_system_prompt

        prompt = get_system_prompt("telegram")
        assert prompt is not None
        assert len(prompt) > 0

    def test_get_system_prompt_for_unknown_channel(self):
        """Test getting system prompt for unknown channel."""
        from executive_assistant.agent.prompts import get_system_prompt

        prompt = get_system_prompt("unknown_channel")
        assert prompt is not None
        assert len(prompt) > 0


# =============================================================================
# Checkpoint Utils Tests
# =============================================================================

class TestCheckpointUtils:
    """Test checkpoint utility functions."""

    def test_checkpoint_utils_imports(self):
        """Test that checkpoint utils can be imported."""
        from executive_assistant.agent.checkpoint_utils import (
            detect_corrupted_messages,
            sanitize_corrupted_messages,
            should_propose_before_action,
            format_proposal,
        )
        assert detect_corrupted_messages is not None
        assert sanitize_corrupted_messages is not None
        assert should_propose_before_action is not None
        assert format_proposal is not None


# =============================================================================
# Integration Tests
# =============================================================================

class TestAgentIntegration:
    """Integration tests for agent components."""

    def test_agent_module_exports(self):
        """Test that agent module exports expected symbols."""
        from executive_assistant import agent

        expected_exports = [
            "AgentState",
            "create_graph",
            "create_react_graph",
            "create_langchain_agent",
            "call_model",
            "call_tools",
            "should_continue",
        ]

        for export in expected_exports:
            assert hasattr(agent, export), f"{export} not exported from agent module"

    def test_state_message_accumulation(self):
        """Test that messages accumulate correctly using add_messages."""
        from langgraph.graph.message import add_messages

        # Existing messages
        existing = [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi there"),
        ]

        # New messages to add
        new = [
            AIMessage(content="How can I help?"),
        ]

        # add_messages should merge/append
        result = add_messages(existing, new)

        assert len(result) == 3
        assert result[0].content == "Hello"
        assert result[1].content == "Hi there"
        assert result[2].content == "How can I help?"

    def test_state_message_deduplication(self):
        """Test that duplicate messages (by id) are handled correctly."""
        from langgraph.graph.message import add_messages

        # Create messages and reuse the same instance for testing deduplication
        ai_msg = AIMessage(content="Hi")
        existing = [
            HumanMessage(content="Hello"),
            ai_msg,
        ]

        # Adding the same message instance shouldn't duplicate (deduped by id)
        new = [
            ai_msg,  # Same instance as existing
        ]

        result = add_messages(existing, new)

        # Should still have only 2 messages (deduped by id)
        assert len(result) == 2
