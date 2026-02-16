"""Unit tests for LoggingMiddleware.

Tests JSONL logging, all event types, error handling.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.middleware.logging_middleware import LoggingMiddleware


class TestLoggingMiddleware:
    """Test suite for LoggingMiddleware."""

    def test_log_directory_creation(self, tmp_path):
        """Test that log directory is created if it doesn't exist."""
        log_dir = tmp_path / "logs"
        middleware = LoggingMiddleware(log_dir=log_dir, user_id="test-user")

        assert log_dir.exists()
        assert log_dir.is_dir()

    def test_log_file_creation(self, tmp_path):
        """Test that log file is created with correct name."""
        log_dir = tmp_path / "logs"
        middleware = LoggingMiddleware(log_dir=log_dir, user_id="test-user")

        log_file = middleware._get_log_file()
        expected_name = f"agent-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.jsonl"

        assert log_file.name == expected_name
        assert log_file.parent == log_dir

    def test_log_entry_format(self, tmp_path):
        """Test that log entries have correct format."""
        log_dir = tmp_path / "logs"
        middleware = LoggingMiddleware(log_dir=log_dir, user_id="test-user")

        middleware._log("test_event", {"key": "value"})

        log_file = middleware._get_log_file()
        assert log_file.exists()

        content = log_file.read_text()
        assert '"timestamp":' in content
        assert '"user_id": "test-user"' in content
        assert '"event": "test_event"' in content
        assert '"data":' in content
        assert '"key": "value"' in content

    def test_log_model_calls_disabled(self, tmp_path, mock_agent_state, mock_runtime):
        """Test that model call logging can be disabled."""
        log_dir = tmp_path / "logs"
        middleware = LoggingMiddleware(
            log_dir=log_dir,
            user_id="test-user",
            log_model_calls=False,  # Disabled
        )

        middleware.before_model(mock_agent_state, mock_runtime)

        # Should not create log file
        log_file = middleware._get_log_file()
        assert not log_file.exists()

    def test_before_model_logging(self, tmp_path, mock_agent_state, mock_runtime):
        """Test logging before model call."""
        log_dir = tmp_path / "logs"
        middleware = LoggingMiddleware(log_dir=log_dir, user_id="test-user")

        middleware.before_model(mock_agent_state, mock_runtime)

        log_file = middleware._get_log_file()
        content = log_file.read_text()

        assert "model_call_start" in content

    def test_after_model_logging(self, tmp_path, mock_agent_state, mock_runtime):
        """Test logging after model call."""
        log_dir = tmp_path / "logs"
        middleware = LoggingMiddleware(log_dir=log_dir, user_id="test-user")

        middleware.after_model(mock_agent_state, mock_runtime)

        log_file = middleware._get_log_file()
        content = log_file.read_text()

        assert "model_call_end" in content

    def test_wrap_model_call_timing(self, tmp_path, mock_model_request, mock_handler):
        """Test that wrap_model_call tracks timing."""
        import time

        log_dir = tmp_path / "logs"
        middleware = LoggingMiddleware(log_dir=log_dir, user_id="test-user")

        middleware.wrap_model_call(mock_model_request, mock_handler)

        log_file = middleware._get_log_file()
        content = log_file.read_text()

        assert "model_call_complete" in content
        assert '"duration_ms":' in content

    def test_wrap_model_call_error_logging(self, tmp_path, mock_model_request):
        """Test that errors in model calls are logged."""
        log_dir = tmp_path / "logs"
        middleware = LoggingMiddleware(log_dir=log_dir, user_id="test-user")

        async def failing_handler(request):
            raise ValueError("Test error")

        try:
            middleware.wrap_model_call(mock_model_request, failing_handler)
        except ValueError:
            pass  # Expected to raise

        log_file = middleware._get_log_file()
        content = log_file.read_text()

        assert "model_call_error" in content
        assert "Test error" in content
        assert '"error_type": "ValueError"' in content

    def test_log_tool_calls(self, tmp_path):
        """Test tool call logging."""
        from langchain.tools.tool_node import ToolCallRequest

        log_dir = tmp_path / "logs"
        middleware = LoggingMiddleware(log_dir=log_dir, user_id="test-user")

        tool_call = {
            "name": "test_tool",
            "args": {"arg1": "value1"},
            "id": "test_id",
        }

        request = ToolCallRequest(tool_call=tool_call, raw=None)

        async def handler(request):
            from langchain.messages import ToolMessage
            return ToolMessage(content="Result", tool_call_id="test_id")

        middleware.wrap_tool_call(request, handler)

        log_file = middleware._get_log_file()
        content = log_file.read_text()

        assert "tool_call_start" in content
        assert "tool_call_end" in content
        assert '"tool": "test_tool"' in content

    def test_log_tool_calls_disabled(self, tmp_path):
        """Test that tool call logging can be disabled."""
        from langchain.tools.tool_node import ToolCallRequest

        log_dir = tmp_path / "logs"
        middleware = LoggingMiddleware(
            log_dir=log_dir,
            user_id="test-user",
            log_tool_calls=False,  # Disabled
        )

        tool_call = {"name": "test_tool", "args": {}, "id": "test_id"}
        request = ToolCallRequest(tool_call=tool_call, raw=None)

        async def handler(request):
            from langchain.messages import ToolMessage
            return ToolMessage(content="Result", tool_call_id="test_id")

        middleware.wrap_tool_call(request, handler)

        # Should not log tool calls
        log_file = middleware._get_log_file()
        assert not log_file.exists() or "tool_call" not in log_file.read_text()

    def test_after_agent_logging(self, tmp_path, mock_agent_state, mock_runtime):
        """Test logging after agent completion."""
        log_dir = tmp_path / "logs"
        middleware = LoggingMiddleware(log_dir=log_dir, user_id="test-user")

        middleware.after_agent(mock_agent_state, mock_runtime)

        log_file = middleware._get_log_file()
        content = log_file.read_text()

        assert "agent_complete" in content
        assert '"total_messages":' in content

    def test_log_errors_disabled(self, tmp_path, mock_model_request):
        """Test that error logging can be disabled."""
        log_dir = tmp_path / "logs"
        middleware = LoggingMiddleware(
            log_dir=log_dir,
            user_id="test-user",
            log_errors=False,  # Disabled
        )

        async def failing_handler(request):
            raise ValueError("Test error")

        try:
            middleware.wrap_model_call(mock_model_request, failing_handler)
        except ValueError:
            pass

        # Should not log errors
        log_file = middleware._get_log_file()
        assert not log_file.exists() or "model_call_error" not in log_file.read_text()

    def test_multiple_log_entries(self, tmp_path, mock_agent_state, mock_runtime):
        """Test that multiple log entries are written correctly."""
        log_dir = tmp_path / "logs"
        middleware = LoggingMiddleware(log_dir=log_dir, user_id="test-user")

        # Log multiple events
        middleware._log("event1", {"data": "value1"})
        middleware._log("event2", {"data": "value2"})
        middleware._log("event3", {"data": "value3"})

        log_file = middleware._get_log_file()
        lines = log_file.read_text().strip().split("\n")

        assert len(lines) == 3
        assert "event1" in lines[0]
        assert "event2" in lines[1]
        assert "event3" in lines[2]

    def test_custom_log_dir(self, tmp_path):
        """Test using a custom log directory."""
        custom_dir = tmp_path / "custom_logs"
        middleware = LoggingMiddleware(log_dir=custom_dir, user_id="test-user")

        middleware._log("test", {})

        log_file = middleware._get_log_file()
        assert custom_dir in log_file.parents
        assert log_file.exists()

    def test_user_id_in_log_entries(self, tmp_path):
        """Test that user_id is included in log entries."""
        log_dir = tmp_path / "logs"
        middleware = LoggingMiddleware(log_dir=log_dir, user_id="custom-user-123")

        middleware._log("test", {})

        log_file = middleware._get_log_file()
        content = log_file.read_text()

        assert '"user_id": "custom-user-123"' in content
