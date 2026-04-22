"""Unit tests for memory tools."""

from unittest.mock import MagicMock, patch

TEST_USER_ID = "test_memory_user"


class TestMemoryGetHistory:
    """Tests for memory_get_history tool."""

    def test_memory_get_history_empty(self):
        """Test memory_get_history with empty result."""
        from src.sdk.tools_core.memory import memory_get_history

        with patch("src.storage.messages.get_conversation_store") as mock_get_store:
            mock_store = MagicMock()
            mock_store.get_messages.return_value = []
            mock_get_store.return_value = mock_store
            result = memory_get_history.invoke({"user_id": TEST_USER_ID})
            assert "no messages" in result.lower() or "empty" in result.lower()

    def test_memory_get_history_with_messages(self):
        """Test memory_get_history returns messages."""
        from src.sdk.tools_core.memory import memory_get_history

        mock_messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        with patch("src.storage.messages.get_conversation_store") as mock_get_store:
            mock_store = MagicMock()
            mock_store.get_messages.return_value = mock_messages
            mock_get_store.return_value = mock_store
            result = memory_get_history.invoke({"user_id": TEST_USER_ID})
            assert "Hello" in result or "Hi" in result


class TestMemorySearch:
    """Tests for memory_search tool."""

    def test_memory_search_requires_query(self):
        """Test memory_search requires query parameter."""
        from src.sdk.tools_core.memory import memory_search

        result = memory_search.invoke({})
        assert "Error" in result or "required" in result.lower()

    def test_memory_search_empty_results(self):
        """Test memory_search with no results."""
        from src.sdk.tools_core.memory import memory_search

        with patch("src.storage.memory.get_memory_store") as mock_get_store:
            mock_store = MagicMock()
            mock_store.search.return_value = []
            mock_get_store.return_value = mock_store
            result = memory_search.invoke({"query": "nonexistent", "user_id": TEST_USER_ID})
            assert "no memories found" in result.lower() or "not found" in result.lower()

    def test_memory_search_with_results(self):
        """Test memory_search returns results."""
        from src.sdk.tools_core.memory import memory_search

        mock_results = [{"content": "User prefers Python", "relevance": 0.9}]
        with patch("src.storage.memory.get_memory_store") as mock_get_store:
            mock_store = MagicMock()
            mock_store.search.return_value = mock_results
            mock_get_store.return_value = mock_store
            result = memory_search.invoke({"query": "Python", "user_id": TEST_USER_ID})
            assert "Python" in result


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
            {"command": "python3 -c 'print(1+1)'", "user_id": TEST_USER_ID}
        )
        assert "2" in result
