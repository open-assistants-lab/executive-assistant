from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from langchain.agents.middleware import AgentMiddleware
from langchain.messages import AIMessage

if TYPE_CHECKING:
    from langchain.agents.middleware import AgentState
    from langgraph.runtime import Runtime


@dataclass
class RateLimitState:
    """Track rate limit state for a user."""

    model_calls: list[float] = field(default_factory=list)
    tool_calls: list[float] = field(default_factory=list)
    last_reset: float = field(default_factory=time.time)


class RateLimitMiddleware(AgentMiddleware):
    """Rate limit agent requests per user.

    Prevents abuse by limiting the number of model and tool calls
    within a time window.

    Usage:
        agent = create_deep_agent(
            model="gpt-4o",
            middleware=[RateLimitMiddleware(
                max_model_calls_per_minute=30,
                max_tool_calls_per_minute=60
            )],
        )
    """

    def __init__(
        self,
        max_model_calls_per_minute: int = 60,
        max_tool_calls_per_minute: int = 120,
        window_seconds: int = 60,
        default_user_id: str = "default",
    ) -> None:
        super().__init__()
        self.max_model_calls = max_model_calls_per_minute
        self.max_tool_calls = max_tool_calls_per_minute
        self.window_seconds = window_seconds
        self.default_user_id = default_user_id

        self._user_states: dict[str, RateLimitState] = defaultdict(RateLimitState)

    def _get_user_id(self, state: AgentState) -> str:
        """Extract user ID from state."""
        return state.get("user_id", self.default_user_id)

    def _cleanup_old_calls(self, state: RateLimitState) -> None:
        """Remove calls outside the time window."""
        now = time.time()
        cutoff = now - self.window_seconds

        state.model_calls = [t for t in state.model_calls if t > cutoff]
        state.tool_calls = [t for t in state.tool_calls if t > cutoff]

    def _check_model_limit(self, user_id: str) -> tuple[bool, int]:
        """Check if user can make another model call.

        Returns (allowed, remaining_calls).
        """
        state = self._user_states[user_id]
        self._cleanup_old_calls(state)

        remaining = self.max_model_calls - len(state.model_calls)
        allowed = remaining > 0

        return allowed, remaining

    def _check_tool_limit(self, user_id: str) -> tuple[bool, int]:
        """Check if user can make another tool call.

        Returns (allowed, remaining_calls).
        """
        state = self._user_states[user_id]
        self._cleanup_old_calls(state)

        remaining = self.max_tool_calls - len(state.tool_calls)
        allowed = remaining > 0

        return allowed, remaining

    def _record_model_call(self, user_id: str) -> None:
        """Record a model call."""
        state = self._user_states[user_id]
        state.model_calls.append(time.time())

    def _record_tool_call(self, user_id: str) -> None:
        """Record a tool call."""
        state = self._user_states[user_id]
        state.tool_calls.append(time.time())

    def before_model(
        self,
        state: AgentState,
        runtime: Runtime,
    ) -> dict[str, Any] | None:
        """Check rate limit before model call."""
        user_id = self._get_user_id(state)
        allowed, remaining = self._check_model_limit(user_id)

        if not allowed:
            retry_after = self.window_seconds
            return {
                "messages": [
                    AIMessage(
                        content=f"Rate limit exceeded. Please wait {retry_after} seconds before trying again."
                    )
                ],
                "jump_to": "end",
            }

        self._record_model_call(user_id)

        return None

    async def abefore_model(
        self,
        state: AgentState,
        runtime: Runtime,
    ) -> dict[str, Any] | None:
        """Async version of rate limit check before model call."""
        return self.before_model(state, runtime)

    def get_status(self, user_id: str | None = None) -> dict:
        """Get rate limit status for a user."""
        uid = user_id or self.default_user_id
        state = self._user_states[uid]
        self._cleanup_old_calls(state)

        model_allowed, model_remaining = self._check_model_limit(uid)
        tool_allowed, tool_remaining = self._check_tool_limit(uid)

        return {
            "user_id": uid,
            "model_calls": {
                "used": len(state.model_calls),
                "limit": self.max_model_calls,
                "remaining": model_remaining,
                "allowed": model_allowed,
            },
            "tool_calls": {
                "used": len(state.tool_calls),
                "limit": self.max_tool_calls,
                "remaining": tool_remaining,
                "allowed": tool_allowed,
            },
            "window_seconds": self.window_seconds,
        }

    def reset(self, user_id: str | None = None) -> None:
        """Reset rate limit for a user."""
        uid = user_id or self.default_user_id
        if uid in self._user_states:
            self._user_states[uid] = RateLimitState()
