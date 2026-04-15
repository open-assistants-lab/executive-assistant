"""Middleware conformance tests.

Verify that SDK middleware produces consistent observable effects.
"""

import os
import tempfile
import pytest
from unittest.mock import MagicMock, patch

os.environ.setdefault("CHECKPOINT_ENABLED", "false")


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
        from src.sdk.middleware_memory import MemoryMiddleware
        from src.sdk.state import AgentState
        from src.sdk.messages import Message

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
        from src.sdk.middleware_memory import MemoryMiddleware
        from src.sdk.state import AgentState
        from src.sdk.messages import Message

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
        from src.sdk.middleware_memory import MemoryMiddleware, EXTRACTION_TURN_INTERVAL
        from src.sdk.messages import Message

        mw = MemoryMiddleware(user_id="test_sdk_extract")

        for turn in range(1, EXTRACTION_TURN_INTERVAL + 1):
            msgs = [Message.user(f"msg {turn}")]
            assert mw._should_extract(msgs) == (turn % EXTRACTION_TURN_INTERVAL == 0)

    def test_sdk_memory_after_agent_returns_none_on_no_extract(self):
        from src.sdk.middleware_memory import MemoryMiddleware
        from src.sdk.state import AgentState
        from src.sdk.messages import Message

        mw = MemoryMiddleware(user_id="test_sdk_after")
        mw._should_extract = lambda msgs: False

        state = AgentState(messages=[Message.user("hello")])
        result = mw.after_agent(state)
        assert result is None


class TestSDKSkillMiddleware:
    """SDK SkillMiddleware must produce consistent behavior."""

    def test_sdk_skill_middleware_init(self):
        from src.sdk.middleware_skill import SkillMiddleware

        with tempfile.TemporaryDirectory() as tmpdir:
            mw = SkillMiddleware(system_dir=tmpdir, user_id="test_user")
            assert mw is not None
            assert mw.registry is not None

    def test_sdk_skill_extends_middleware(self):
        from src.sdk.middleware import Middleware
        from src.sdk.middleware_skill import SkillMiddleware

        with tempfile.TemporaryDirectory() as tmpdir:
            mw = SkillMiddleware(system_dir=tmpdir, user_id="test_user")
            assert isinstance(mw, Middleware)

    def test_sdk_skill_empty_prompt_when_no_skills(self):
        from src.sdk.middleware_skill import SkillMiddleware

        with tempfile.TemporaryDirectory() as tmpdir:
            mw = SkillMiddleware(system_dir=tmpdir, user_id="test_user")
            prompt = mw._build_skills_prompt()
            assert prompt == ""

    def test_sdk_skill_before_agent_injects_prompt(self):
        from src.sdk.middleware_skill import SkillMiddleware
        from src.sdk.state import AgentState
        from src.sdk.messages import Message

        with tempfile.TemporaryDirectory() as tmpdir:
            mw = SkillMiddleware(system_dir=tmpdir, user_id="test_user")
            mw.registry = MagicMock()
            mw.registry.get_skill_descriptions.return_value = ["- **test_skill**: A test skill"]

            state = AgentState(messages=[Message.system("You are helpful.")])
            result = mw.before_agent(state)

            assert result is not None
            assert "messages" in result
            assert "Available Skills" in result["messages"][0].content

    def test_sdk_skill_before_agent_no_system_message(self):
        from src.sdk.middleware_skill import SkillMiddleware
        from src.sdk.state import AgentState
        from src.sdk.messages import Message

        with tempfile.TemporaryDirectory() as tmpdir:
            mw = SkillMiddleware(system_dir=tmpdir, user_id="test_user")
            mw.registry = MagicMock()
            mw.registry.get_skill_descriptions.return_value = ["- **test_skill**: A test skill"]

            state = AgentState(messages=[Message.user("hello")])
            result = mw.before_agent(state)

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
        from src.sdk.middleware_summarization import SummarizationMiddleware
        from src.sdk.state import AgentState
        from src.sdk.messages import Message

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
        from src.sdk.middleware_summarization import SummarizationMiddleware
        from src.sdk.state import AgentState
        from src.sdk.messages import Message

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
        from src.sdk.middleware_summarization import SummarizationMiddleware
        from src.sdk.messages import Message, ToolCall

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


class TestWSProtocolConformance:
    """WS protocol must handle all message types consistently."""

    def test_client_message_roundtrip(self):
        """All client message types must serialize and parse correctly."""
        from src.http.ws_protocol import (
            UserMessage,
            ApproveMessage,
            RejectMessage,
            EditAndApproveMessage,
            CancelMessage,
            PingMessage,
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
            ToolStartMessage,
            ToolEndMessage,
            InterruptMessage,
            DoneMessage,
            ErrorMessage,
            PongMessage,
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
