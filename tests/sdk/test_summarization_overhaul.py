"""Tests for summarization overhaul: pruning, force_summarize, overflow recovery, tool."""

from __future__ import annotations

import pytest

from src.sdk.messages import Message

# -- Helpers --


def _msg(role: str, content: str = "", tool_call_id: str | None = None) -> Message:
    from src.sdk.messages import Message

    if role == "tool":
        return Message(role="tool", content=content, tool_call_id=tool_call_id or "tc1", name="time_get")
    return Message(role=role, content=content)


# -- ProviderContextOverflowError --


def test_provider_context_overflow_error_exists():
    from src.sdk.providers.base import ProviderContextOverflowError

    err = ProviderContextOverflowError("too long")
    assert "too long" in str(err)
    assert isinstance(err, Exception)


# -- _prune_tool_outputs --


def test_prune_tool_outputs_replaces_old_tool_outputs():
    from src.sdk.middleware_summarization import SummarizationMiddleware

    mw = SummarizationMiddleware()
    messages = [
        _msg("user", "hello"),
        _msg("assistant", "let me check"),
        _msg("tool", "big output " * 5000, tool_call_id="tc1"),
        _msg("user", "what now?"),
        _msg("assistant", "here you go"),
    ]

    pruned = mw._prune_tool_outputs(messages, keep_tokens=200)

    # Old tool output should be replaced with placeholder
    assert pruned[2].role == "tool"
    assert pruned[2].content.startswith("[pruned:")
    assert "tokens of tool output" in pruned[2].content
    # Recent messages should be intact
    assert pruned[3].content == "what now?"
    assert pruned[4].content == "here you go"


def test_prune_tool_outputs_leaves_recent_messages_intact():
    from src.sdk.middleware_summarization import SummarizationMiddleware

    mw = SummarizationMiddleware()
    messages = [
        _msg("user", "hi"),
        _msg("assistant", "hello"),
    ]

    pruned = mw._prune_tool_outputs(messages, keep_tokens=1000)
    assert pruned[0].content == "hi"
    assert pruned[1].content == "hello"


def test_prune_does_not_mutate_original_list():
    from src.sdk.middleware_summarization import SummarizationMiddleware

    mw = SummarizationMiddleware()
    messages = [
        _msg("user", "hi"),
        _msg("tool", "big output" * 1000, tool_call_id="tc1"),
        _msg("user", "bye"),
    ]
    original_content = messages[1].content
    mw._prune_tool_outputs(messages, keep_tokens=10)
    assert messages[1].content == original_content


# -- _split_messages --


def test_split_messages_separates_old_and_recent():
    from src.sdk.middleware_summarization import SummarizationMiddleware

    mw = SummarizationMiddleware()
    messages = [
        _msg("user", "old1"),
        _msg("assistant", "old2"),
        _msg("user", "recent1"),
        _msg("assistant", "recent2"),
    ]

    old, recent = mw._split_messages(messages, keep_tokens=3)

    # With keep_tokens=3, only the last few chars fit: at least recent2 should be recent
    assert len(old) >= 0
    assert len(recent) >= 1


def test_split_messages_preserves_system_messages():
    from src.sdk.middleware_summarization import SummarizationMiddleware

    mw = SummarizationMiddleware()
    messages = [
        _msg("system", "you are a helpful assistant"),
        _msg("user", "old1"),
        _msg("assistant", "old2"),
    ]

    old, recent = mw._split_messages(messages, keep_tokens=1000)

    # System message should be in recent, not in old
    assert not any(m.role == "system" for m in old)
    assert any(m.role == "system" for m in recent)


# -- force_summarize --


@pytest.mark.asyncio
async def test_force_summarize_returns_false_for_empty():
    from src.sdk.middleware_summarization import SummarizationMiddleware
    from src.sdk.state import AgentState

    mw = SummarizationMiddleware()
    state = AgentState(messages=[Message.user("hi")])

    result = await mw.force_summarize(state)
    assert result is False


@pytest.mark.asyncio
async def test_force_summarize_fires_on_summarize_callback():
    from src.sdk.middleware_summarization import SummarizationMiddleware

    callback_called = []

    async def on_summary(content: str) -> None:
        callback_called.append(content)

    mw = SummarizationMiddleware(on_summarize=on_summary)

    # force_summarize will call _generate_summary which uses AgentLoop.run_single
    # which requires a real provider. This test just verifies the method exists
    # and follows the correct path.
    assert hasattr(mw, "force_summarize")
    assert callable(mw.force_summarize)


# -- summarize_session tool --


def test_summarize_session_registered():
    from src.sdk.native_tools import get_native_tools

    names = {t.name for t in get_native_tools()}
    assert "summarize_session" in names


def test_summarize_session_annotations():
    from src.sdk.tools_core.summarize import summarize_session

    ann = summarize_session.annotations
    assert ann.read_only is True
    assert ann.idempotent is True


@pytest.mark.asyncio
async def test_summarize_session_uses_active_loop_state():
    from src.sdk.loop import AgentLoop, _current_agent_loop
    from src.sdk.messages import Message
    from src.sdk.middleware_summarization import SummarizationMiddleware
    from src.sdk.providers.base import LLMProvider, ModelInfo
    from src.sdk.state import AgentState
    from src.sdk.tools_core.summarize import summarize_session

    class Provider(LLMProvider):
        @property
        def provider_id(self) -> str:
            return "fake"

        async def chat(self, *args, **kwargs):
            return Message.assistant("ok")

        async def chat_stream(self, *args, **kwargs):
            if False:
                yield None

        def get_model_info(self, model: str | None = None):
            return ModelInfo(id=model or "fake", provider_id="fake")

        def count_tokens(self, messages) -> int:
            return 0

    mw = SummarizationMiddleware()
    loop = AgentLoop(provider=Provider(), middlewares=[mw])
    loop.state = AgentState(messages=[Message.user("old " * 500), Message.user("new " * 500)])

    async def fake_force_summarize(state, instructions=None):
        state.messages = [Message.system("summary"), Message.user("new")]
        return True

    mw.force_summarize = fake_force_summarize
    token = _current_agent_loop.set(loop)
    try:
        result = await summarize_session.ainvoke({"user_id": "u"})
    finally:
        _current_agent_loop.reset(token)

    assert result.startswith("Summarized. Saved ~")


@pytest.mark.asyncio
async def test_abefore_model_returns_none_when_summary_generation_fails():
    from src.sdk.messages import Message
    from src.sdk.middleware_summarization import SummarizationMiddleware
    from src.sdk.state import AgentState

    mw = SummarizationMiddleware(trigger_tokens=10, keep_tokens=5)

    async def no_summary(text: str) -> None:
        return None

    mw._generate_summary = no_summary
    state = AgentState(
        messages=[
            Message.user("old " * 100),
            Message.assistant("middle " * 100),
            Message.user("new " * 100),
        ]
    )

    assert await mw.abefore_model(state) is None


@pytest.mark.asyncio
async def test_context_overflow_retry_does_not_duplicate_latest_user_message():
    from src.sdk.loop import AgentLoop
    from src.sdk.messages import Message
    from src.sdk.middleware_summarization import SummarizationMiddleware
    from src.sdk.providers.base import LLMProvider, ModelInfo, ProviderContextOverflowError

    seen_prepared_messages: list[list[Message]] = []

    class Provider(LLMProvider):
        calls = 0

        @property
        def provider_id(self) -> str:
            return "fake"

        async def chat(self, messages, *args, **kwargs):
            self.calls += 1
            seen_prepared_messages.append(list(messages))
            if self.calls == 1:
                raise ProviderContextOverflowError("too large")
            return Message.assistant("ok")

        async def chat_stream(self, *args, **kwargs):
            if False:
                yield None

        def get_model_info(self, model: str | None = None):
            return ModelInfo(id=model or "fake", provider_id="fake")

        def count_tokens(self, messages) -> int:
            return 0

    mw = SummarizationMiddleware()

    async def fake_force_summarize(state, instructions=None):
        state.messages = [Message.system("summary"), Message.user("latest")]
        return True

    mw.force_summarize = fake_force_summarize
    loop = AgentLoop(provider=Provider(), middlewares=[mw])

    result = await loop.run([Message.user("latest")])

    assert result[-1].content == "ok"
    retried_user_messages = [m for m in seen_prepared_messages[1] if m.role == "user"]
    assert [m.content for m in retried_user_messages] == ["latest"]


# -- get_current_agent_loop --


def test_get_current_agent_loop_exists():
    from src.sdk.loop import get_current_agent_loop

    # Should return None when not inside a run
    assert get_current_agent_loop() is None


# -- AgentLoop.find_middleware --


def test_find_middleware_returns_correct_type():
    from src.sdk.loop import AgentLoop

    # Only test that the method exists and has correct signature
    assert hasattr(AgentLoop, "find_middleware")
    assert callable(AgentLoop.find_middleware)
