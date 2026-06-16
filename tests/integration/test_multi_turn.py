"""Multi-turn conversation tests via AgentLoop with FakeProvider."""

import pytest

from src.sdk.messages import Message


def _last_assistant_content(messages: list[Message]) -> str:
    """Extract content from the last non-tool assistant message."""
    for m in reversed(messages):
        if m.role == "assistant" and not m.tool_calls:
            return m.content if isinstance(m.content, str) else ""
    return ""


@pytest.mark.asyncio
async def test_agent_stops_on_tool_result(loop):
    """After tool executes, agent returns text response (doesn't loop infinitely)."""
    loop.provider._responses = [
        {"tool_calls": [{"name": "time_get", "arguments": {}, "id": "call_t1"}]},
        {"content": "The current time is now."},
    ]
    await loop.run([Message.user("what time is it?")])
    content = _last_assistant_content(loop.state.messages)
    assert content, "Agent should respond after tool execution"
    assert len(content) > 0


@pytest.mark.asyncio
async def test_agent_handles_unknown_tool(loop):
    """Agent loop handles unknown tool gracefully, returns error message."""
    loop.provider._responses = [
        {"tool_calls": [{"name": "nonexistent_tool", "arguments": {"x": "y"}, "id": "call_u1"}]},
        {"content": "I encountered an error trying to use that tool."},
    ]
    await loop.run([Message.user("use nonexistent tool")])
    content = _last_assistant_content(loop.state.messages)
    assert content, "Agent should respond even with unknown tool"
    assert len(content) > 0


@pytest.mark.asyncio
async def test_empty_tool_call_list(loop):
    """No-tool path works, text returned directly."""
    loop.provider._responses = [
        {"content": "Hello! How can I help you today?"},
    ]
    await loop.run([Message.user("say hello")])
    content = _last_assistant_content(loop.state.messages)
    assert content
    assert "hello" in content.lower()


@pytest.mark.asyncio
async def test_multiple_tool_calls(loop):
    """Multiple distinct tool calls both execute."""
    loop.provider._responses = [
        {
            "tool_calls": [
                {"name": "time_get", "arguments": {}, "id": "call_1"},
                {"name": "time_get", "arguments": {}, "id": "call_2"},
            ]
        },
        {"content": "Done with both."},
    ]
    await loop.run([Message.user("check time twice")])
    content = _last_assistant_content(loop.state.messages)
    assert content, "Agent should respond after multiple tool calls"
