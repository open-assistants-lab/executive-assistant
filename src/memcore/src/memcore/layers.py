"""L0-L3 wake-up context stack.

Inspired by MemPalace's four-layer memory stack and validated against
the human memory multi-store model (Mujawar et al., 2021).

L0: Identity    — user profile text (~100 tokens, always loaded)
L1: Essential   — top-ranked recent memories (~500 chars, always loaded)
L2: On-Demand   — session-specific context (~200-500 chars, on detect)
L3: Deep Search — full hybrid/semantic search (per explicit query)
"""

from memcore.types import Memory, SearchResult
from memcore.backends.base import StoreBackend
from memcore.heuristics import SearchHeuristics


class WakeUpContext:
    """Build the L0-L3 context stack from a memory backend.

    Usage:
        ctx = WakeUpContext(backend)
        l0_l1 = ctx.essential(user_id="alice")     # ~170 tokens, always
        l2 = ctx.session(session_id="sess_5")       # on session detect
        l3 = ctx.deep_search("model kits", limit=5) # explicit tool call
    """

    def __init__(self, backend: StoreBackend):
        self._backend = backend

    def essential(self, user_id: str = "default") -> str:
        """Build L0 + L1 context (~170 tokens)."""
        parts = []

        parts.append(f"[L0: Identity] User: {user_id}")

        recent = self._backend.get_recent(limit=10)
        if recent:
            snippets = []
            for m in recent[:3]:
                content = m.content[:200]
                if len(m.content) > 200:
                    content += "..."
                snippets.append(f"  - [{m.role}] {content}")
            parts.append("[L1: Essential] Recent context:\n" + "\n".join(snippets))

        return "\n".join(parts)

    def session(self, session_id: str) -> str | None:
        """Build L2 context for a specific session."""
        recent = self._backend.get_recent(limit=20)
        session_memories = [
            m for m in recent
            if m.session_id == session_id
        ]
        if not session_memories:
            return None

        lines = [f"[L2: On-Demand] Session {session_id}:"]
        for m in session_memories[:5]:
            content = m.content[:200]
            if len(m.content) > 200:
                content += "..."
            lines.append(f"  - [{m.role}] {content}")
        return "\n".join(lines)

    def deep_search(self, query: str, limit: int = 10) -> str | None:
        """Build L3 context from a full search query."""
        from memcore.types import SearchQuery

        results = self._backend.search(SearchQuery(text=query, limit=limit))
        if not results:
            return None

        is_counting = SearchHeuristics.is_counting_question(query)

        lines = [f"[L3: Deep Search] Results for '{query}':"]
        for r in results:
            content = r.memory.content
            if is_counting and len(content) > SearchHeuristics.COUNTING_QUESTION_SNIPPET_LENGTH:
                content = content[:SearchHeuristics.COUNTING_QUESTION_SNIPPET_LENGTH] + "..."
            elif len(content) > 500:
                content = content[:500] + "..."

            lines.append(
                f"  {r.memory.id[:12]} [{r.memory.role}] "
                f"(score={r.score:.2f}): {content}"
            )

        return "\n".join(lines)
