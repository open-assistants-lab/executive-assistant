"""Deterministic retrieval planner for user memory questions."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

MemoryQueryIntent = Literal[
    "current_fact",
    "historical_fact",
    "timeline",
    "summary",
    "search_evidence",
    "unknown",
]


@dataclass(frozen=True)
class MemoryQueryPlan:
    intent: MemoryQueryIntent
    needs_current_facts: bool = False
    needs_fact_history: bool = False
    needs_messages: bool = False
    prefer_current: bool = True
    max_facts: int = 6
    max_history: int = 0
    max_messages: int = 0


SELF_REFERENCE_PATTERNS = [
    r"\bwhat(?:'s| is| was| are| were) my\b",
    r"\bwhere (?:do|did|am|was) i\b",
    r"\bwho (?:is|was|are|were) my\b",
    r"\bwhen (?:is|was|did) my\b",
    r"\bhow (?:do|did|am|was|many|much) i\b",
    r"\bdo i\b",
    r"\bam i\b",
    r"\bdid i\b",
    r"\bmy .*\?",
    r"\bremember\b",
    r"\bwhat (?:have|did) we (?:discuss|talk)\b",
    r"\bsearch (?:my|for|our)\b",
    r"\blook up\b",
    r"\bfind (?:messages|conversations|anything)\b",
    r"\bsummarize .*\b(?:me|my|we|our)\b",
]

EXPLICIT_SEARCH_PATTERNS = [
    r"\bsearch\b",
    r"\bfind\b",
    r"\blook up\b",
    r"\bwhat (?:have|did) we (?:discuss|talk)\b",
    r"\bconversation(?:s)? about\b",
    r"\bmessages about\b",
]

SUMMARY_PATTERNS = [
    r"\bsummarize\b",
    r"\bsummary\b",
    r"\bprofile\b",
    r"\beverything you know\b",
    r"\ball (?:my|the) (?:current )?(?:key )?facts\b",
    r"\bwhat should you remember\b",
]

TIMELINE_PATTERNS = [
    r"\btimeline\b",
    r"\bhistory\b",
    r"\bover time\b",
    r"\bin order\b",
    r"\bthroughout\b",
    r"\bfrom the beginning\b",
    r"\bsince the start\b",
    r"\ball .* changes\b",
    r"\bcurrent and past\b",
    r"\bpast and current\b",
]

HISTORICAL_PATTERNS = [
    r"\bbefore\b",
    r"\bprevious\b",
    r"\bpreviously\b",
    r"\bold\b",
    r"\boriginal\b",
    r"\boriginally\b",
    r"\bused to\b",
    r"\bchanged from\b",
    r"\breplaced\b",
    r"\bno longer\b",
]

CURRENT_PATTERNS = [
    r"\bcurrent\b",
    r"\bcurrently\b",
    r"\bnow\b",
    r"\blatest\b",
    r"\bnew\b",
    r"\btoday\b",
]


def _matches_any(query: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, query) for pattern in patterns)


def is_memory_query(query: str) -> bool:
    query_lower = query.lower().strip()
    if not query_lower:
        return False
    has_self_reference = _matches_any(query_lower, SELF_REFERENCE_PATTERNS)
    has_memory_verbs = _matches_any(
        query_lower, SUMMARY_PATTERNS + TIMELINE_PATTERNS + EXPLICIT_SEARCH_PATTERNS
    )
    has_user_subject = bool(
        re.search(
            r"\b(?:i|me|my|mine|we|our|us|family|pets?|wife|husband|career|job|work)\b",
            query_lower,
        )
    )
    if "?" not in query_lower and not (has_memory_verbs and has_user_subject):
        return False
    return has_self_reference or (has_memory_verbs and has_user_subject)


def plan_memory_query(query: str) -> MemoryQueryPlan:
    """Plan local memory retrieval without an LLM call."""
    query_lower = query.lower().strip()
    if not is_memory_query(query_lower):
        return MemoryQueryPlan(intent="unknown")

    explicit_search = _matches_any(query_lower, EXPLICIT_SEARCH_PATTERNS)
    wants_summary = _matches_any(query_lower, SUMMARY_PATTERNS)
    wants_timeline = _matches_any(query_lower, TIMELINE_PATTERNS)
    wants_historical = _matches_any(query_lower, HISTORICAL_PATTERNS)
    wants_current = _matches_any(query_lower, CURRENT_PATTERNS)

    if explicit_search:
        return MemoryQueryPlan(
            intent="search_evidence",
            needs_current_facts=True,
            needs_fact_history=wants_timeline or wants_historical,
            needs_messages=True,
            prefer_current=not wants_historical,
            max_facts=6,
            max_history=10 if (wants_timeline or wants_historical) else 0,
            max_messages=8,
        )

    if wants_timeline:
        return MemoryQueryPlan(
            intent="timeline",
            needs_current_facts=True,
            needs_fact_history=True,
            needs_messages=True,
            prefer_current=False,
            max_facts=6,
            max_history=12,
            max_messages=6,
        )

    if wants_summary:
        return MemoryQueryPlan(
            intent="summary",
            needs_current_facts=True,
            needs_fact_history=False,
            needs_messages=True,
            prefer_current=True,
            max_facts=10,
            max_history=0,
            max_messages=6,
        )

    if wants_historical and not wants_current:
        return MemoryQueryPlan(
            intent="historical_fact",
            needs_current_facts=True,
            needs_fact_history=True,
            needs_messages=False,
            prefer_current=False,
            max_facts=4,
            max_history=10,
            max_messages=0,
        )

    return MemoryQueryPlan(
        intent="current_fact",
        needs_current_facts=True,
        needs_fact_history=False,
        needs_messages=True,
        prefer_current=True,
        max_facts=6,
        max_history=0,
        max_messages=4,
    )
