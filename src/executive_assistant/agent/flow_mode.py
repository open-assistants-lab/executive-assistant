"""Flow mode tracking for flow-building sessions."""
from __future__ import annotations

from contextvars import ContextVar

_flow_mode_active: ContextVar[bool] = ContextVar("_flow_mode_active", default=False)
_flow_mode_chats: set[str] = set()

def set_flow_mode_active(active: bool) -> None:
    _flow_mode_active.set(active)

def is_flow_mode_active() -> bool:
    return _flow_mode_active.get()

def enable_flow_mode(conversation_id: str) -> None:
    _flow_mode_chats.add(str(conversation_id))

def disable_flow_mode(conversation_id: str) -> None:
    _flow_mode_chats.discard(str(conversation_id))

def is_flow_mode_enabled(conversation_id: str) -> bool:
    return str(conversation_id) in _flow_mode_chats
