"""Unit tests for todos tools."""


class TestTodosStorageFunctions:
    """Tests for todos storage functions."""

    def test_get_db_path(self):
        """Test getting database path."""
        from src.tools.todos.storage import get_db_path

        path = get_db_path("test_user")
        assert "test_user" in path
        assert "todos.db" in path
