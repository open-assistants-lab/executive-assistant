"""coremem — Zero-LLM memory for AI agents.

Dual-backend architecture:
  - ChromaBackend: Pure ChromaDB (baseline, 95%+ LongMemEval target)
  - HybridBackend: HybridDB (SQLite+FTS5+ChromaDB, >95% target)

Usage:
    from coremem import MemoryCore
    from coremem.backends.chroma import ChromaBackend

    core = MemoryCore(backend=ChromaBackend(path="./memory"))
    results = core.search("How many model kits?")
    context = core.wakeup(user_id="alice")
    core.ingest("user", "I built a Spitfire model kit")
"""

from coremem.core import MemoryCore
from coremem.heuristics import SearchHeuristics
from coremem.types import Memory, SearchQuery, SearchResult

__all__ = ["MemoryCore", "Memory", "SearchResult", "SearchQuery", "SearchHeuristics"]
