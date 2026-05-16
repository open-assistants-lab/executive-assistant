"""Unit tests for memory tools."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

TEST_USER_ID = "test_memory_user"


class TestMemoryGetHistory:
    """Tests for memory_get_history tool."""

    def test_memory_get_history_empty(self):
        """Test memory_get_history with empty result."""
        from src.sdk.tools_core.memory import memory_get_history

        with patch("src.sdk.tools_core.memory.get_message_store") as mock_get_store:
            mock_store = MagicMock()
            mock_store.get_messages.return_value = []
            mock_get_store.return_value = mock_store
            result = memory_get_history.invoke({"user_id": TEST_USER_ID})
            assert "no messages" in result.lower() or "empty" in result.lower()

    def test_memory_get_history_with_messages(self):
        """Test memory_get_history returns messages."""
        from src.sdk.tools_core.memory import memory_get_history

        mock_messages = [
            SimpleNamespace(role="user", content="Hello", ts=datetime.now(UTC)),
            SimpleNamespace(role="assistant", content="Hi there", ts=datetime.now(UTC)),
        ]
        with patch("src.sdk.tools_core.memory.get_message_store") as mock_get_store:
            mock_store = MagicMock()
            mock_store.get_messages.return_value = mock_messages
            mock_get_store.return_value = mock_store
            result = memory_get_history.invoke({"user_id": TEST_USER_ID})
            assert "Hello" in result or "Hi" in result

    def test_memory_get_history_distinguishes_empty_store(self):
        from src.sdk.tools_core.memory import memory_get_history

        with patch("src.sdk.tools_core.memory.get_message_store") as mock_get_store:
            mock_store = MagicMock()
            mock_store.get_messages.return_value = []
            mock_store.count_messages.return_value = 0
            mock_get_store.return_value = mock_store

            result = memory_get_history.invoke({"date_str": "2026-05-04", "user_id": TEST_USER_ID})

        assert "not been persisted" in result.lower()


class TestMemorySearch:
    """Tests for memory_search tool."""

    def test_memory_search_requires_query(self):
        """Test memory_search requires query parameter."""
        from src.sdk.tools_core.memory import memory_search

        try:
            memory_search.invoke({})
        except TypeError as e:
            assert "query" in str(e)
        else:
            raise AssertionError("memory_search should require query")

    def test_memory_search_empty_results(self):
        """Test memory_search with no results."""
        from src.sdk.tools_core.memory import memory_search

        with (
            patch("src.sdk.tools_core.memory.get_memory_store") as mock_get_memory_store,
            patch("src.sdk.tools_core.memory.get_message_store") as mock_get_message_store,
        ):
            mock_store = MagicMock()
            mock_store.find_facts_for_query.return_value = []
            mock_store.find_fact_history_for_query.return_value = []
            mock_get_memory_store.return_value = mock_store
            mock_conversation = MagicMock()
            mock_conversation.search_hybrid.return_value = []
            mock_conversation.get_messages.return_value = []
            mock_get_message_store.return_value = mock_conversation
            result = memory_search.invoke({"query": "nonexistent", "user_id": TEST_USER_ID})
            assert "no messages found" in result.lower() or "not found" in result.lower()

    def test_memory_search_with_results(self):
        """Test memory_search returns results."""
        from src.sdk.tools_core.memory import memory_search

        with (
            patch("src.sdk.tools_core.memory.get_memory_store") as mock_get_memory_store,
            patch("src.sdk.tools_core.memory.get_message_store") as mock_get_message_store,
        ):
            mock_store = MagicMock()
            mock_store.find_facts_for_query.return_value = []
            mock_store.find_fact_history_for_query.return_value = []
            mock_get_memory_store.return_value = mock_store
            mock_conversation = MagicMock()
            mock_conversation.search_hybrid.return_value = [
                SimpleNamespace(
                    id=1,
                    content="User prefers Python",
                    role="user",
                    score=0.9,
                    ts=datetime.now(UTC),
                )
            ]
            mock_get_message_store.return_value = mock_conversation
            result = memory_search.invoke({"query": "Python", "user_id": TEST_USER_ID})
            assert "Python" in result

    def test_llm_expand_queries_uses_provider_chat(self):
        from src.sdk.messages import Message
        from src.sdk.tools_core.memory import _llm_expand_queries

        class FakeProvider:
            def invoke(self, prompt):
                raise AssertionError("invoke should not be used")

            async def chat(self, messages):
                assert isinstance(messages[0], Message)
                return Message.assistant('["alpha", "beta"]')

        with patch("src.sdk.providers.factory.create_model_from_config", return_value=FakeProvider()):
            assert _llm_expand_queries("original") == ["alpha", "beta"]

    def test_memory_search_always_searches_messages_with_high_conf_facts(self):
        from src.sdk.tools_core.memory import memory_search

        fact = SimpleNamespace(
            id="f1",
            is_superseded=False,
            confidence=0.9,
            structured_data={"entity": "user", "attribute": "topic", "value": "pipeline"},
            trigger="topic",
            action="pipeline",
        )
        with (
            patch("src.sdk.tools_core.memory.get_memory_store") as mock_get_memory_store,
            patch("src.sdk.tools_core.memory.get_message_store") as mock_get_message_store,
            patch("src.sdk.tools_core.memory._expand_queries", return_value=["pipeline"]),
        ):
            mock_store = MagicMock()
            mock_store.find_facts_for_query.return_value = [fact, fact, fact]
            mock_store.find_fact_history_for_query.return_value = []
            mock_get_memory_store.return_value = mock_store
            mock_conversation = MagicMock()
            mock_conversation.search_hybrid.return_value = [
                SimpleNamespace(
                    id=1,
                    content="Deployment pipeline context",
                    role="user",
                    score=0.8,
                    ts=datetime.now(UTC),
                )
            ]
            mock_get_message_store.return_value = mock_conversation

            result = memory_search.invoke({"query": "pipeline", "user_id": TEST_USER_ID})

        mock_conversation.search_hybrid.assert_called()
        assert "Deployment pipeline" in result

    def test_memory_search_does_not_apply_second_recency_multiplier(self):
        from src.sdk.tools_core.memory import memory_search

        recent = SimpleNamespace(
            id=1,
            content="recent",
            role="user",
            score=0.5,
            ts=datetime.now(UTC),
        )
        older = SimpleNamespace(
            id=2,
            content="older",
            role="user",
            score=0.55,
            ts=datetime.now(UTC) - timedelta(days=60),
        )
        with (
            patch("src.sdk.tools_core.memory.get_memory_store") as mock_get_memory_store,
            patch("src.sdk.tools_core.memory.get_message_store") as mock_get_message_store,
            patch("src.sdk.tools_core.memory._expand_queries", return_value=["topic"]),
        ):
            mock_store = MagicMock()
            mock_store.find_facts_for_query.return_value = []
            mock_store.find_fact_history_for_query.return_value = []
            mock_get_memory_store.return_value = mock_store
            mock_conversation = MagicMock()
            mock_conversation.search_hybrid.return_value = [recent, older]
            mock_get_message_store.return_value = mock_conversation

            memory_search.invoke({"query": "topic", "user_id": TEST_USER_ID})

        assert recent.score == 0.5
        assert older.score == 0.55

    def test_cross_workspace_penalty_is_softened(self):
        from src.sdk.tools_core.memory import memory_search

        cross = SimpleNamespace(
            id=7,
            content="cross workspace",
            role="user",
            score=1.0,
            ts=datetime.now(UTC),
        )
        with (
            patch("src.sdk.tools_core.memory.get_memory_store") as mock_get_memory_store,
            patch("src.sdk.tools_core.memory.get_message_store") as mock_get_message_store,
            patch("src.sdk.tools_core.memory._expand_queries", return_value=["topic"]),
            patch("src.sdk.tools_core.memory._search_all_workspaces", return_value=(["other"], [(cross, "other")])) as xws,
        ):
            mock_store = MagicMock()
            mock_store.find_facts_for_query.return_value = []
            mock_store.find_fact_history_for_query.return_value = []
            mock_get_memory_store.return_value = mock_store
            mock_conversation = MagicMock()
            mock_conversation.search_hybrid.return_value = []
            mock_conversation.get_messages.return_value = []
            mock_get_message_store.return_value = mock_conversation

            memory_search.invoke({"query": "topic", "user_id": TEST_USER_ID})

        xws.assert_called()
        assert cross.score == 0.95

    def test_memory_search_includes_knowledge_update_resolution(self):
        from src.sdk.tools_core.memory import memory_search

        older = SimpleNamespace(
            id=1,
            content="You were pre-approved for $350,000 from Wells Fargo.",
            role="user",
            score=0.8,
            ts=datetime.now(UTC) - timedelta(days=2),
        )
        newer = SimpleNamespace(
            id=2,
            content="Remember when I got pre-approved for $400,000 from Wells Fargo?",
            role="user",
            score=0.9,
            ts=datetime.now(UTC),
        )
        with (
            patch("src.sdk.tools_core.memory.get_memory_store") as mock_get_memory_store,
            patch("src.sdk.tools_core.memory.get_message_store") as mock_get_message_store,
            patch("src.sdk.tools_core.memory._expand_queries", return_value=["pre-approved Wells Fargo"]),
        ):
            mock_store = MagicMock()
            mock_store.find_facts_for_query.return_value = []
            mock_store.find_fact_history_for_query.return_value = []
            mock_get_memory_store.return_value = mock_store
            mock_conversation = MagicMock()
            mock_conversation.search_hybrid.return_value = [older, newer]
            mock_conversation.db.raw_query.return_value = [
                {"id": 1, "metadata": '{"session_id": "s1"}'},
                {"id": 2, "metadata": '{"session_id": "s2"}'},
            ]
            mock_get_message_store.return_value = mock_conversation

            result = memory_search.invoke(
                {
                    "query": "What was the amount I was pre-approved for when I got my mortgage from Wells Fargo?",
                    "user_id": TEST_USER_ID,
                }
            )

        assert "KNOWLEDGE-UPDATE DETECTED" in result
        assert "updated=$400,000" in result


class TestTimeGet:
    """Tests for time_get tool."""

    def test_time_get_returns_time(self):
        """Test time_get returns current time."""
        from src.sdk.tools_core.time import time_get

        result = time_get.invoke({})
        assert len(result) > 0
        assert any(char.isdigit() for char in result)

    def test_time_get_with_timezone(self):
        """Test time_get with timezone parameter."""
        from src.sdk.tools_core.time import time_get

        result = time_get.invoke({"timezone": "America/New_York"})
        assert len(result) > 0


class TestShellExecute:
    """Tests for shell_execute tool."""

    def test_shell_execute_allowed_command(self):
        """Test shell_execute with allowed command."""
        from src.sdk.tools_core.shell import shell_execute

        result = shell_execute.invoke({"command": "echo hello", "user_id": TEST_USER_ID})
        assert "hello" in result.lower()

    def test_shell_execute_disallowed_command(self):
        """Test shell_execute rejects disallowed command."""
        from src.sdk.tools_core.shell import shell_execute

        result = shell_execute.invoke({"command": "rm -rf /", "user_id": TEST_USER_ID})
        assert "not allowed" in result.lower() or "error" in result.lower()

    def test_shell_execute_python(self):
        """Test shell_execute runs Python."""
        from src.sdk.tools_core.shell import shell_execute

        result = shell_execute.invoke(
            {"command": "python3 -c print(1+1)", "user_id": TEST_USER_ID}
        )
        assert "2" in result
