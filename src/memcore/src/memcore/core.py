"""MemoryCore — the main entry point for memcore.

Wraps any StoreBackend with heuristics, wake-up context, and ingestion.
"""

from memcore.backends.base import StoreBackend
from memcore.heuristics import SearchHeuristics
from memcore.ingest import ingest_batch, ingest_message
from memcore.layers import WakeUpContext
from memcore.types import SearchQuery, SearchResult


class MemoryCore:
    """Zero-LLM memory core for AI agents.

    Dual-backend architecture:
      - ChromaBackend: Pure ChromaDB (baseline)
      - HybridBackend: HybridDB SQLite+FTS5+ChromaDB (enhanced)

    Same API regardless of backend.

    Usage:
        core = MemoryCore(backend=ChromaBackend(path="./memory"))
        core.ingest("user", "I built a Spitfire model kit")
        results = core.search("How many model kits?")
        context = core.wake_up(user_id="alice")
    """

    def __init__(self, backend: StoreBackend):
        self._backend = backend
        self._wakeup = WakeUpContext(backend)
        self._heuristics = SearchHeuristics()

    @property
    def backend(self) -> StoreBackend:
        return self._backend

    def ingest(self, role: str, content: str, session_id: str | None = None) -> str:
        """Store a message verbatim.

        No LLM extraction. No summarization. Just store the raw text.
        """
        return ingest_message(backend=self._backend, role=role, content=content, session_id=session_id)

    def ingest_many(self, messages: list[dict], session_id: str | None = None) -> list[str]:
        """Store a batch of messages verbatim."""
        return ingest_batch(backend=self._backend, messages=messages, session_id=session_id)

    def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        """Search memories and apply deterministic heuristics.

        Pipeline:
          1. Backend raw search (embedding ± keyword)
          2. Apply heuristics (keyword overlap, temporal, person name, quoted)
          3. Session-level dedup (if backend supports it)
          4. Return ranked results

        All steps are deterministic — zero LLM calls.
        """
        sq = SearchQuery(text=query, limit=limit * 3)
        results = self._backend.search(sq)

        for r in results:
            r.score = SearchHeuristics.apply_all(
                query=query,
                content=r.memory.content,
                score=r.score,
                ts=r.memory.ts.isoformat() if r.memory.ts else None,
            )

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    def wake_up(self, user_id: str = "default", session_id: str | None = None) -> str:
        """Build the L0+L1 (+ optional L2) wake-up context.

        Returns ~170 tokens of always-on context that the agent can
        inject into its system prompt without waiting for a tool call.
        """
        context = self._wakeup.essential(user_id=user_id)

        if session_id:
            l2 = self._wakeup.session(session_id=session_id)
            if l2:
                context += "\n\n" + l2

        return context

    def deep_search_context(self, query: str, limit: int = 10) -> str | None:
        """Perform an L3 deep search and return formatted context.

        This is the equivalent of calling the memory_search tool.
        Returns None if no results found.
        """
        return self._wakeup.deep_search(query=query, limit=limit)

    def count(self) -> int:
        """Return total number of stored memories."""
        return self._backend.count()

    def clear(self) -> None:
        """Delete all memories."""
        self._backend.clear()
