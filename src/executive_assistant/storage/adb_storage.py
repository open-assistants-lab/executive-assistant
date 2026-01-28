"""DuckDB storage for adb queries (context-scoped)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

import duckdb

from executive_assistant.config import settings
from executive_assistant.storage.thread_storage import get_thread_id
from executive_assistant.storage.user_registry import register_adb_path_best_effort


Scope = Literal["context"]


def _get_adb_path(scope: Scope = "context") -> Path:
    """Resolve the DuckDB adb DB path for the current context.

    Priority (context scope):
    1) thread_id
    """
    if scope != "context":
        raise ValueError("ADB DB only supports scope='context' for now")

    thread_id = get_thread_id()
    if not thread_id:
        raise ValueError("No thread_id context available")

    path = settings.get_thread_root(thread_id) / "adb"
    path.mkdir(parents=True, exist_ok=True)
    return path / "duckdb.db"


@lru_cache(maxsize=128)
def _get_duckdb_connection(db_path: Path) -> duckdb.DuckDBPyConnection:
    """Return a cached DuckDB connection for the given path."""
    return duckdb.connect(str(db_path))


def get_adb(scope: Scope = "context") -> duckdb.DuckDBPyConnection:
    """Get a DuckDB connection for adb in the current context."""
    db_path = _get_adb_path(scope)
    register_adb_path_best_effort(get_thread_id(), "unknown", str(db_path))
    return _get_duckdb_connection(db_path)
