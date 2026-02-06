"""
Thread-based storage routing.

All data is scoped to thread_id, which is channel + channel identifier (e.g., telegram:123, http:user_abc).
Storage layout:
  data/users/{thread_id}/
    files/
    kb/
    tdb/
    mem/
    reminders/
    vdb/
"""

import threading
from contextvars import ContextVar
from functools import wraps
from pathlib import Path
from typing import Callable, Literal
import inspect

from executive_assistant.config.settings import settings
from executive_assistant.storage.user_allowlist import is_admin

_thread_id: ContextVar[str | None] = ContextVar("_thread_id", default=None)
_channel: ContextVar[str | None] = ContextVar("_channel", default=None)
_chat_type: ContextVar[str | None] = ContextVar("_chat_type", default=None)

# Global fallback for ThreadPoolExecutor scenarios
# Key: main asyncio thread ID (accessible from all worker threads)
# Value: dict of context values
_context_fallback: dict = {}
_context_lock = threading.Lock()
_main_thread_id: int | None = None


def _get_context_key() -> int:
    """Get the main thread ID as the context key."""
    global _main_thread_id
    if _main_thread_id is None:
        # Detect the main thread (where asyncio event loop runs)
        try:
            import asyncio
            asyncio.current_task()  # Will raise RuntimeError if not in async context
            _main_thread_id = threading.get_ident()
        except RuntimeError:
            # Not in async context, use current thread ID
            _main_thread_id = threading.get_ident()
    return _main_thread_id


def set_thread_id(thread_id: str) -> None:
    _thread_id.set(thread_id)
    # Also store in fallback for ThreadPoolExecutor scenarios
    key = _get_context_key()
    with _context_lock:
        if key not in _context_fallback:
            _context_fallback[key] = {}
        _context_fallback[key]['thread_id'] = thread_id


def get_thread_id() -> str | None:
    # First try ContextVar (async context)
    thread_id = _thread_id.get()
    if thread_id:
        return thread_id
    # Fallback to global dict (for thread pool execution)
    key = _get_context_key()
    with _context_lock:
        return _context_fallback.get(key, {}).get('thread_id')


def clear_thread_id() -> None:
    try:
        _thread_id.set(None)
    except Exception:
        pass


def set_channel(channel: str) -> None:
    _channel.set(channel)
    key = _get_context_key()
    with _context_lock:
        if key not in _context_fallback:
            _context_fallback[key] = {}
        _context_fallback[key]['channel'] = channel


def get_channel() -> str | None:
    channel = _channel.get()
    if channel:
        return channel
    key = _get_context_key()
    with _context_lock:
        return _context_fallback.get(key, {}).get('channel')


def set_chat_type(chat_type: str) -> None:
    _chat_type.set(chat_type)
    key = _get_context_key()
    with _context_lock:
        if key not in _context_fallback:
            _context_fallback[key] = {}
        _context_fallback[key]['chat_type'] = chat_type


def get_chat_type() -> str | None:
    chat_type = _chat_type.get()
    if chat_type:
        return chat_type
    key = _get_context_key()
    with _context_lock:
        return _context_fallback.get(key, {}).get('chat_type')


def clear_chat_type() -> None:
    try:
        _chat_type.set(None)
    except Exception:
        pass


def sanitize_thread_id(thread_id: str) -> str:
    return settings._sanitize_id(thread_id)


def get_threads_root() -> Path:
    return settings.USERS_ROOT


def get_thread_path(thread_id: str) -> Path:
    safe_id = sanitize_thread_id(thread_id)
    thread_path = (get_threads_root() / safe_id).resolve()
    thread_path.mkdir(parents=True, exist_ok=True)
    return thread_path


def get_thread_files_path(thread_id: str) -> Path:
    return get_thread_path(thread_id) / "files"


def get_thread_file_path(thread_id: str) -> Path:
    """Backward-compatible alias for get_thread_files_path()."""
    return get_thread_files_path(thread_id)


def get_thread_kb_path(thread_id: str) -> Path:
    return get_thread_path(thread_id) / "kb"


def get_thread_tdb_path(thread_id: str, database: str = "default") -> Path:
    tdb_root = get_thread_path(thread_id) / "tdb"
    tdb_root.mkdir(parents=True, exist_ok=True)
    return tdb_root / f"{database}.sqlite"


def get_thread_mem_path(thread_id: str) -> Path:
    mem_root = get_thread_path(thread_id) / "mem"
    mem_root.mkdir(parents=True, exist_ok=True)
    return mem_root / "mem.db"


def get_thread_reminders_path(thread_id: str) -> Path:
    return get_thread_path(thread_id) / "reminders"


def get_thread_vdb_path(thread_id: str) -> Path:
    return get_thread_path(thread_id) / "vdb"


def require_permission(
    action: Literal["read", "write", "admin"],
    scope: Literal["shared", "context"] = "context",
):
    def decorator(func: Callable) -> Callable:
        def _check():
            thread_id = get_thread_id()
            if scope == "shared" and action != "read":
                if not is_admin(thread_id):
                    raise PermissionError("Admin permission required for shared resources")
            else:
                if not thread_id:
                    raise PermissionError("No thread_id context")

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            _check()
            return await func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            _check()
            return func(*args, **kwargs)

        return async_wrapper if inspect.iscoroutinefunction(func) else sync_wrapper

    return decorator
