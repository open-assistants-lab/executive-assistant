"""Abstract backend interface."""

from abc import ABC, abstractmethod

from memcore.types import Memory, SearchResult, SearchQuery


class StoreBackend(ABC):
    """Abstract memory storage and retrieval backend.

    Implementations:
      - ChromaBackend: pure ChromaDB
      - HybridBackend: HybridDB (SQLite + FTS5 + ChromaDB)
    """

    @abstractmethod
    def ingest(self, memory: Memory) -> str:
        """Store a memory. Returns the storage ID."""
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
    def get_recent(self, limit: int = 10) -> list[Memory]:
        """Return most recently stored memories."""
        ...

    @abstractmethod
    def count(self) -> int:
        """Return total number of stored memories."""
        ...

    @abstractmethod
    def clear(self) -> None:
        """Delete all memories."""
        ...
