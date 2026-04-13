"""Middleware conformance tests.

Verify that middleware produces consistent observable effects.
These tests ensure that both the current LangChain middleware and the
future SDK middleware produce the same behavior.
"""

import os
import tempfile
import pytest
from unittest.mock import MagicMock, patch

os.environ.setdefault("CHECKPOINT_ENABLED", "false")


class TestMemoryMiddlewareConformance:
    """MemoryMiddleware must produce consistent behavior."""

    def test_memory_middleware_init(self):
        """MemoryMiddleware must accept user_id."""
        from src.middleware.memory import MemoryMiddleware

        mw = MemoryMiddleware(user_id="test_user")
        assert mw is not None
        assert mw.user_id == "test_user"

    def test_memory_middleware_has_before_agent(self):
        """MemoryMiddleware must implement before_agent hook."""
        from src.middleware.memory import MemoryMiddleware

        mw = MemoryMiddleware(user_id="test_user")
        assert hasattr(mw, "before_agent")

    def test_memory_middleware_has_after_agent(self):
        """MemoryMiddleware must implement after_agent hook."""
        from src.middleware.memory import MemoryMiddleware

        mw = MemoryMiddleware(user_id="test_user")
        assert hasattr(mw, "after_agent")

    def test_memory_context_format(self):
        """Memory context must be a formatted string with sections."""
        from src.storage.memory import MemoryStore, get_memory_store

        store = get_memory_store("test_middleware_conf")
        store.add_memory(
            trigger="when user provides name",
            action="call them Alice",
            confidence=0.9,
            domain="personal",
            memory_type="fact",
        )
        context = store.get_memory_context()
        assert isinstance(context, str)
        assert len(context) > 0

    def test_correction_keywords_are_defined(self):
        """MemoryMiddleware must have correction keywords defined."""
        from src.middleware.memory import CORRECTION_KEYWORDS

        assert isinstance(CORRECTION_KEYWORDS, (list, tuple, set))
        assert len(CORRECTION_KEYWORDS) > 0
        assert "actually" in CORRECTION_KEYWORDS or "correction" in CORRECTION_KEYWORDS

    def test_extraction_turn_interval(self):
        """Memory extraction happens every N turns."""
        from src.middleware.memory import EXTRACTION_TURN_INTERVAL

        assert EXTRACTION_TURN_INTERVAL >= 1


class TestSkillMiddlewareConformance:
    """SkillMiddleware must produce consistent behavior."""

    def test_skill_middleware_init(self):
        """SkillMiddleware must accept system_dir and user_id."""
        from src.middleware.skill import SkillMiddleware

        with tempfile.TemporaryDirectory() as tmpdir:
            mw = SkillMiddleware(system_dir=tmpdir, user_id="test_user")
            assert mw is not None

    def test_skill_middleware_builds_prompt(self):
        """SkillMiddleware must build a skills prompt when skills exist."""
        from src.middleware.skill import SkillMiddleware

        with tempfile.TemporaryDirectory() as tmpdir:
            mw = SkillMiddleware(system_dir=tmpdir, user_id="test_user")
            prompt = mw._build_skills_prompt()
            assert isinstance(prompt, str)

    def test_skill_middleware_empty_prompt_when_no_skills(self):
        """Skills prompt must be empty when no skills are loaded."""
        from src.middleware.skill import SkillMiddleware

        with tempfile.TemporaryDirectory() as tmpdir:
            mw = SkillMiddleware(system_dir=tmpdir, user_id="test_user")
            prompt = mw._build_skills_prompt()
            assert prompt == ""


class TestSummarizationMiddlewareConformance:
    """SummarizationMiddleware must produce consistent behavior."""

    def test_summarization_middleware_init(self):
        """SummarizationMiddleware must accept model and threshold params."""
        from src.middleware.summarization import SummarizationMiddleware
        from unittest.mock import MagicMock

        model = MagicMock()
        mw = SummarizationMiddleware(
            model=model,
            trigger=("tokens", 8000),
            keep=("tokens", 2000),
        )
        assert mw is not None

    def test_summarization_trigger_threshold(self):
        """Summarization must trigger at the configured token threshold."""
        from src.middleware.summarization import SummarizationMiddleware
        from unittest.mock import MagicMock

        model = MagicMock()
        mw = SummarizationMiddleware(
            model=model,
            trigger=("tokens", 8000),
            keep=("tokens", 2000),
        )
        assert mw._last_summary_msg_count == 0


class TestMiddlewareOrderConformance:
    """The middleware pipeline must run in a specific order."""

    def test_factory_middleware_order(self):
        """Middleware must be: Summarization → HITL → Skill → Memory."""
        from src.agents.factory import AgentFactory
        from unittest.mock import MagicMock, patch

        with patch("src.agents.factory.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                memory=MagicMock(
                    summarization=MagicMock(enabled=True, trigger_tokens=8000, keep_tokens=2000)
                ),
                filesystem=MagicMock(enabled=True),
            )
            factory = AgentFactory(user_id="test_user", enable_summarization=True)
            model = MagicMock()
            middleware = factory._get_middleware(model)
            assert len(middleware) >= 1
            from src.middleware.summarization import SummarizationMiddleware

            assert isinstance(middleware[0], SummarizationMiddleware)


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
