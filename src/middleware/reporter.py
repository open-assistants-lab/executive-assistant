"""Middleware reporter for visibility.

Middlewares can use this to report their activity during execution.
"""

from contextvars import ContextVar
from typing import Any

# Context variable to store the current state update callback
_state_update_callback: ContextVar = ContextVar("state_update_callback", default=None)


def set_state_update_callback(callback: Any) -> None:
    """Set the state update callback for the current context.

    Args:
        callback: Function to call to update state with middleware activity
    """
    _state_update_callback.set(callback)


def report_middleware_activity(
    name: str,
    status: str,
    message: str = "",
    details: dict | None = None,
) -> None:
    """Report middleware activity.

    This should be called by middlewares to report their activity.

    Args:
        name: Middleware name
        status: Status (active, completed, skipped, failed)
        message: Optional status message
        details: Optional additional details

    Example:
        >>> from src.middleware.reporter import report_middleware_activity
        >>>
        >>> class MyMiddleware(AgentMiddleware):
        >>>     async def before_model(self, ...):
        >>>         report_middleware_activity(
        >>>             name="MyMiddleware",
        >>>             status="active",
        >>>             message="Processing input..."
        >>>         )
    """
    callback = _state_update_callback.get(None)
    if callback:
        activity = {
            "name": name,
            "status": status,
            "message": message,
            "details": details or {},
        }
        try:
            callback(activity)
        except Exception:
            # Silently fail if callback doesn't work
            pass
