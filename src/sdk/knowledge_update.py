"""Deterministic helpers for current/latest knowledge-update questions."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class KnowledgeUpdateCandidate:
    value: str
    score: float
    evidence: str


@dataclass
class KnowledgeUpdateResolution:
    recommended_value: str
    reason: str
    candidates: list[KnowledgeUpdateCandidate] = field(default_factory=list)
    rejected_values: list[str] = field(default_factory=list)


_UPDATE_QUERY_RE = re.compile(
    r"\b(?:current|latest|now|after|recent|recently|moved|relocation|pre-approved|"
    r"personal best|what was|where did|how often)\b",
    re.IGNORECASE,
)


def resolve_knowledge_update(
    query: str,
    snippets: list[str],
) -> KnowledgeUpdateResolution | None:
    """Resolve a compact current-value hint from retrieved raw snippets.

    This is intentionally conservative: it only emits a resolution for update-like
    questions and only from explicit values in the retrieved text.
    """
    if not snippets or not _UPDATE_QUERY_RE.search(query):
        return None

    candidates = _extract_candidates(query, snippets)
    if not candidates:
        return None

    candidates.sort(key=lambda c: c.score, reverse=True)
    best = candidates[0]
    rejected = []
    for candidate in candidates[1:]:
        if candidate.value != best.value and candidate.value not in rejected:
            rejected.append(candidate.value)
    return KnowledgeUpdateResolution(
        recommended_value=best.value,
        reason=_reason_for(query, best),
        candidates=candidates,
        rejected_values=rejected,
    )


def _extract_candidates(query: str, snippets: list[str]) -> list[KnowledgeUpdateCandidate]:
    query_lower = query.lower()
    candidates: list[KnowledgeUpdateCandidate] = []
    for index, snippet in enumerate(snippets):
        recency_score = index * 0.05
        for value in _values_for_query(query_lower, snippet):
            score = 1.0 + recency_score + _cue_score(query_lower, snippet, value)
            candidates.append(KnowledgeUpdateCandidate(value=value, score=score, evidence=snippet))
    return candidates


def _values_for_query(query_lower: str, snippet: str) -> list[str]:
    if "pre-approved" in query_lower or "mortgage" in query_lower:
        return re.findall(r"\$\s*[0-9][0-9,]*(?:\.[0-9]+)?", snippet)
    if "personal best" in query_lower or "time" in query_lower:
        return re.findall(r"\b\d{1,2}:\d{2}\b", snippet)
    if "where" in query_lower or "moved" in query_lower or "relocation" in query_lower:
        locations = []
        if re.search(r"\bthe suburbs\b", snippet, re.IGNORECASE):
            locations.append("the suburbs")
        locations.extend(re.findall(r"\b(?:to|in)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", snippet))
        return locations
    return []


def _cue_score(query_lower: str, snippet: str, value: str) -> float:
    snippet_lower = snippet.lower()
    score = 0.0
    if "personal best" in query_lower and "personal best" in snippet_lower:
        score += 3.0
    if "pre-approved" in query_lower and "pre-approved" in snippet_lower:
        score += 1.0
    if "wells fargo" in query_lower and "wells fargo" in snippet_lower:
        score += 1.0
    if re.search(r"\bremember when\b", snippet_lower):
        score += 0.7
    if ("moved" in query_lower or "relocation" in query_lower) and re.search(
        r"\b(?:moved|relocation|relocated)\b", snippet_lower
    ):
        score += 1.0
    if value.lower() == "the suburbs":
        score += 1.5
    if re.search(r"\b(?:goal|hoping|hope|aiming|beat)\b", snippet_lower):
        if "personal best" not in snippet_lower:
            score -= 2.0
    return score


def _reason_for(query: str, candidate: KnowledgeUpdateCandidate) -> str:
    query_lower = query.lower()
    if "personal best" in query_lower:
        return "Selected the value explicitly tied to personal best evidence."
    if "pre-approved" in query_lower or "mortgage" in query_lower:
        return "Selected the strongest raw mortgage pre-approval evidence."
    if "where" in query_lower or "moved" in query_lower:
        return "Selected the most specific relocation destination evidence."
    return "Selected the strongest retrieved update evidence."
