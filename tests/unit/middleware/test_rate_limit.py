"""Unit tests for RateLimitMiddleware.

Tests rate limiting, window cleanup, status reporting.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from unittest.mock import MagicMock

import pytest
from langchain.messages import AIMessage

from src.middleware.rate_limit import RateLimitMiddleware, RateLimitState


@dataclass
class MockAgentState:
    """Mock agent state for testing."""
    user_id: str = "test-user"
    messages: list = field(default_factory=list)


class TestRateLimitState:
    """Test suite for RateLimitState."""

    def test_default_state(self):
        """Test default state values."""
        state = RateLimitState()

        assert state.model_calls == []
        assert state.tool_calls == []
        assert state.last_reset > 0

    def test_state_with_initial_values(self):
        """Test state with initial values."""
        now = time.time()
        state = RateLimitState(
            model_calls=[now, now - 10],
            tool_calls=[now - 5],
            last_reset=now - 100,
        )

        assert len(state.model_calls) == 2
        assert len(state.tool_calls) == 1


class TestRateLimitMiddleware:
    """Test suite for RateLimitMiddleware."""

    def test_initialization(self):
        """Test middleware initialization."""
        middleware = RateLimitMiddleware(
            max_model_calls_per_minute=30,
            max_tool_calls_per_minute=60,
            window_seconds=60,
            default_user_id="default",
        )

        assert middleware.max_model_calls == 30
        assert middleware.max_tool_calls == 60
        assert middleware.window_seconds == 60
        assert middleware.default_user_id == "default"

    def test_get_user_id_from_state(self):
        """Test extracting user ID from state."""
        middleware = RateLimitMiddleware()

        state = MockAgentState(user_id="custom-user")
        user_id = middleware._get_user_id(state)

        assert user_id == "custom-user"

    def test_get_user_id_default(self):
        """Test default user ID when not in state."""
        middleware = RateLimitMiddleware(default_user_id="default-user")

        state = MockAgentState()  # No user_id
        user_id = middleware._get_user_id(state)

        assert user_id == "default-user"

    def test_cleanup_old_calls(self):
        """Test cleanup of calls outside time window."""
        middleware = RateLimitMiddleware(window_seconds=60)

        now = time.time()
        state = RateLimitState(
            model_calls=[now - 120, now - 90, now - 30],  # 2 outside, 1 inside
            tool_calls=[now - 100, now - 10],  # 1 outside, 1 inside
        )

        middleware._cleanup_old_calls(state)

        assert len(state.model_calls) == 1
        assert len(state.tool_calls) == 1

    def test_check_model_limit_within_limit(self):
        """Test model limit check when within limit."""
        middleware = RateLimitMiddleware(
            max_model_calls_per_minute=10,
            window_seconds=60,
        )

        now = time.time()
        state = RateLimitState(model_calls=[now - 10, now - 20, now - 30])

        allowed, remaining = middleware._check_model_limit("user-123")

        assert allowed == True
        assert remaining == 7  # 10 - 3

    def test_check_model_limit_exceeded(self):
        """Test model limit check when limit exceeded."""
        middleware = RateLimitMiddleware(
            max_model_calls_per_minute=5,
            window_seconds=60,
        )

        now = time.time()
        state = RateLimitState(model_calls=[now - i for i in range(10)])  # 10 calls

        allowed, remaining = middleware._check_model_limit("user-123")

        assert allowed == False
        assert remaining <= 0

    def test_check_tool_limit_within_limit(self):
        """Test tool limit check when within limit."""
        middleware = RateLimitMiddleware(
            max_tool_calls_per_minute=20,
            window_seconds=60,
        )

        now = time.time()
        state = RateLimitState(tool_calls=[now - i for i in range(5)])

        allowed, remaining = middleware._check_tool_limit("user-123")

        assert allowed == True
        assert remaining == 15  # 20 - 5

    def test_check_tool_limit_exceeded(self):
        """Test tool limit check when limit exceeded."""
        middleware = RateLimitMiddleware(
            max_tool_calls_per_minute=10,
            window_seconds=60,
        )

        now = time.time()
        state = RateLimitState(tool_calls=[now - i for i in range(15)])

        allowed, remaining = middleware._check_tool_limit("user-123")

        assert allowed == False
        assert remaining <= 0

    def test_record_model_call(self):
        """Test recording a model call."""
        middleware = RateLimitMiddleware()

        before_count = len(middleware._user_states["user-123"].model_calls)
        middleware._record_model_call("user-123")
        after_count = len(middleware._user_states["user-123"].model_calls)

        assert after_count == before_count + 1

    def test_record_tool_call(self):
        """Test recording a tool call."""
        middleware = RateLimitMiddleware()

        before_count = len(middleware._user_states["user-123"].tool_calls)
        middleware._record_tool_call("user-123")
        after_count = len(middleware._user_states["user-123"].tool_calls)

        assert after_count == before_count + 1

    def test_before_model_allows_within_limit(self):
        """Test before_model allows call when within limit."""
        middleware = RateLimitMiddleware(
            max_model_calls_per_minute=10,
        )

        state = MockAgentState(user_id="user-123")
        runtime = MagicMock()

        result = middleware.before_model(state, runtime)

        # Should return None (allow call)
        assert result is None

    def test_before_model_blocks_when_exceeded(self):
        """Test before_model blocks call when limit exceeded."""
        middleware = RateLimitMiddleware(
            max_model_calls_per_minute=1,
            window_seconds=60,
        )

        state = MockAgentState(user_id="user-123")
        runtime = MagicMock()

        # First call should succeed
        result1 = middleware.before_model(state, runtime)
        assert result1 is None

        # Second call should be blocked
        result2 = middleware.before_model(state, runtime)
        assert result2 is not None
        assert "messages" in result2
        assert "jump_to" in result2

        # Check error message
        assert len(result2["messages"]) == 1
        assert isinstance(result2["messages"][0], AIMessage)
        assert "Rate limit exceeded" in result2["messages"][0].content

    def test_per_user_isolation(self):
        """Test that rate limits are isolated per user."""
        middleware = RateLimitMiddleware(
            max_model_calls_per_minute=2,
        )

        state1 = MockAgentState(user_id="user-1")
        state2 = MockAgentState(user_id="user-2")
        runtime = MagicMock()

        # User 1 makes 2 calls
        middleware.before_model(state1, runtime)
        middleware.before_model(state1, runtime)

        # User 1 should be blocked
        result1 = middleware.before_model(state1, runtime)
        assert result1 is not None

        # User 2 should still be allowed
        result2 = middleware.before_model(state2, runtime)
        assert result2 is None

    def test_get_status(self):
        """Test getting rate limit status."""
        middleware = RateLimitMiddleware(
            max_model_calls_per_minute=10,
            max_tool_calls_per_minute=20,
            window_seconds=60,
        )

        # Make some calls
        middleware._record_model_call("user-123")
        middleware._record_model_call("user-123")
        middleware._record_tool_call("user-123")

        status = middleware.get_status("user-123")

        assert "user_id" in status
        assert status["user_id"] == "user-123"
        assert "model_calls" in status
        assert status["model_calls"]["used"] == 2
        assert status["model_calls"]["limit"] == 10
        assert status["model_calls"]["remaining"] == 8
        assert status["model_calls"]["allowed"] == True
        assert "tool_calls" in status
        assert status["tool_calls"]["used"] == 1
        assert status["tool_calls"]["limit"] == 20
        assert status["tool_calls"]["remaining"] == 19
        assert status["tool_calls"]["allowed"] == True
        assert status["window_seconds"] == 60

    def test_get_status_default_user(self):
        """Test getting status for default user."""
        middleware = RateLimitMiddleware(default_user_id="default-user")

        status = middleware.get_status()

        assert status["user_id"] == "default-user"

    def test_reset(self):
        """Test resetting rate limit for a user."""
        middleware = RateLimitMiddleware(
            max_model_calls_per_minute=10,
        )

        # Make some calls
        middleware._record_model_call("user-123")
        middleware._record_model_call("user-123")

        # Verify calls were recorded
        status_before = middleware.get_status("user-123")
        assert status_before["model_calls"]["used"] == 2

        # Reset
        middleware.reset("user-123")

        # Verify reset
        status_after = middleware.get_status("user-123")
        assert status_after["model_calls"]["used"] == 0

    def test_reset_default_user(self):
        """Test resetting default user."""
        middleware = RateLimitMiddleware(default_user_id="default-user")

        middleware._record_model_call("default-user")
        middleware.reset()

        status = middleware.get_status()
        assert status["model_calls"]["used"] == 0

    def test_window_expiration(self):
        """Test that old calls expire outside the window."""
        middleware = RateLimitMiddleware(
            max_model_calls_per_minute=5,
            window_seconds=2,  # 2 second window
        )

        state = MockAgentState(user_id="user-123")
        runtime = MagicMock()

        # Make 5 calls (should hit limit)
        for _ in range(5):
            middleware.before_model(state, runtime)

        # Should be blocked
        result = middleware.before_model(state, runtime)
        assert result is not None

        # Wait for window to expire
        time.sleep(2.1)

        # Should now be allowed (old calls expired)
        result = middleware.before_model(state, runtime)
        assert result is None

    def test_different_windows_for_model_and_tool(self):
        """Test that model and tool calls have separate windows."""
        middleware = RateLimitMiddleware(
            max_model_calls_per_minute=1,
            max_tool_calls_per_minute=10,
            window_seconds=60,
        )

        state = MockAgentState(user_id="user-123")
        runtime = MagicMock()

        # Exhaust model calls
        result1 = middleware.before_model(state, runtime)
        assert result1 is None

        result2 = middleware.before_model(state, runtime)
        assert result2 is not None  # Blocked

        # But tool calls should still be available
        status = middleware.get_status("user-123")
        assert status["tool_calls"]["allowed"] == True
        assert status["tool_calls"]["remaining"] == 10
