"""Abstract backend interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from coremem.types import Memory, SearchQuery, SearchResult


class StoreBackend(ABC):
    """Abstract memory storage and retrieval backend.

    Implementations:
      - ChromaBackend: pure ChromaDB
      - HybridBackend: HybridDB (SQLite + FTS5 + ChromaDB)
    """

    @abstractmethod
    def ingest(self, memory: Memory, embedding: list[float] | None = None) -> str:
        """Store a memory. Returns the storage ID.
        
        Args:
            memory: The memory to store.
            embedding: Optional pre-computed embedding vector. When provided,
                      the backend uses this instead of computing one.
        """
        ...

    @abstractmethod
    def ingest_batch(self, memories: list[Memory]) -> list[str]:
        """Store multiple memories in one batch. Returns storage IDs."""
        ...

    @abstractmethod
    def search(self, query: SearchQuery) -> list[SearchResult]:
        """Search for memories by query text."""
        ...

    @abstractmethod
    def list(
        self,
        role: str | None = None,
        session_id: str | None = None,
        user_id: str | None = None,
        agent_id: str | None = None,
        ts_after: str | None = None,
        ts_before: str | None = None,
        metadata: dict | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Memory]:
        """List memories with optional column and metadata filters. Backbone of export()."""
        ...

    @abstractmethod
    def get_recent(self, limit: int = 10) -> list[Memory]:
        """Return most recently stored memories."""
        ...

    @abstractmethod
    def count(self) -> int:
        """Return total number of stored memories."""
        ...

    @abstractmethod
    def delete(
        self,
        role: str | None = None,
        session_id: str | None = None,
        user_id: str | None = None,
        agent_id: str | None = None,
        ts_after: str | None = None,
        ts_before: str | None = None,
        metadata: dict | None = None,
    ) -> int:
        """Delete memories matching filters. Returns count deleted."""
        ...

    @abstractmethod
    def clear(self) -> None:
        """Delete all memories."""
        ...
