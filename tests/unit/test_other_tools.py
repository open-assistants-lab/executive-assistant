"""Unit tests for shell, memory, firecrawl, and other tools."""


class TestShellTool:
    """Tests for shell execution tool."""

    def test_shell_execute_with_command(self):
        """Test shell_execute works."""
        from src.tools.shell import shell_execute

        result = shell_execute.invoke({"command": "echo hello", "user_id": "test"})
        assert "hello" in result


class TestTimeTool:
    """Tests for time tool."""

    def test_time_get(self):
        """Test time_get returns current time."""
        from src.tools.time import time_get

        result = time_get.invoke({"user_id": "test"})
        assert isinstance(result, str)
        assert len(result) > 0
