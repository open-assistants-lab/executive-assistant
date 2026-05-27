"""memcore — Zero-LLM memory for AI agents.

Dual-backend architecture:
  - ChromaBackend: Pure ChromaDB (baseline, 95%+ LongMemEval target)
  - HybridBackend: HybridDB (SQLite+FTS5+ChromaDB, >95% target)

Usage:
    from memcore import MemoryCore
    from memcore.backends.chroma import ChromaBackend

    core = MemoryCore(backend=ChromaBackend(path="./memory"))
    results = core.search("How many model kits?")
    context = core.wakeup(user_id="alice")
    core.ingest("user", "I built a Spitfire model kit")
"""

from memcore.core import MemoryCore
from memcore.heuristics import SearchHeuristics
from memcore.types import Memory, SearchQuery, SearchResult

__all__ = ["MemoryCore", "Memory", "SearchResult", "SearchQuery", "SearchHeuristics"]
