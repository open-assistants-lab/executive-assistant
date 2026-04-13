"""SDK conftest - shared fixtures for SDK tests."""

import os
import tempfile
from unittest.mock import MagicMock, AsyncMock

import pytest

os.environ.setdefault("CHECKPOINT_ENABLED", "false")


@pytest.fixture
def tmp_dir():
    """Create a temporary directory for per-test isolation."""
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def mock_llm_response():
    """Create a mock LLM response (LangChain AIMessage format)."""

    def _make(content="", tool_calls=None):
        msg = MagicMock()
        msg.content = content
        msg.type = "ai"
        msg.tool_calls = tool_calls or []
        msg.additional_kwargs = {}
        msg.response_metadata = {}
        msg.id = "msg_test"
        return msg

    return _make


@pytest.fixture
def mock_tool_call():
    """Create a mock tool call."""

    def _make(name="time_get", args=None, call_id="call_1"):
        return {
            "name": name,
            "args": args or {},
            "id": call_id,
            "type": "tool_call",
        }

    return _make


@pytest.fixture
def mock_tool_result():
    """Create a mock tool result message (LangChain ToolMessage format)."""

    def _make(content="result", name="time_get", tool_call_id="call_1"):
        msg = MagicMock()
        msg.content = content
        msg.name = name
        msg.tool_call_id = tool_call_id
        msg.type = "tool"
        return msg

    return _make
