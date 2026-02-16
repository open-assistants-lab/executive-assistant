from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from langchain.agents.middleware import AgentMiddleware
from langchain.messages import AIMessage

if TYPE_CHECKING:
    from langchain.agents.middleware import AgentState, ModelRequest, ModelResponse
    from langgraph.runtime import Runtime


class CheckinMiddleware(AgentMiddleware):
    """Handle periodic check-ins with the user.

    This middleware enables the agent to periodically check in
    with the user, similar to a heartbeat mechanism.

    Usage:
        agent = create_deep_agent(
            model="gpt-4o",
            middleware=[CheckinMiddleware(
                interval_minutes=30,
                checklist=["Check pending tasks", "Review recent activity"]
            )],
        )
    """

    def __init__(
        self,
        interval_minutes: int = 30,
        active_hours_start: int = 8,
        active_hours_end: int = 22,
        checklist: list[str] | None = None,
        idle_threshold_hours: int = 8,
    ) -> None:
        super().__init__()
        self.interval_minutes = interval_minutes
        self.active_hours_start = active_hours_start
        self.active_hours_end = active_hours_end
        self.checklist = checklist or [
            "Check for pending tasks",
            "Review recent conversations for follow-ups",
            "Summarize any completed work",
        ]
        self.idle_threshold_hours = idle_threshold_hours

        self._last_checkin: datetime | None = None
        self._last_activity: datetime = datetime.now(timezone.utc)

    def _is_active_hours(self) -> bool:
        """Check if current time is within active hours."""
        now = datetime.now()
        hour = now.hour
        return self.active_hours_start <= hour < self.active_hours_end

    def _should_checkin(self, state: AgentState) -> bool:
        """Determine if a check-in should be triggered."""
        if not self._is_active_hours():
            return False

        now = datetime.now(timezone.utc)

        if self._last_checkin is None:
            return False

        minutes_since_checkin = (now - self._last_checkin).total_seconds() / 60
        if minutes_since_checkin < self.interval_minutes:
            return False

        return True

    def _is_user_initiated(self, state: AgentState) -> bool:
        """Check if this is a user-initiated message (not a check-in)."""
        messages = state.get("messages", [])
        if not messages:
            return True

        last_msg = messages[-1]
        if hasattr(last_msg, "type") and last_msg.type == "human":
            return True

        return False

    def before_model(
        self,
        state: AgentState,
        runtime: Runtime,
    ) -> dict[str, Any] | None:
        """Update last activity timestamp on user messages."""
        if self._is_user_initiated(state):
            self._last_activity = datetime.now(timezone.utc)

        return None

    async def abefore_model(
        self,
        state: AgentState,
        runtime: Runtime,
    ) -> dict[str, Any] | None:
        """Async version of update last activity timestamp on user messages."""
        return self.before_model(state, runtime)

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """Inject check-in context if appropriate."""
        messages = request.messages

        is_idle = self._check_idle_time()

        if is_idle and self._is_active_hours():
            checkin_prompt = self._build_checkin_prompt()
            new_system = self._append_checkin_context(request.system_message, checkin_prompt)
            return handler(request.override(system_message=new_system))

        return handler(request)

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        """Async version of inject check-in context if appropriate."""
        messages = request.messages

        is_idle = self._check_idle_time()

        if is_idle and self._is_active_hours():
            checkin_prompt = self._build_checkin_prompt()
            new_system = self._append_checkin_context(request.system_message, checkin_prompt)
            return await handler(request.override(system_message=new_system))

        return await handler(request)

    def _check_idle_time(self) -> bool:
        """Check if user has been idle for threshold."""
        now = datetime.now(timezone.utc)
        hours_idle = (now - self._last_activity).total_seconds() / 3600
        return hours_idle >= self.idle_threshold_hours

    def _build_checkin_prompt(self) -> str:
        """Build the check-in prompt."""
        checklist_items = "\n".join(f"- {item}" for item in self.checklist)

        return f"""
## Check-in Opportunity

The user has been idle for a while. Consider proactively checking in:

{checklist_items}

If there's nothing to report, respond normally without mentioning the check-in.
If there's something important, briefly mention it at the start of your response.
"""

    def _append_checkin_context(self, system_message, checkin_prompt: str) -> Any:
        """Append check-in context to system message."""
        from langchain.messages import SystemMessage

        existing_content = system_message.content

        if isinstance(existing_content, str):
            new_content = existing_content + checkin_prompt
        elif isinstance(existing_content, list):
            new_content = list(existing_content) + [{"type": "text", "text": checkin_prompt}]
        else:
            new_content = str(existing_content) + checkin_prompt

        return SystemMessage(content=new_content)

    def trigger_checkin(self) -> str | None:
        """Manually trigger a check-in.

        Returns a message if there's something to report, None otherwise.
        """
        self._last_checkin = datetime.now(timezone.utc)

        return None

    def get_status(self) -> dict:
        """Get check-in status."""
        now = datetime.now(timezone.utc)

        next_checkin = None
        if self._last_checkin:
            from datetime import timedelta

            next_checkin = self._last_checkin + timedelta(minutes=self.interval_minutes)

        return {
            "enabled": True,
            "interval_minutes": self.interval_minutes,
            "active_hours": {
                "start": self.active_hours_start,
                "end": self.active_hours_end,
            },
            "last_checkin": self._last_checkin.isoformat() if self._last_checkin else None,
            "next_checkin": next_checkin.isoformat() if next_checkin else None,
            "last_activity": self._last_activity.isoformat(),
            "is_active_hours": self._is_active_hours(),
        }
