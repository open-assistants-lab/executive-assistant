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
    "preference_profile",
    "search_evidence",
    "aggregation",
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

PREFERENCE_PATTERNS = [
    r"\brecommend\b",
    r"\bsuggest\b",
    r"\bshould i\b",
    r"\bwhat (?:kind|type|sort) of\b",
    r"\bcan you recommend\b",
    r"\bcan you suggest\b",
    r"\bdo i like\b",
    r"\bdo i prefer\b",
    r"\bwhat do i\b",
    r"\bwhat.s my favorite\b",
    r"\bwhat is my favorite\b",
    r"\bwhat should i\b",
    r"\badvice\b",
    r"\btips?\b",
    r"\bwhat would i\b",
]

AGGREGATION_PATTERNS = [
    r"\bhow many\b",
    r"\bhow much\b",
    r"\bhow long\b",
    r"\bhow often\b",
    r"\bhow many days\b",
    r"\bhow many times\b",
    r"\bhow many weeks\b",
    r"\bhow many hours\b",
    r"\bhow many different\b",
    r"\bhow many types\b",
    r"\btotal\b",
    r"\baltogether\b",
    r"\bcombined\b",
    r"\ball (?:the|my|of)\b",
    r"\bcount\b",
    r"\blist all\b",
    r"\bevery .* (?:i|we|you)\b",
    r"\bwhat (?:is|was|are|were) the total\b",
    r"\bover the past\b",
    r"\bin total\b",
    r"\boverall\b",
    r"\bacross all\b",
    r"\bhow many .* (?:have|did|do) (?:i|we|you)\b",
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
    return (
        has_self_reference
        or (has_memory_verbs and has_user_subject)
        or ("?" in query_lower and has_user_subject)
    )


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
    wants_preference = _matches_any(query_lower, PREFERENCE_PATTERNS)
    wants_aggregation = _matches_any(query_lower, AGGREGATION_PATTERNS)

    if wants_preference:
        return MemoryQueryPlan(
            intent="preference_profile",
            needs_current_facts=True,
            needs_fact_history=True,
            needs_messages=True,
            prefer_current=True,
            max_facts=10,
            max_history=5,
            max_messages=6,
        )

    if wants_aggregation:
        return MemoryQueryPlan(
            intent="aggregation",
            needs_current_facts=False,
            needs_fact_history=False,
            needs_messages=True,
            prefer_current=False,
            max_facts=0,
            max_history=0,
            max_messages=20,
        )

    if explicit_search:
        return MemoryQueryPlan(
            intent="search_evidence",
            needs_current_facts=True,
            needs_fact_history=True,
            needs_messages=True,
            prefer_current=not wants_historical,
            max_facts=6,
            max_history=10 if (wants_timeline or wants_historical) else 4,
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
            needs_fact_history=True,
            needs_messages=True,
            prefer_current=True,
            max_facts=10,
            max_history=3,
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
        needs_fact_history=True,
        needs_messages=True,
        prefer_current=True,
        max_facts=6,
        max_history=3,
        max_messages=4,
    )
