"""MemoryCore — the main entry point for coremem.

Wraps any StoreBackend with heuristics, wake-up context, and ingestion.
"""

from typing import Any

from coremem.backends.base import StoreBackend
from coremem.heuristics import SearchHeuristics
from coremem.ingest import ingest_batch, ingest_message
from coremem.layers import WakeUpContext
from coremem.query import LLMProvider, expand_queries
from coremem.rerank import get_cross_encoder, rerank
from coremem.types import Memory, SearchQuery, SearchResult

_DEFAULT_SEARCH_DEPTH = 5


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

    For enhanced search with multi-query expansion and cross-encoder
    reranking, pass an optional llm_provider (disabled by default):
        core = MemoryCore(backend=..., llm_provider=my_model)
        results = core.search_enhanced("How many model kits?")
    """

    def __init__(self, backend: StoreBackend, llm_provider: LLMProvider | None = None):
        self._backend = backend
        self._wakeup = WakeUpContext(backend)
        self._heuristics = SearchHeuristics()
        self._llm_provider = llm_provider

    @property
    def backend(self) -> StoreBackend:
        return self._backend

    def warmup(self) -> None:
        """Pre-download models to avoid delay on first search.

        Loads the cross-encoder model (~500MB download on first call).
        Safe to call multiple times — models are cached after load.
        """
        get_cross_encoder()

    def ingest(
        self, role: str, content: str, session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        embedding: list[float] | None = None,
    ) -> str:
        """Store a message verbatim.

        No LLM extraction. No summarization. Just store the raw text.

        Args:
            role: Message role (user, assistant, tool, system).
            content: Raw message text — stored as-is.
            session_id: Optional session/thread identifier.
            metadata: Optional arbitrary key-value pairs for filtering.
            embedding: Optional pre-computed embedding vector. When provided,
                      the backend uses this instead of computing one.
        """
        return ingest_message(
            backend=self._backend, role=role, content=content,
            session_id=session_id, metadata=metadata, embedding=embedding,
        )

    def ingest_many(self, messages: list[dict[str, Any]], session_id: str | None = None) -> list[str]:
        """Store a batch of messages verbatim."""
        return ingest_batch(backend=self._backend, messages=messages, session_id=session_id)

    def search(
        self, query: str, limit: int = 10,
        metadata: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Search memories and apply deterministic heuristics.

        Pipeline:
          1. Backend raw search (embedding ± keyword)
          2. Apply heuristics (keyword overlap, temporal, person name, quoted)
          3. Session-level dedup (if backend supports it)
          4. Return ranked results

        All steps are deterministic — zero LLM calls.
        """
        sq = SearchQuery(text=query, limit=limit * 3, metadata=metadata or {})
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

    def search_enhanced(
        self, query: str, limit: int = 10,
        metadata: dict[str, Any] | None = None,
        depth: int = _DEFAULT_SEARCH_DEPTH,
    ) -> list[SearchResult]:
        """Search with multi-query expansion and cross-encoder reranking.

        Pipeline:
          1. Multi-query expansion (regex + optional LLM)
          2. Run raw search for each query variant
          3. Merge results deduplicated by memory ID
          4. Apply deterministic heuristics
          5. Cross-encoder reranking for better relevance

        LLM expansion is disabled by default — enable by passing an
        llm_provider to MemoryCore().

        Args:
            query: The search query.
            limit: Max results to return.
            metadata: Optional metadata key=value equality filters.
            depth: Candidate multiplier for search depth (default 5).
                   Higher depth means more candidates for the reranker.

        Returns:
            Reranked SearchResult list.
        """
        queries = expand_queries(query, llm_provider=self._llm_provider)

        effective_limit = limit * depth
        all_results: list[SearchResult] = []
        seen_ids: set[int] = set()

        for q in queries:
            sq = SearchQuery(text=q, limit=effective_limit, metadata=metadata or {})
            results = self._backend.search(sq)
            for r in results:
                rid = id(r)
                if rid not in seen_ids:
                    seen_ids.add(rid)
                    all_results.append(r)

        for r in all_results:
            r.score = SearchHeuristics.apply_all(
                query=query,
                content=r.memory.content,
                score=r.score,
                ts=r.memory.ts.isoformat() if r.memory.ts else None,
            )

        all_results.sort(key=lambda r: r.score, reverse=True)

        all_results = rerank(query, all_results)

        return all_results[:limit]

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

    def export(
        self, metadata: dict[str, Any] | None = None,
        limit: int = 1000, offset: int = 0,
    ) -> list[Memory]:
        """Paginated export. Returns one page of memories matching metadata filters."""
        return self._backend.list(metadata=metadata, limit=limit, offset=offset)

    def export_all(self, metadata: dict[str, Any] | None = None) -> list[Memory]:
        """Export all matching memories. Internally loops with pagination."""
        all_memories: list[Memory] = []
        offset = 0
        page_size = 1000
        while True:
            page = self._backend.list(metadata=metadata, limit=page_size, offset=offset)
            if not page:
                break
            all_memories.extend(page)
            offset += len(page)
        return all_memories

    def import_batch(self, memories: list[Memory]) -> list[str]:
        """Batch import. Returns storage IDs. Delegates to backend.ingest_batch()."""
        return self._backend.ingest_batch(memories)

    def count(self) -> int:
        """Return total number of stored memories."""
        return self._backend.count()

    def delete(self, metadata: dict[str, Any] | None = None) -> int:
        """Delete memories matching metadata filters. Returns count deleted."""
        return self._backend.delete(metadata=metadata)

    def clear(self) -> None:
        """Delete all memories."""
        self._backend.clear()
