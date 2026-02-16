"""Memory system for the Executive Assistant.

Provides persistent memory storage with:
- SQLite + FTS5 for structured storage and full-text search
- ChromaDB for semantic vector search
- 3-layer progressive disclosure workflow

Usage:
    from src.memory import MemoryStore, MemoryCreate, MemoryType

    store = MemoryStore(user_id="user-123", data_path=Path("/data/users/user-123"))

    # Add a memory
    memory = store.add(MemoryCreate(
        title="Prefers async communication",
        type=MemoryType.PREFERENCE,
        narrative="User prefers async communication over real-time meetings",
    ))

    # Search (Layer 1)
    results = store.search(MemorySearchParams(query="communication", limit=10))

    # Timeline (Layer 2)
    timeline = store.timeline(MemoryTimelineParams(anchor_id=results[0].id))

    # Get full details (Layer 3)
    memories = store.get_batch([r.id for r in results[:3]])
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from src.memory.models import (
    Memory,
    MemoryCreate,
    MemorySearchParams,
    MemorySearchResult,
    MemorySource,
    MemoryTimelineEntry,
    MemoryTimelineParams,
    MemoryType,
    MemoryUpdate,
)
from src.memory.store import MemoryStore
from src.memory.tools import (
    memory_search,
    memory_timeline,
    memory_get,
    memory_save,
    set_memory_store,
    get_memory_store,
    MEMORY_WORKFLOW,
)

if TYPE_CHECKING:
    pass

__all__ = [
    "Memory",
    "MemoryCreate",
    "MemorySearchParams",
    "MemorySearchResult",
    "MemorySource",
    "MemoryTimelineEntry",
    "MemoryTimelineParams",
    "MemoryType",
    "MemoryUpdate",
    "MemoryStore",
    "get_memory_store",
    "memory_get",
    "memory_save",
    "memory_search",
    "memory_timeline",
    "set_memory_store",
    "MEMORY_WORKFLOW",
]


_stores: dict[str, MemoryStore] = {}


def get_memory_store_factory(user_id: str, data_path: Path) -> MemoryStore:
    """Get or create a MemoryStore for a user.

    Caches stores per user to avoid recreating connections.
    """
    if user_id not in _stores:
        _stores[user_id] = MemoryStore(user_id=user_id, data_path=data_path)
    return _stores[user_id]
