"""Middleware conformance tests.

Verify that SDK middleware produces consistent observable effects.
"""

from unittest.mock import MagicMock

import pytest

# ==================== SDK Middleware Tests ====================


class TestSDKMemoryMiddleware:
    """SDK MemoryMiddleware must produce consistent behavior."""

    def test_sdk_memory_middleware_init(self):
        from src.sdk.middleware_memory import MemoryMiddleware

        mw = MemoryMiddleware(user_id="test_user")
        assert mw is not None
        assert mw.user_id == "test_user"

    def test_sdk_memory_middleware_extends_middleware(self):
        from src.sdk.middleware import Middleware
        from src.sdk.middleware_memory import MemoryMiddleware

        mw = MemoryMiddleware(user_id="test_user")
        assert isinstance(mw, Middleware)

    def test_sdk_memory_middleware_has_hooks(self):
        from src.sdk.middleware_memory import MemoryMiddleware

        mw = MemoryMiddleware(user_id="test_user")
        assert hasattr(mw, "before_agent")
        assert hasattr(mw, "after_agent")
        assert callable(mw.before_agent)
        assert callable(mw.after_agent)

    def test_sdk_memory_before_agent_injects_context(self):
        from src.sdk.messages import Message
        from src.sdk.middleware_memory import MemoryMiddleware
        from src.sdk.state import AgentState

        mw = MemoryMiddleware(user_id="test_sdk_memory_inject")
        mw.memory_store = MagicMock()
        mw.memory_store.get_memory_context.return_value = (
            "## User Profile & Preferences\n- Name: Test"
        )

        state = AgentState(messages=[Message.system("You are a helpful assistant.")])
        result = mw.before_agent(state)

        assert result is not None
        assert "messages" in result
        assert "User Profile" in result["messages"][0].content

    def test_sdk_memory_before_agent_no_context(self):
        from src.sdk.messages import Message
        from src.sdk.middleware_memory import MemoryMiddleware
        from src.sdk.state import AgentState

        mw = MemoryMiddleware(user_id="test_sdk_memory_noctx")
        mw.memory_store = MagicMock()
        mw.memory_store.get_memory_context.return_value = ""

        state = AgentState(messages=[Message.system("You are helpful.")])
        result = mw.before_agent(state)

        assert result is None

    def test_sdk_memory_correction_keywords(self):
        from src.sdk.middleware_memory import CORRECTION_KEYWORDS

        assert isinstance(CORRECTION_KEYWORDS, (list, tuple, set))
        assert len(CORRECTION_KEYWORDS) > 0
        assert "actually" in CORRECTION_KEYWORDS or "correction" in CORRECTION_KEYWORDS

    def test_sdk_memory_extraction_interval(self):
        from src.sdk.middleware_memory import EXTRACTION_TURN_INTERVAL

        assert EXTRACTION_TURN_INTERVAL >= 1

    def test_sdk_memory_should_extract_every_n_turns(self):
        from src.sdk.messages import Message
        from src.sdk.middleware_memory import EXTRACTION_TURN_INTERVAL, MemoryMiddleware

        mw = MemoryMiddleware(user_id="test_sdk_extract")

        for turn in range(1, EXTRACTION_TURN_INTERVAL + 1):
            msgs = [Message.user(f"msg {turn}")]
            assert mw._should_extract(msgs) == (turn % EXTRACTION_TURN_INTERVAL == 0)

    def test_sdk_memory_after_agent_returns_none_on_no_extract(self):
        from src.sdk.messages import Message
        from src.sdk.middleware_memory import MemoryMiddleware
        from src.sdk.state import AgentState

        mw = MemoryMiddleware(user_id="test_sdk_after")
        mw._should_extract = lambda msgs: False

        state = AgentState(messages=[Message.user("hello")])
        result = mw.after_agent(state)
        assert result is None


class TestSDKSummarizationMiddleware:
    """SDK SummarizationMiddleware must produce consistent behavior."""

    def test_sdk_summarization_init(self):
        from src.sdk.middleware_summarization import SummarizationMiddleware

        mw = SummarizationMiddleware(
            trigger_tokens=8000,
            keep_tokens=2000,
            model="ollama:minimax-m2.5",
        )
        assert mw is not None
        assert mw.trigger_tokens == 8000
        assert mw.keep_tokens == 2000
        assert mw._last_summary_msg_count == 0

    def test_sdk_summarization_extends_middleware(self):
        from src.sdk.middleware import Middleware
        from src.sdk.middleware_summarization import SummarizationMiddleware

        mw = SummarizationMiddleware(trigger_tokens=8000, keep_tokens=2000)
        assert isinstance(mw, Middleware)

    def test_sdk_summarization_count_tokens_string(self):
        from src.sdk.middleware_summarization import SummarizationMiddleware

        mw = SummarizationMiddleware(trigger_tokens=8000, keep_tokens=2000)
        count = mw.count_tokens("Hello, this is a test string.")
        assert isinstance(count, int)
        assert count > 0

    def test_sdk_summarization_below_threshold(self):
        from src.sdk.messages import Message
        from src.sdk.middleware_summarization import SummarizationMiddleware
        from src.sdk.state import AgentState

        mw = SummarizationMiddleware(trigger_tokens=50000, keep_tokens=1000)
        state = AgentState(
            messages=[
                Message.system("You are helpful."),
                Message.user("Hello"),
            ]
        )
        result = mw.before_model(state)
        assert result is None

    @pytest.mark.asyncio
    async def test_sdk_summarization_duplicate_prevention(self):
        from src.sdk.messages import Message
        from src.sdk.middleware_summarization import SummarizationMiddleware
        from src.sdk.state import AgentState

        mw = SummarizationMiddleware(trigger_tokens=50000, keep_tokens=1000)
        mw._last_summary_msg_count = 100
        state = AgentState(messages=[Message.user("hi")])
        result = await mw.abefore_model(state)
        assert result is None

    def test_sdk_summarization_callback(self):
        from src.sdk.middleware_summarization import SummarizationMiddleware

        callback_data = []

        async def on_summary(content: str):
            callback_data.append(content)

        mw = SummarizationMiddleware(
            trigger_tokens=8000,
            keep_tokens=2000,
            model="ollama:minimax-m2.5",
            on_summarize=on_summary,
        )
        assert mw._on_summarize is not None

    def test_sdk_summarization_message_token_counting(self):
        from src.sdk.messages import Message, ToolCall
        from src.sdk.middleware_summarization import SummarizationMiddleware

        mw = SummarizationMiddleware(trigger_tokens=8000, keep_tokens=2000)

        simple_msg = Message.user("Hello world")
        simple_count = mw._count_message_tokens(simple_msg)
        assert simple_count > 0

        tool_msg = Message.assistant(
            content="Let me check",
            tool_calls=[ToolCall(id="tc1", name="time_get", arguments={})],
        )
        tool_count = mw._count_message_tokens(tool_msg)
        assert tool_count > simple_count

    def test_sdk_summarization_reasoning_tokens_included(self):
        from src.sdk.messages import Message
        from src.sdk.middleware_summarization import SummarizationMiddleware

        mw = SummarizationMiddleware(trigger_tokens=8000, keep_tokens=2000)

        no_reasoning = Message.assistant(
            content="The answer is 42.",
        )
        with_reasoning = Message.assistant(
            content="The answer is 42.",
            reasoning="Let me think step by step. First, I need to consider the question. "
            "The user is asking about the meaning of life, the universe, and everything. "
            "According to Douglas Adams' Hitchhiker's Guide to the Galaxy, "
            "the answer is 42. This was computed by Deep Thought "
            "after 7.5 million years of calculation.",
        )

        no_reasoning_count = mw._count_message_tokens(no_reasoning)
        with_reasoning_count = mw._count_message_tokens(with_reasoning)

        assert with_reasoning_count > no_reasoning_count, (
            f"Message with reasoning ({with_reasoning_count}) should have more tokens "
            f"than message without ({no_reasoning_count})"
        )


    @pytest.mark.asyncio
    async def test_sdk_summarization_callback_invoked_on_summarize(self):
        from unittest.mock import AsyncMock
        from src.sdk.messages import Message
        from src.sdk.middleware_summarization import SummarizationMiddleware
        from src.sdk.state import AgentState

        callback = AsyncMock()
        mw = SummarizationMiddleware(
            trigger_tokens=10,
            keep_tokens=5,
            on_summarize=callback,
        )

        summary_text = (
            "This is a test summary of the conversation. It covers the key topics discussed "
            "including user preferences, decisions made, and action items identified. "
            "The user asked about various subjects and the assistant provided helpful responses. "
            "Several important facts were established during this exchange. "
            "The conversation covered multiple topics and reached several conclusions. "
            "Key points included the user's preferences for concise answers and structured responses. "
            "The assistant demonstrated the ability to handle complex queries. "
            "Overall this was a productive exchange that achieved its objectives. "
            "The summary captures all essential information for future reference. "
            "Nothing important was omitted from this conversation summary."
        )
        assert len(summary_text) >= 200, f"Summary too short: {len(summary_text)} chars"

        mw._generate_summary = AsyncMock(return_value=summary_text)

        msgs = [Message.user(f"Message number {i} about various topics.") for i in range(20)]
        state = AgentState(messages=msgs)

        result = await mw.abefore_model(state)

        assert result is not None
        assert "messages" in result
        callback.assert_awaited_once()
        callback.assert_awaited_with(summary_text)


class TestWSProtocolConformance:
    """WS protocol must handle all message types consistently."""

    def test_client_message_roundtrip(self):
        """All client message types must serialize and parse correctly."""
        from src.http.ws_protocol import (
            ApproveMessage,
            CancelMessage,
            EditAndApproveMessage,
            PingMessage,
            RejectMessage,
            UserMessage,
            parse_client_message,
        )

        messages = [
            UserMessage(content="Hello"),
            ApproveMessage(call_id="call_1"),
            RejectMessage(call_id="call_1", reason="no"),
            EditAndApproveMessage(call_id="call_1", edited_args={"path": "/safe"}),
            CancelMessage(),
            PingMessage(),
        ]
        for msg in messages:
            data = msg.model_dump()
            parsed = parse_client_message(data)
            assert parsed is not None
            assert parsed.type == msg.type

    def test_server_message_roundtrip(self):
        """All server message types must serialize and parse correctly."""
        from src.http.ws_protocol import (
            AiTokenMessage,
            DoneMessage,
            ErrorMessage,
            InterruptMessage,
            PongMessage,
            ToolEndMessage,
            ToolStartMessage,
            parse_server_message,
        )

        messages = [
            AiTokenMessage(content="Hi"),
            ToolStartMessage(tool="time_get", call_id="c1"),
            ToolEndMessage(tool="time_get", call_id="c1", result_preview="12:00"),
            InterruptMessage(call_id="c1", tool="files_delete", args={"path": "/x"}),
            DoneMessage(response="Done"),
            ErrorMessage(message="fail", code="ERR"),
            PongMessage(),
        ]
        for msg in messages:
            data = msg.model_dump()
            parsed = parse_server_message(data)
            assert parsed is not None
            assert parsed.type == msg.type

    def test_unknown_types_return_none(self):
        """Unknown message types must return None (forward compatibility)."""
        from src.http.ws_protocol import parse_client_message, parse_server_message

        assert parse_client_message({"type": "future_type"}) is None
        assert parse_server_message({"type": "future_type"}) is None

    def test_missing_required_fields_return_none(self):
        """Messages missing required fields must return None."""
        from src.http.ws_protocol import parse_client_message, parse_server_message

        assert parse_client_message({"type": "user_message"}) is None
        assert parse_server_message({"type": "ai_token"}) is None
