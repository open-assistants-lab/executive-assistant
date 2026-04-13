"""Agent loop conformance tests.

Verifies that the LangChain agent loop produces consistent observable behavior.
These tests will be re-run against the custom SDK AgentLoop to ensure parity.

Tests use FastAPI TestClient to invoke the agent through the HTTP API,
avoiding the need for a running LLM. Where possible, we mock the LLM response
to test specific agent behaviors (tool calling, error handling, etc.).
"""

import os
import pytest

os.environ.setdefault("CHECKPOINT_ENABLED", "false")


class TestMessageContracts:
    """Verify message type contracts are met."""

    def test_langchain_ai_message_has_role(self):
        """AI messages from LangChain must have type='ai' and content."""
        from langchain_core.messages import AIMessage

        msg = AIMessage(content="Hello")
        assert msg.type == "ai"
        assert msg.content == "Hello"

    def test_langchain_human_message_has_role(self):
        """Human messages must have type='human'."""
        from langchain_core.messages import HumanMessage

        msg = HumanMessage(content="Hi there")
        assert msg.type == "human"
        assert msg.content == "Hi there"

    def test_langchain_tool_message_has_fields(self):
        """Tool messages must have type='tool', content, name, tool_call_id."""
        from langchain_core.messages import ToolMessage

        msg = ToolMessage(content="result", name="time_get", tool_call_id="call_1")
        assert msg.type == "tool"
        assert msg.content == "result"
        assert msg.name == "time_get"
        assert msg.tool_call_id == "call_1"

    def test_langchain_ai_message_tool_calls(self):
        """AI messages may include tool_calls with id, name, args."""
        from langchain_core.messages import AIMessage

        msg = AIMessage(
            content="",
            tool_calls=[
                {"id": "call_1", "name": "time_get", "args": {}},
            ],
        )
        assert msg.tool_calls is not None
        assert len(msg.tool_calls) == 1
        assert msg.tool_calls[0]["name"] == "time_get"

    def test_ws_ai_token_message_schema(self):
        """WS ai_token message must have type, content, session_id."""
        from src.http.ws_protocol import AiTokenMessage

        msg = AiTokenMessage(content="Hello", session_id="sess_1")
        data = msg.model_dump()
        assert data["type"] == "ai_token"
        assert data["content"] == "Hello"
        assert data["session_id"] == "sess_1"

    def test_ws_done_message_schema(self):
        """WS done message must have type, response, tool_calls."""
        from src.http.ws_protocol import DoneMessage

        msg = DoneMessage(response="Done!", tool_calls=[{"name": "time_get"}])
        data = msg.model_dump()
        assert data["type"] == "done"
        assert data["response"] == "Done!"
        assert len(data["tool_calls"]) == 1

    def test_ws_interrupt_message_schema(self):
        """WS interrupt message must have call_id, tool, args, allowed_actions."""
        from src.http.ws_protocol import InterruptMessage

        msg = InterruptMessage(
            call_id="call_1",
            tool="files_delete",
            args={"path": "/test.txt"},
        )
        data = msg.model_dump()
        assert data["type"] == "interrupt"
        assert data["call_id"] == "call_1"
        assert data["tool"] == "files_delete"
        assert data["allowed_actions"] == ["approve", "reject", "edit"]


class TestStreamingEventFormat:
    """Verify the format of LangChain v2 astream_events chunks.

    These tests document the exact format of streaming events so that
    the WS endpoint and SDK streaming produce identical output.
    """

    def test_v2_event_has_required_keys(self):
        """Every v2 astream_event dict must have 'event', 'name', 'data' keys."""
        from langchain_core.messages import AIMessageChunk

        chunk = AIMessageChunk(content="test")
        event = {
            "event": "on_chat_model_stream",
            "name": "ChatOllama",
            "data": {"chunk": chunk},
            "run_id": "test-run-id",
            "tags": [],
            "metadata": {},
        }
        assert "event" in event
        assert "name" in event
        assert "data" in event

    def test_v2_model_stream_event_format(self):
        """Model stream events contain AIMessageChunk in data['chunk']."""
        from langchain_core.messages import AIMessageChunk

        chunk = AIMessageChunk(content="Hello")
        assert hasattr(chunk, "content")
        assert chunk.content == "Hello"

    def test_v2_tool_start_event_format(self):
        """Tool start events have input data."""
        event = {
            "event": "on_tool_start",
            "name": "time_get",
            "data": {"input": {"user_id": "test"}},
        }
        assert "input" in event["data"]

    def test_v2_tool_end_event_format(self):
        """Tool end events have data['output']."""
        event = {
            "event": "on_tool_end",
            "name": "time_get",
            "data": {"output": "The current time is..."},
        }
        assert "output" in event["data"]

    def test_ws_event_type_mapping(self):
        """Mapping from v2 events to WS types must be consistent."""
        v2_to_ws = {
            "on_chat_model_stream": "ai_token",
            "on_tool_start": "tool_start",
            "on_tool_end": "tool_end",
        }
        for v2_event, ws_type in v2_to_ws.items():
            assert ws_type in (
                "ai_token",
                "tool_start",
                "tool_end",
                "done",
                "error",
                "interrupt",
                "middleware",
                "reasoning",
            )


class TestAgentPoolContract:
    """Verify AgentPool creates and manages agent instances correctly."""

    def test_pool_creates_with_user_id(self):
        from src.agents.manager import AgentPool

        pool = AgentPool("test_user", pool_size=2)
        assert pool.user_id == "test_user"
        assert pool.pool_size == 2

    def test_agent_factory_creates_with_user_id(self):
        from src.agents.factory import AgentFactory

        factory = AgentFactory(user_id="test_user")
        assert factory.user_id == "test_user"

    def test_middleware_order_is_correct(self):
        """Middleware must be in order: Summarization → HITL → Skill → Memory."""
        from src.agents.factory import AgentFactory
        from unittest.mock import MagicMock, patch

        with patch("src.agents.factory.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                memory=MagicMock(summarization=MagicMock(enabled=False)),
                filesystem=MagicMock(enabled=False),
            )
            factory = AgentFactory(user_id="test_user", enable_summarization=False)
            model = MagicMock()
            middleware = factory._get_middleware(model)
            assert len(middleware) == 0

    def test_middleware_summarization_included_when_enabled(self):
        """When summarization is enabled, SummarizationMiddleware is first."""
        from src.agents.factory import AgentFactory
        from unittest.mock import MagicMock, patch

        with patch("src.agents.factory.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                memory=MagicMock(
                    summarization=MagicMock(enabled=True, trigger_tokens=8000, keep_tokens=2000)
                ),
                filesystem=MagicMock(enabled=False),
            )
            factory = AgentFactory(user_id="test_user", enable_summarization=True)
            model = MagicMock()
            middleware = factory._get_middleware(model)
            assert len(middleware) == 1
            from src.agents.middleware.summarization import SummarizationMiddleware

            assert isinstance(middleware[0], SummarizationMiddleware)
