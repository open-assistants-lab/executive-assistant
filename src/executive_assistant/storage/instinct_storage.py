"""Instinct storage compatibility module.

Instincts are now persisted in SQLite only.
This module keeps the legacy import path stable for existing callers.
"""

from executive_assistant.storage.instinct_storage_sqlite import (
    InstinctStorageSQLite,
    get_instinct_storage_sqlite,
)

# Backward-compatible type alias used across the codebase/tests.
InstinctStorage = InstinctStorageSQLite


def get_instinct_storage() -> InstinctStorageSQLite:
    """Return the singleton SQLite instincts storage."""
    return get_instinct_storage_sqlite()

