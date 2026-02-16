"""Middleware activity tracker.

Tracks middleware execution and outcomes for visibility.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MiddlewareStatus(str, Enum):
    """Middleware execution status."""

    ACTIVE = "active"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class MiddlewareActivity:
    """Activity record for a middleware execution."""

    name: str
    status: MiddlewareStatus
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0

    def __str__(self) -> str:
        """Format activity for display."""
        if self.status == MiddlewareStatus.ACTIVE:
            emoji = "⚙️"
            status_text = "running"
        elif self.status == MiddlewareStatus.COMPLETED:
            emoji = "✅"
            status_text = "done"
        elif self.status == MiddlewareStatus.SKIPPED:
            emoji = "⏭️"
            status_text = "skipped"
        else:  # FAILED
            emoji = "❌"
            status_text = "failed"

        result = f"{emoji} {self.name} ({status_text}"
        if self.message:
            result += f": {self.message}"
        result += ")"

        return result


class MiddlewareTracker:
    """Track middleware activity during agent execution."""

    def __init__(self) -> None:
        self.activities: list[MiddlewareActivity] = []

    def add_activity(
        self,
        name: str,
        status: MiddlewareStatus,
        message: str = "",
        details: dict[str, Any] | None = None,
    ) -> None:
        """Add a middleware activity record.

        Args:
            name: Middleware name
            status: Activity status
            message: Optional status message
            details: Optional additional details
        """
        import time

        activity = MiddlewareActivity(
            name=name,
            status=status,
            message=message,
            details=details or {},
            timestamp=time.time(),
        )

        # Update existing activity if same middleware and active
        for i, existing in enumerate(self.activities):
            if existing.name == name and existing.status == MiddlewareStatus.ACTIVE:
                self.activities[i] = activity
                return

        # Otherwise add new activity
        self.activities.append(activity)

    def get_active_activities(self) -> list[MiddlewareActivity]:
        """Get currently active middleware activities."""
        return [a for a in self.activities if a.status == MiddlewareStatus.ACTIVE]

    def get_completed_activities(self) -> list[MiddlewareActivity]:
        """Get completed middleware activities."""
        return [a for a in self.activities if a.status == MiddlewareStatus.COMPLETED]

    def get_all_activities(self) -> list[MiddlewareActivity]:
        """Get all middleware activities."""
        return self.activities.copy()

    def clear(self) -> None:
        """Clear all activities."""
        self.activities.clear()

    def to_dict_list(self) -> list[dict]:
        """Convert activities to list of dicts for state storage."""
        return [
            {
                "name": a.name,
                "status": a.status.value,
                "message": a.message,
                "details": a.details,
                "timestamp": a.timestamp,
            }
            for a in self.activities
        ]

    @staticmethod
    def from_dict_list(data: list[dict]) -> list[MiddlewareActivity]:
        """Create list of activities from dict list."""
        activities = []
        for item in data:
            activity = MiddlewareActivity(
                name=item["name"],
                status=MiddlewareStatus(item["status"]),
                message=item.get("message", ""),
                details=item.get("details", {}),
                timestamp=item.get("timestamp", 0.0),
            )
            activities.append(activity)
        return activities
