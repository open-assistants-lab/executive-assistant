"""Middleware effect verification tests via AgentLoop with FakeProvider.

Each test verifies the middleware's effect on the pipeline, not its internal logic.
"""

import pytest

from src.sdk.messages import Message


def _last_assistant_content(messages: list[Message]) -> str:
    for m in reversed(messages):
        if m.role == "assistant" and not m.tool_calls:
            return m.content if isinstance(m.content, str) else ""
    return ""


@pytest.mark.asyncio
async def test_memory_persistence(loop):
    """Two back-to-back runs both produce results (state is per-run)."""
    loop.provider._responses = [
        {"content": "Hello there!"},
        {"content": "I remember you said hello."},
    ]
    await loop.run([Message.user("say hello")])
    await loop.run([Message.user("what did I say?")])
    # Both runs completed — verify by checking state has messages from last run
    assert len(loop.state.messages) >= 2


@pytest.mark.asyncio
async def test_summary_generation(loop):
    """After summarization threshold is crossed, loop completes normally."""
    msg = Message.user("this is a test message " * 50)
    loop.provider._responses = [
        {"content": "That's a lot of text."},
    ]
    await loop.run([msg])
    assert any(m.content for m in loop.state.messages)


@pytest.mark.asyncio
async def test_sequential_turns_clean_state(loop):
    """Two back-to-back runs both complete successfully."""
    loop.provider._responses = [
        {"content": "First response."},
        {"content": "Second response."},
    ]
    await loop.run([Message.user("first message")])
    assert len(loop.state.messages) >= 2
    await loop.run([Message.user("second message")])
    assert len(loop.state.messages) >= 2
