"""Feature smoke tests via AgentLoop with FakeProvider.

Each test: FakeProvider returns a tool_call → AgentLoop executes tool → verify result.
No LLM calls, no network, no real filesystem writes (temp dirs + cleanup).
"""

import pytest

from src.sdk.messages import Message

# Each test case: (tool_name, response, side_effect_check)
# We verify: tool was called + tool result is non-empty (success indicator)
TEST_CASES = [
    ("web_search", {"tool_calls": [{"name": "web_search", "arguments": {"query": "AI news", "limit": 3}, "id": "call_ws1"}]}),
    ("files_list", {"tool_calls": [{"name": "files_list", "arguments": {"path": "."}, "id": "call_fl1"}]}),
    ("files_mkdir", {"tool_calls": [{"name": "files_mkdir", "arguments": {"path": "test_dir"}, "id": "call_fm1"}]}),
    ("files_write", {"tool_calls": [{"name": "files_write", "arguments": {"path": "test.txt", "content": "hello world"}, "id": "call_fw1"}]}),
    ("files_glob_search", {"tool_calls": [{"name": "files_glob_search", "arguments": {"pattern": "*.txt"}, "id": "call_fg1"}]}),
    ("time_get", {"tool_calls": [{"name": "time_get", "arguments": {}, "id": "call_tg1"}]}),
    ("message_search", {"tool_calls": [{"name": "message_search", "arguments": {"query": "hello"}, "id": "call_ms1"}]}),
    ("message_count", {"tool_calls": [{"name": "message_count", "arguments": {"query": "messages"}, "id": "call_mc1"}]}),
    ("workspace_info", {"tool_calls": [{"name": "workspace_info", "arguments": {}, "id": "call_wi1"}]}),
    ("todos_add", {"tool_calls": [{"name": "todos_add", "arguments": {"title": "buy milk", "priority": "medium"}, "id": "call_ta1"}]}),
    ("todos_list", {"tool_calls": [{"name": "todos_list", "arguments": {}, "id": "call_tl1"}]}),
    ("contacts_add", {"tool_calls": [{"name": "contacts_add", "arguments": {"name": "John Doe", "phone": "555-0100"}, "id": "call_ca1"}]}),
    ("contacts_list", {"tool_calls": [{"name": "contacts_list", "arguments": {}, "id": "call_cl1"}]}),
    ("shell_execute", {"tool_calls": [{"name": "shell_execute", "arguments": {"command": "echo hello test"}, "id": "call_se1"}]}),
    ("user_prompt_get", {"tool_calls": [{"name": "user_prompt_get", "arguments": {}, "id": "call_up1"}]}),
    ("mcp_list", {"tool_calls": [{"name": "mcp_list", "arguments": {}, "id": "call_ml1"}]}),
]


def _get_tool_result(messages: list[Message], tool_name: str) -> str | None:
    """Extract the tool result content for a given tool call from message history."""
    for i, msg in enumerate(messages):
        if msg.role == "assistant" and msg.tool_calls:
            for tc in msg.tool_calls:
                if tc.name == tool_name and tc.id:
                    # Find the tool result message with matching tool_call_id
                    for j in range(i + 1, len(messages)):
                        if messages[j].role == "tool" and messages[j].tool_call_id == tc.id:
                            return messages[j].content if isinstance(messages[j].content, str) else str(messages[j].content)
    return None


@pytest.mark.parametrize("tool_name,response", TEST_CASES)
@pytest.mark.asyncio
async def test_tool_execution(tool_name, response, loop):
    """Verifies each tool can be called and returns a non-empty result."""
    loop.provider._responses = [response, {"content": "Done."}]
    await loop.run([Message.user(f"run {tool_name}")])

    # Verify tool was called — check state.messages for assistant message with tool_calls
    tool_msgs = [m for m in loop.state.messages if m.role == "assistant" and m.tool_calls]
    assert any(
        tc.name == tool_name
        for msg in tool_msgs
        for tc in (msg.tool_calls or [])
    ), f"Tool '{tool_name}' was not called"

    # Verify tool result is non-empty (tool executed without crash)
    tool_result = _get_tool_result(loop.state.messages, tool_name)
    assert tool_result is not None, f"No tool result found for {tool_name}"
    assert len(tool_result) > 0, f"Empty tool result for {tool_name}"

    # Verify final assistant response exists
    last_assistant = None
    for m in reversed(loop.state.messages):
        if m.role == "assistant" and not m.tool_calls:
            last_assistant = m
            break
    assert last_assistant is not None, f"No assistant response for {tool_name}"


@pytest.mark.asyncio
async def test_invalid_tool_call(loop):
    """Agent handles tool calls with missing required arguments gracefully."""
    loop.provider._responses = [
        {"tool_calls": [{"name": "files_write", "arguments": {}, "id": "call_inv1"}]},
        {"content": "I need a file path to write to."},
    ]
    await loop.run([Message.user("write to a file")])
    last_assistant = None
    for m in reversed(loop.state.messages):
        if m.role == "assistant" and not m.tool_calls:
            last_assistant = m
            break
    assert last_assistant is not None and last_assistant.content, "Agent should respond even with invalid tool call"
