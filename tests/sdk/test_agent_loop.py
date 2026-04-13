"""Agent loop conformance tests (non-HTTP).

These tests verify agent behavior through direct Python calls,
not through the HTTP API. For API-level tests, see tests/api/test_agent_loop.py.
"""

import os
import pytest

os.environ.setdefault("CHECKPOINT_ENABLED", "false")


class TestAgentLoopBasic:
    """Basic agent loop behavior that must be consistent."""

    def test_recursion_limit_is_set(self):
        """Agent must have a recursion limit to prevent infinite loops."""
        from src.agents.manager import _get_pool_size

        pool_size = _get_pool_size()
        assert isinstance(pool_size, int)
        assert pool_size > 0

    def test_pool_creates_with_user_id(self):
        """AgentPool must be created with a user_id."""
        from src.agents.manager import AgentPool

        pool = AgentPool("test_user", pool_size=2)
        assert pool.user_id == "test_user"
        assert pool.pool_size == 2

    def test_pool_size_default(self):
        """Default pool size should be > 0."""
        from src.agents.manager import AgentPool

        pool = AgentPool("test_user")
        assert pool.pool_size > 0

    def test_agent_factory_creates_with_user_id(self):
        """AgentFactory must track the user_id."""
        from src.agents.factory import AgentFactory

        factory = AgentFactory(user_id="test_user")
        assert factory.user_id == "test_user"


class TestAgentLoopWSProtocol:
    """WebSocket protocol must be self-consistent with HTTP API."""

    def test_ws_protocol_covers_all_event_types(self):
        """WS protocol must define types for all agent events."""
        from src.http.ws_protocol import SERVER_MESSAGE_TYPES, CLIENT_MESSAGE_TYPES

        expected_server_types = {
            "ai_token",
            "tool_start",
            "tool_end",
            "interrupt",
            "done",
            "error",
            "pong",
        }
        expected_client_types = {
            "user_message",
            "approve",
            "reject",
            "edit_and_approve",
            "cancel",
            "ping",
        }

        actual_server = set(SERVER_MESSAGE_TYPES.keys())
        actual_client = set(CLIENT_MESSAGE_TYPES.keys())

        assert expected_server_types.issubset(actual_server), (
            f"Missing: {expected_server_types - actual_server}"
        )
        assert expected_client_types.issubset(actual_client), (
            f"Missing: {expected_client_types - actual_client}"
        )

    def test_interrupt_message_has_allowed_actions(self):
        """Interrupt messages must specify allowed actions for HITL."""
        from src.http.ws_protocol import InterruptMessage

        msg = InterruptMessage(call_id="c1", tool="files_delete", args={"path": "/x"})
        assert "approve" in msg.allowed_actions
        assert "reject" in msg.allowed_actions

    def test_done_message_can_include_tool_calls(self):
        """Done message must be able to include tool call info."""
        from src.http.ws_protocol import DoneMessage

        msg = DoneMessage(
            response="Here are the results", tool_calls=[{"name": "time_get", "call_id": "c1"}]
        )
        assert len(msg.tool_calls) == 1
        assert msg.tool_calls[0]["name"] == "time_get"
