"""Multi-query expansion for better recall.

Regex expansion is always available. LLM-based expansion is opt-in —
requires a provider passed via MemoryCore(llm_provider=...).
"""

import re
from typing import Any, Protocol

_SEARCH_DEPTH_MULTIPLIER = 5


class LLMProvider(Protocol):
    """Minimal interface for LLM query expansion.

    Any object with a chat(messages) method returning something
    with a .content attribute is valid.
    """

    def chat(self, messages: list[dict[str, Any]]) -> Any: ...


def expand_queries(
    query: str,
    llm_provider: LLMProvider | None = None,
) -> list[str]:
    """Generate search query variants for better recall.

    Uses LLM rephrasing when a provider is configured, falls back to regex.
    """
    if llm_provider is not None:
        try:
            variants = _llm_expand_queries(query, llm_provider)
            if variants:
                seen = {query.lower()}
                result = [query]
                for v in variants:
                    if v.lower() not in seen and len(result) < 4:
                        seen.add(v.lower())
                        result.append(v)
                return result
        except Exception:
            pass
    return _regex_expand_queries(query)


def _regex_expand_queries(query: str) -> list[str]:
    """Fallback regex-based query expansion."""
    queries = [query]

    words = query.lower().split()
    if len(words) > 4:
        queries.append(" ".join(words[:4]))

    for kw in ["how many", "how much", "how long", "how often", "how many days",
                "how many times", "total", "all the", "list of", "every"]:
        if kw in query.lower():
            stripped = query.lower().replace(kw, "").strip()
            queries.append(stripped)
            if re.search(r"\b(?:how many|how much)\b", query.lower()):
                aspects = re.split(r"\s+(?:and|or)\s+", stripped)
                if len(aspects) > 1:
                    for a in aspects:
                        a = a.rstrip("?.").strip()
                        if a and a not in queries and len(a.split()) >= 1:
                            queries.append(a)
                subject = re.search(
                    r"(.+?)\s+(?:have|did|do|has|does|can|should|would|will)\s+(?:i|you|we|they)\s+",
                    stripped,
                )
                if subject and subject.group(1).strip() not in queries:
                    queries.append(subject.group(1).strip())
            break

    for kw in ["current", "latest", "now", "after", "updated", "new", "recently",
                "last", "previous", "before", "changed"]:
        if kw in query.lower():
            core = query.lower().replace(kw, "").strip()
            if core and core != query.lower():
                queries.append(core)
            break

    for kw in ["recommend", "suggest", "should i", "what kind of", "what type of",
                "can you recommend", "can you suggest", "do i like", "do i prefer",
                "what do i", "what's my favorite", "what is my favorite"]:
        if kw in query.lower():
            for sub in ["like", "enjoy", "love", "prefer", "favorite", "interested in"]:
                queries.append(sub)
            break

    date_refs = re.findall(r"\b(?:january|february|march|april|may|june|july|august"
                           r"|september|october|november|december|\d{1,2}(?:st|nd|rd|th)?"
                           r"(?:\s+of)?\s+\d{4})\b", query.lower())
    for d in date_refs:
        queries.append(d)

    return queries


def _llm_expand_queries(query: str, provider: LLMProvider) -> list[str] | None:
    """LLM-based query rephrasing.

    The provider must support chat(messages: list[dict]) -> object with .content.
    Returns None on failure (falls back to regex).
    """
    prompt = (
        "Rephrase this search query exactly 2 different ways to improve retrieval recall. "
        "Keep the original meaning. Return ONLY a JSON array of 2 strings.\n\n"
        f"Query: {query}\n\n"
        'Format: ["rephrase 1", "rephrase 2"]'
    )
    try:
        import asyncio
        try:
            asyncio.get_running_loop()
            return None
        except RuntimeError:
            pass

        messages = [{"role": "user", "content": prompt}]
        result = asyncio.run(provider.chat(messages))
        text = str(result.content if hasattr(result, "content") else result).strip()
        if text.startswith("["):
            variants = __import__("json").loads(text)
            if isinstance(variants, list) and all(isinstance(v, str) for v in variants):
                return variants
        match = re.search(r"\[(.*?)\]", text, re.DOTALL)
        if match:
            inner = match.group(0)
            variants = __import__("json").loads(inner)
            if isinstance(variants, list) and all(isinstance(v, str) for v in variants):
                return variants
    except Exception:
        pass
    return None
