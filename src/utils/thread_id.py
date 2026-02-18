from __future__ import annotations

import re
from datetime import datetime, timezone
from uuid import uuid4


def _normalize_component(value: str) -> str:
    """Normalize thread ID components to safe ASCII tokens."""
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip())
    normalized = normalized.strip("-").lower()
    return normalized or "default"


def create_thread_id(user_id: str, channel: str, reason: str = "session") -> str:
    """Create a conversation/session-scoped thread ID.

    Format:
        {channel}-{user_id}-{reason}-{timestamp}-{suffix}
    """
    safe_channel = _normalize_component(channel)
    safe_user = _normalize_component(user_id)
    safe_reason = _normalize_component(reason)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    suffix = uuid4().hex[:8]
    return f"{safe_channel}-{safe_user}-{safe_reason}-{timestamp}-{suffix}"
