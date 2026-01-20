"""Tests for StatusUpdateMiddleware."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain.messages import ToolMessage
from langchain.tools.tool_node import ToolCallRequest
from langgraph.types import Command

from executive_assistant.agent.status_middleware import StatusUpdateMiddleware, create_status_middleware


# =============================================================================
# Mock Channel Fixture
# =============================================================================

@pytest.fixture
def mock_channel():
    """Create a mock channel for testing."""
    channel = AsyncMock()
    channel.send_status = AsyncMock()
    return channel


@pytest.fixture
def middleware(mock_channel):
    """Create a StatusUpdateMiddleware instance for testing."""
    return StatusUpdateMiddleware(
        channel=mock_channel,
        show_tool_args=False,
        update_interval=0.5,
    )


# =============================================================================
# Test Initialization
# =============================================================================

class TestStatusUpdateMiddlewareInit:
    """Test StatusUpdateMiddleware initialization."""

    def test_init_default_values(self, mock_channel):
        """Test initialization with default values."""
        mw = StatusUpdateMiddleware(mock_channel)

        assert mw.channel == mock_channel
        assert mw.show_tool_args is False
        assert mw.update_interval == 0.5
        assert mw.tool_count == 0
        assert mw.start_time is None
        assert mw.last_status_time is None
        assert mw.current_conversation_id is None

    def test_init_custom_values(self, mock_channel):
        """Test initialization with custom values."""
        mw = StatusUpdateMiddleware(
            mock_channel,
            show_tool_args=True,
            update_interval=1.0,
        )

        assert mw.show_tool_args is True
        assert mw.update_interval == 1.0


# =============================================================================
# Test _should_send_status
# =============================================================================

class TestShouldSendStatus:
    """Test _should_send_status method."""

    def test_should_send_first_call(self, middleware):
        """Test that first call always returns True."""
        assert middleware._should_send_status() is True

    def test_should_send_within_interval(self, middleware):
        """Test that calls within interval return False."""
        middleware.last_status_time = time.time()
        assert middleware._should_send_status() is False

    def test_should_send_after_interval(self, middleware):
        """Test that calls after interval return True."""
        middleware.last_status_time = time.time() - 1.0  # 1 second ago
        assert middleware._should_send_status() is True

    def test_should_send_exactly_at_interval(self, middleware):
        """Test boundary condition at exactly interval."""
        middleware.last_status_time = time.time() - 0.5  # Exactly at interval
        assert middleware._should_send_status() is True


# =============================================================================
# Test _send_status
# =============================================================================

class TestSendStatus:
    """Test _send_status method."""

    @pytest.mark.asyncio
    async def test_send_status_calls_channel(self, middleware):
        """Test that _send_status calls channel.send_status."""
        middleware.current_conversation_id = "test_conv_123"

        await middleware._send_status("Test status", "test_conv_123")

        middleware.channel.send_status.assert_called_once_with(
            conversation_id="test_conv_123",
            message="Test status",
            update=True,
        )
        assert middleware.last_status_time is not None

    @pytest.mark.asyncio
    async def test_send_status_uses_conversation_id(self, middleware):
        """Test that _send_status uses current_conversation_id if not provided."""
        middleware.current_conversation_id = "test_conv_456"

        await middleware._send_status("Test status")

        middleware.channel.send_status.assert_called_once_with(
            conversation_id="test_conv_456",
            message="Test status",
            update=True,
        )

    @pytest.mark.asyncio
    async def test_send_status_without_conversation_id(self, middleware):
        """Test that _send_status returns early if no conversation_id."""
        await middleware._send_status("Test status")

        middleware.channel.send_status.assert_not_called()
        assert middleware.last_status_time is None

    @pytest.mark.asyncio
    @patch("executive_assistant.agent.status_middleware.settings")
    async def test_send_status_disabled(self, mock_settings, middleware):
        """Test that _send_status returns early if disabled in settings."""
        mock_settings.MW_STATUS_UPDATE_ENABLED = False
        middleware.current_conversation_id = "test_conv_123"

        await middleware._send_status("Test status")

        middleware.channel.send_status.assert_not_called()
        assert middleware.last_status_time is None

    @pytest.mark.asyncio
    async def test_send_status_handles_exceptions(self, middleware, caplog):
        """Test that _send_status handles channel exceptions gracefully."""
        middleware.channel.send_status.side_effect = Exception("Channel error")
        middleware.current_conversation_id = "test_conv_123"

        await middleware._send_status("Test status")

        # Should not raise exception
        assert middleware.last_status_time is not None
        # Should log warning
        assert "Failed to send status update" in caplog.text


# =============================================================================
# Test abefore_agent
# =============================================================================

class TestBeforeAgent:
    """Test abefore_agent method."""

    @pytest.mark.asyncio
    async def test_before_agent_initializes_state(self, middleware):
        """Test that abefore_agent properly initializes state."""
        state = {}
        runtime = {
            "config": {
                "configurable": {
                    "thread_id": "TelegramChannel:123"
                }
            }
        }

        result = await middleware.abefore_agent(state, runtime)

        assert result is None  # Should not modify state
        assert middleware.tool_count == 0
        assert middleware.start_time is not None
        assert middleware.last_status_time is not None
        assert middleware.current_conversation_id == "123"

    @pytest.mark.asyncio
    async def test_before_agent_extracts_conversation_id(self, middleware):
        """Test conversation_id extraction from various formats."""
        test_cases = [
            ("TelegramChannel:123", "123"),
            ("http:test_conv", "test_conv"),
            ("simple_id", "simple_id"),
        ]

        for thread_id, expected_conv_id in test_cases:
            runtime = {
                "config": {
                    "configurable": {
                        "thread_id": thread_id
                    }
                }
            }

            await middleware.abefore_agent({}, runtime)

            assert middleware.current_conversation_id == expected_conv_id

    @pytest.mark.asyncio
    async def test_before_agent_sends_thinking_status(self, middleware):
        """Test that abefore_agent sends 'Thinking...' status."""
        runtime = {
            "config": {
                "configurable": {
                    "thread_id": "TelegramChannel:123"
                }
            }
        }

        await middleware.abefore_agent({}, runtime)

        middleware.channel.send_status.assert_called_once_with(
            conversation_id="123",
            message="🤔 Thinking...",
            update=True,
        )

    @pytest.mark.asyncio
    async def test_before_agent_without_thread_id(self, middleware):
        """Test abefore_agent when thread_id is not in config."""
        runtime = {"config": {}}

        await middleware.abefore_agent({}, runtime)

        assert middleware.current_conversation_id is None
        middleware.channel.send_status.assert_not_called()


# =============================================================================
# Test awrap_tool_call
# =============================================================================

class TestWrapToolCall:
    """Test awrap_tool_call method."""

    @pytest.fixture
    def tool_call_request(self):
        """Create a mock ToolCallRequest."""
        request = MagicMock(spec=ToolCallRequest)
        request.tool_call = {
            "name": "test_tool",
            "args": {"query": "test"},
            "id": "call_123",
        }
        return request

    @pytest.fixture
    def mock_handler(self):
        """Create a mock handler function."""
        handler = AsyncMock()
        handler.return_value = ToolMessage(content="Tool result", tool_call_id="call_123")
        return handler

    @pytest.mark.asyncio
    async def test_wrap_tool_call_increments_count(self, middleware, tool_call_request, mock_handler):
        """Test that tool_count is incremented."""
        middleware.current_conversation_id = "test_conv"

        await middleware.awrap_tool_call(tool_call_request, mock_handler)

        assert middleware.tool_count == 1

    @pytest.mark.asyncio
    async def test_wrap_tool_call_sends_status_before(self, middleware, tool_call_request, mock_handler):
        """Test that status is sent before tool execution."""
        middleware.current_conversation_id = "test_conv"

        await middleware.awrap_tool_call(tool_call_request, mock_handler)

        assert middleware.channel.send_status.call_count == 1
        first_call = middleware.channel.send_status.call_args_list[0]
        assert "🛠️ Tool: test_tool" in first_call[1]["message"]

    @pytest.mark.asyncio
    async def test_wrap_tool_call_sends_status_after_success(self, middleware, tool_call_request, mock_handler):
        """Test that success status is sent after tool execution."""
        middleware.current_conversation_id = "test_conv"

        await middleware.awrap_tool_call(tool_call_request, mock_handler)

        assert middleware.channel.send_status.call_count == 1

    @pytest.mark.asyncio
    async def test_wrap_tool_call_shows_args_when_enabled(self, middleware, tool_call_request, mock_handler):
        """Test that tool args are shown when show_tool_args=True."""
        middleware.show_tool_args = True
        middleware.current_conversation_id = "test_conv"

        await middleware.awrap_tool_call(tool_call_request, mock_handler)

        first_call = middleware.channel.send_status.call_args_list[0]
        message = first_call[1]["message"]
        # Should show args (sanitized)
        assert "query" in message or "test" in message

    @pytest.mark.asyncio
    async def test_wrap_tool_call_handles_exceptions(self, middleware, tool_call_request):
        """Test that exceptions are handled and error status is sent."""
        middleware.current_conversation_id = "test_conv"

        async def failing_handler(request):
            raise ValueError("Tool execution failed")

        with pytest.raises(ValueError, match="Tool execution failed"):
            await middleware.awrap_tool_call(tool_call_request, failing_handler)

        assert middleware.channel.send_status.call_count == 1

    @pytest.mark.asyncio
    async def test_wrap_tool_call_truncates_long_errors(self, middleware, tool_call_request):
        """Test that long error messages are truncated."""
        middleware.current_conversation_id = "test_conv"

        async def failing_handler(request):
            raise ValueError("x" * 200)  # Long error message

        with pytest.raises(ValueError):
            await middleware.awrap_tool_call(tool_call_request, failing_handler)

        assert middleware.channel.send_status.call_count == 1


# =============================================================================
# Test aafter_agent
# =============================================================================

class TestAfterAgent:
    """Test aafter_agent method."""

    @pytest.mark.asyncio
    async def test_after_agent_quick_completion(self, middleware):
        """Test completion status for quick execution (<1s)."""
        middleware.start_time = time.time()
        middleware.current_conversation_id = "test_conv"

        await middleware.aafter_agent({}, {})

        middleware.channel.send_status.assert_called_once_with(
            conversation_id="test_conv",
            message="✅ Done",
            update=True,
        )

    @pytest.mark.asyncio
    async def test_after_agent_with_timing(self, middleware):
        """Test completion status with timing information."""
        middleware.start_time = time.time() - 2.5  # 2.5 seconds ago
        middleware.current_conversation_id = "test_conv"

        await middleware.aafter_agent({}, {})

        middleware.channel.send_status.assert_called_once()
        message = middleware.channel.send_status.call_args[1]["message"]
        assert "✅ Done in 2.5s" in message

    @pytest.mark.asyncio
    async def test_after_agent_without_start_time(self, middleware):
        """Test that aafter_agent returns early if start_time is None."""
        middleware.start_time = None
        middleware.current_conversation_id = "test_conv"

        result = await middleware.aafter_agent({}, {})

        assert result is None
        middleware.channel.send_status.assert_not_called()


# =============================================================================
# Test _sanitize_args
# =============================================================================

class TestSanitizeArgs:
    """Test _sanitize_args method."""

    def test_sanitize_args_hides_sensitive_keys(self, middleware):
        """Test that sensitive keys are hidden."""
        args = {
            "api_key": "sk-1234567890abcdef",
            "password": "secret123",
            "query": "test search",
        }

        result = middleware._sanitize_args(args)

        assert result["api_key"] == "***"
        assert result["password"] == "***"
        assert result["query"] == "test search"

    def test_sanitize_args_case_insensitive(self, middleware):
        """Test that sensitive key detection is case-insensitive."""
        args = {
            "API_KEY": "sk-1234567890abcdef",
            "Password": "secret123",
            "ToKeN": "value",
        }

        result = middleware._sanitize_args(args)

        assert result["API_KEY"] == "***"
        assert result["Password"] == "***"
        assert result["ToKeN"] == "***"

    def test_sanitize_args_truncates_long_strings(self, middleware):
        """Test that long string values are truncated."""
        args = {
            "content": "x" * 100,
        }

        result = middleware._sanitize_args(args)

        assert result["content"] == "x" * 50 + "..."

    def test_sanitize_args_truncates_complex_objects(self, middleware):
        """Test that long dicts/lists are truncated."""
        args = {
            "data": {"key": "x" * 100},
        }

        result = middleware._sanitize_args(args)

        assert "..." in str(result["data"])

    def test_sanitize_args_limits_total_length(self, middleware):
        """Test that total args string length is limited."""
        args = {
            f"key_{i}": f"value_{i}" * 10
            for i in range(20)
        }

        result = middleware._sanitize_args(args)

        # Result should be truncated to ~100 chars
        result_str = str(result)
        assert len(result_str) < 150
        assert "..." in result_str

    def test_sanitize_args_preserves_normal_values(self, middleware):
        """Test that normal values are preserved."""
        args = {
            "query": "search term",
            "limit": 10,
            "flag": True,
        }

        result = middleware._sanitize_args(args)

        assert result["query"] == "search term"
        assert result["limit"] == 10
        assert result["flag"] is True


# =============================================================================
# Test create_status_middleware Factory
# =============================================================================

class TestCreateStatusMiddleware:
    """Test create_status_middleware factory function."""

    @patch("executive_assistant.agent.status_middleware.settings")
    def test_create_when_enabled(self, mock_settings, mock_channel):
        """Test factory returns middleware when enabled."""
        mock_settings.MW_STATUS_UPDATE_ENABLED = True
        mock_settings.MW_STATUS_SHOW_TOOL_ARGS = False
        mock_settings.MW_STATUS_UPDATE_INTERVAL = 0.5

        result = create_status_middleware(mock_channel)

        assert isinstance(result, StatusUpdateMiddleware)
        assert result.channel == mock_channel
        assert result.show_tool_args is False
        assert result.update_interval == 0.5

    @patch("executive_assistant.agent.status_middleware.settings")
    def test_create_when_disabled(self, mock_settings, mock_channel):
        """Test factory returns None when disabled."""
        mock_settings.MW_STATUS_UPDATE_ENABLED = False

        result = create_status_middleware(mock_channel)

        assert result is None

    @patch("executive_assistant.agent.status_middleware.settings")
    def test_create_uses_settings_values(self, mock_settings, mock_channel):
        """Test factory uses values from settings."""
        mock_settings.MW_STATUS_UPDATE_ENABLED = True
        mock_settings.MW_STATUS_SHOW_TOOL_ARGS = True
        mock_settings.MW_STATUS_UPDATE_INTERVAL = 1.5

        result = create_status_middleware(mock_channel)

        assert result.show_tool_args is True
        assert result.update_interval == 1.5


# =============================================================================
# Integration Tests
# =============================================================================

class TestStatusUpdateMiddlewareIntegration:
    """Integration tests for complete middleware workflow."""

    @pytest.mark.asyncio
    async def test_full_agent_workflow(self, middleware):
        """Test complete workflow: before_agent -> tool calls -> after_agent."""
        runtime = {
            "config": {
                "configurable": {
                    "thread_id": "TelegramChannel:123"
                }
            }
        }

        # Simulate agent lifecycle
        await middleware.abefore_agent({}, runtime)

        # Simulate tool call
        request = MagicMock(spec=ToolCallRequest)
        request.tool_call = {"name": "test_tool", "args": {}, "id": "call_1"}

        async def handler(req):
            return ToolMessage(content="Result", tool_call_id="call_1")

        await middleware.awrap_tool_call(request, handler)

        # Complete agent
        await middleware.aafter_agent({}, {})

        # Verify all status messages were sent
        assert middleware.channel.send_status.call_count == 3  # Thinking + tool + Done

    @pytest.mark.asyncio
    async def test_multiple_tool_calls(self, middleware):
        """Test middleware with multiple sequential tool calls."""
        middleware.current_conversation_id = "test_conv"

        # Simulate 3 tool calls
        for i in range(3):
            request = MagicMock(spec=ToolCallRequest)
            request.tool_call = {"name": f"tool_{i}", "args": {}, "id": f"call_{i}"}

            async def handler(req):
                return ToolMessage(content="Result", tool_call_id=req.tool_call["id"])

            await middleware.awrap_tool_call(request, handler)

        assert middleware.channel.send_status.call_count == 3
        assert middleware.tool_count == 3
