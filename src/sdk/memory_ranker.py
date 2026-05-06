"""Deterministic memory evidence ranker.

Collects candidates from structured facts, learned memories, and messages,
then scores, deduplicates, and formats them for context injection.

No LLM calls. Designed to improve long-memory retrieval accuracy by:
- Preventing stale facts from beating current ones
- Deduplicating redundant evidence
- Bounding context size to reduce model confusion
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from src.app_logging import get_logger
from src.sdk.memory_planner import MemoryQueryPlan, plan_memory_query

logger = get_logger()

SourceType = Literal["fact", "message", "memory"]


@dataclass
class MemoryCandidate:
    source: SourceType
    text: str
    score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


SCORE_CURRENT_STRUCTURED_FACT = 40
SCORE_VALUE_TOKEN_OVERLAP = 25
SCORE_ATTRIBUTE_DOMAIN_OVERLAP = 20
SCORE_MAX_MESSAGE_SEARCH = 20
SCORE_MAX_RECENCY = 10
SCORE_USER_AUTHORED = 8
SCORE_CORRECTION_MARKER = 8
SCORE_SHORT_EXACT_FACT = 5

PENALTY_SUPERSEDED_CURRENT_QUERY = -50
PENALTY_OLD_MESSAGE_MAX = -25
PENALTY_DUPLICATE = -10
PENALTY_ASSISTANT_WHEN_USER_EXISTS = -10
PENALTY_LONG_TEXT_MAX = -15

CORRECTION_MARKERS = [
    "actually", "changed", "new", "moved", "update", "correct",
    "no longer", "not anymore", "switched", "replaced",
]

RECENCY_KEYWORDS = [
    "current", "latest", "now", "after", "updated", "new",
    "recently", "last", "nowadays", "these days", "today",
]

HISTORY_KEYWORDS = [
    "before", "previous", "previously", "old", "original",
    "originally", "used to", "changed from", "replaced",
    "no longer", "history", "timeline", "over time",
]


def extract_query_features(query: str) -> MemoryQueryPlan:
    return plan_memory_query(query)


def collect_candidates_from_facts(
    facts: list[Any],
    plan: MemoryQueryPlan,
) -> list[MemoryCandidate]:
    candidates: list[MemoryCandidate] = []
    for fact in facts:
        sd = fact.structured_data
        text = f"{sd.get('entity', 'user')}.{sd.get('attribute', fact.trigger)} = {sd.get('value', fact.action)}"
        current = not fact.is_superseded
        metadata: dict[str, Any] = {
            "entity": sd.get("entity", "user"),
            "attribute": sd.get("attribute", fact.trigger),
            "value": str(sd.get("value", fact.action)),
            "current": current,
            "superseded": fact.is_superseded,
            "domain": fact.domain,
            "memory_id": fact.id,
            "confidence": fact.confidence,
            "superseded_by": fact.superseded_by,
            "effective_at": sd.get("effective_at"),
            "updated_at": str(fact.updated_at) if fact.updated_at else None,
        }
        candidates.append(
            MemoryCandidate(source="fact", text=text, metadata=metadata)
        )
    return candidates


def collect_candidates_from_messages(
    search_results: list[Any],
) -> list[MemoryCandidate]:
    candidates: list[MemoryCandidate] = []
    for r in search_results:
        role = getattr(r, "role", "?")
        ts = getattr(r, "ts", None)
        content = getattr(r, "content", "")
        search_score = getattr(r, "score", 0.0)
        text = f"{role} ({str(ts.date()) if ts else '?'}): {content[:200]}"
        metadata: dict[str, Any] = {
            "role": role,
            "ts": str(ts) if ts else None,
            "search_score": search_score,
            "msg_id": getattr(r, "id", None),
        }
        candidates.append(
            MemoryCandidate(source="message", text=text, metadata=metadata)
        )
    return candidates


def collect_candidates_from_memories(
    memories: list[Any],
) -> list[MemoryCandidate]:
    candidates: list[MemoryCandidate] = []
    for m in memories:
        text = f"[{m.domain}] {m.trigger}: {m.action}"
        metadata: dict[str, Any] = {
            "domain": m.domain,
            "trigger": m.trigger,
            "action": m.action,
            "confidence": m.confidence,
            "memory_id": m.id,
            "memory_type": m.memory_type,
        }
        candidates.append(
            MemoryCandidate(source="memory", text=text, metadata=metadata)
        )
    return candidates


def rank_memory_candidates(
    query: str,
    candidates: list[MemoryCandidate],
) -> list[MemoryCandidate]:
    plan = plan_memory_query(query)
    query_lower = query.lower()
    wants_history = plan.needs_fact_history

    is_aggregation = plan.intent == "aggregation"

    for c in candidates:
        c.score = _score_candidate(c, query_lower, plan, wants_history)

    if not is_aggregation:
        _apply_dedup_penalties(candidates)
        _apply_assistant_penalty(candidates)

    candidates.sort(key=lambda c: (-c.score, c.source == "fact", c.source == "message"))
    return candidates


def _score_candidate(
    c: MemoryCandidate,
    query_lower: str,
    plan: MemoryQueryPlan,
    wants_history: bool,
) -> float:
    score = 0.0
    meta = c.metadata
    is_fact = c.source == "fact"
    is_msg = c.source == "message"

    # -- Positive signals --
    if is_fact and meta.get("current") and not meta.get("superseded"):
        score += SCORE_CURRENT_STRUCTURED_FACT

    value = str(meta.get("value", "")).lower()
    text_lower = c.text.lower()
    if _token_overlap(query_lower, value):
        score += SCORE_VALUE_TOKEN_OVERLAP
    elif _token_overlap(query_lower, text_lower):
        score += min(SCORE_VALUE_TOKEN_OVERLAP, 15)

    attr = str(meta.get("attribute", "")).lower()
    domain = str(meta.get("domain", "")).lower()
    if attr and attr in query_lower:
        score += SCORE_ATTRIBUTE_DOMAIN_OVERLAP
    elif domain and domain in query_lower:
        score += min(SCORE_ATTRIBUTE_DOMAIN_OVERLAP, 10)

    if is_msg:
        search_s = meta.get("search_score", 0.0)
        if isinstance(search_s, (int, float)):
            score += min(search_s * 25, SCORE_MAX_MESSAGE_SEARCH)

    if _wants_recent(query_lower):
        recency = _compute_recency(meta)
        score += recency * SCORE_MAX_RECENCY

    if is_msg and meta.get("role") == "user":
        score += SCORE_USER_AUTHORED

    if any(kw in text_lower for kw in CORRECTION_MARKERS):
        score += SCORE_CORRECTION_MARKER

    if plan.intent == "aggregation" and is_msg:
        num_count = len(re.findall(r"\b\d+\b", text_lower))
        if num_count >= 3:
            score += 12
        elif num_count >= 1:
            score += 6

    val_len = len(value) if value else 0
    if is_fact and meta.get("current") and 1 <= val_len <= 20:
        score += SCORE_SHORT_EXACT_FACT

    # -- Negative signals --
    if is_fact and meta.get("superseded") and not wants_history:
        penalty = PENALTY_SUPERSEDED_CURRENT_QUERY
        if _token_overlap(query_lower, value):
            penalty = min(penalty + 15, -10)
        score += penalty

    if is_msg and meta.get("role") == "assistant" and not _wants_recent(query_lower):
        if plan.intent != "aggregation":
            score += PENALTY_OLD_MESSAGE_MAX * 0.4

    if len(c.text) > 400 and plan.intent != "aggregation":
        score += PENALTY_LONG_TEXT_MAX * 0.5

    return score


def _token_overlap(query: str, target: str) -> bool:
    query_tokens = set(re.findall(r"\w{2,}", query))
    target_tokens = set(re.findall(r"\w{2,}", target))
    return len(query_tokens & target_tokens) > 0


def _wants_recent(query_lower: str) -> bool:
    return any(kw in query_lower for kw in RECENCY_KEYWORDS)


def _compute_recency(meta: dict[str, Any]) -> float:
    ts_str = meta.get("ts") or meta.get("updated_at") or meta.get("effective_at")
    if not ts_str:
        return 0.0
    try:
        from datetime import UTC, datetime
        now = datetime.now(UTC)
        if isinstance(ts_str, str):
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        else:
            return 0.0
        hours_ago = (now - ts).total_seconds() / 3600
        if hours_ago <= 1:
            return 1.0
        if hours_ago <= 24:
            return 0.8
        if hours_ago <= 168:
            return 0.5
        if hours_ago <= 720:
            return 0.2
        return 0.0
    except Exception:
        return 0.0


def _apply_dedup_penalties(candidates: list[MemoryCandidate]) -> None:
    seen_values: set[str] = set()
    for c in candidates:
        val = str(c.metadata.get("value", c.text[:60])).lower().strip()
        if not val:
            continue
        if val in seen_values:
            c.score += PENALTY_DUPLICATE
        else:
            seen_values.add(val)


def _apply_assistant_penalty(candidates: list[MemoryCandidate]) -> None:
    has_user_evidence = any(
        c.source == "message" and c.metadata.get("role") == "user"
        for c in candidates
    )
    if not has_user_evidence:
        return
    for c in candidates:
        if c.source == "message" and c.metadata.get("role") == "assistant":
            c.score += PENALTY_ASSISTANT_WHEN_USER_EXISTS


def format_ranked_memory_context(
    query: str,
    ranked: list[MemoryCandidate],
    plan: MemoryQueryPlan | None = None,
    max_chars: int = 2500,
) -> str:
    if not ranked:
        return ""

    if plan is None:
        plan = plan_memory_query(query)

    current_facts = [c for c in ranked if c.source == "fact" and c.metadata.get("current")]
    historical = [c for c in ranked if c.source == "fact" and c.metadata.get("superseded")]
    messages = [c for c in ranked if c.source == "message"]
    memories = [c for c in ranked if c.source == "memory"]

    limits = _injection_limits(plan)
    current_facts = current_facts[: limits["facts"]]
    historical = historical[: limits["history"]]
    messages = messages[: limits["messages"]]
    memories = memories[: limits["memories"]]

    lines: list[str] = ["## Relevant Memory Search Results"]

    if plan.prefer_current:
        lines.append("Use Exact Facts first when they directly answer the user question.")
    else:
        lines.append("Use historical facts for timeline/before questions.")

    lines.append("")

    if current_facts or historical:
        lines.append("### Highest-Ranked Evidence")
        idx = 1
        for c in current_facts:
            lines.append(f"{idx}. [fact/current] {c.text}")
            idx += 1
        for c in historical:
            lines.append(f"{idx}. [fact/superseded] {c.text}")
            idx += 1
        lines.append("")

    if messages:
        lines.append("### Conversation Evidence")
        for c in messages:
            role = c.metadata.get("role", "?")
            ts = c.metadata.get("ts", "?")
            lines.append(f"- [{role}/{ts}] {c.text}")
        lines.append("")

    if memories:
        lines.append("### Learned Memory Matches")
        for c in memories:
            lines.append(f"- {c.text}")
        lines.append("")

    result = "\n".join(lines)
    if plan.intent == "aggregation":
        max_chars = 5000
    if len(result) > max_chars:
        suffix = "\n... [context truncated]"
        result = result[:max(max_chars - len(suffix), 100)] + suffix

    return result


def _injection_limits(plan: MemoryQueryPlan) -> dict[str, int]:
    intent = plan.intent
    if intent == "current_fact":
        return {"facts": 3, "messages": 3, "memories": 1, "history": 0}
    if intent == "aggregation":
        return {"facts": 0, "messages": 15, "memories": 0, "history": 0}
    if intent in ("search_evidence", "historical_fact"):
        return {"facts": 4, "messages": 5, "memories": 2, "history": 4}
    if intent in ("summary", "timeline"):
        return {"facts": 8, "messages": 4, "memories": 4, "history": 4}
    return {"facts": 3, "messages": 3, "memories": 1, "history": 0}


def collect_memory_candidates(
    user_id: str,
    query: str,
    workspace_id: str = "personal",
) -> list[MemoryCandidate]:
    from src.sdk.memory_planner import plan_memory_query
    from src.storage.memory import get_memory_store
    from src.storage.messages import get_message_store

    plan = plan_memory_query(query)
    memory_store = get_memory_store(user_id, workspace_id)
    message_store = get_message_store(user_id, workspace_id)

    candidates: list[MemoryCandidate] = []

    if plan.needs_current_facts:
        facts = memory_store.find_facts_for_query(query, limit=plan.max_facts)
        candidates.extend(collect_candidates_from_facts(facts, plan))

    if plan.needs_fact_history:
        temporal = memory_store.find_fact_history_for_query(query, limit=plan.max_history)
        candidates.extend(collect_candidates_from_facts(temporal, plan))

    if plan.needs_messages:
        from src.sdk.tools_core.memory import _expand_queries
        queries = _expand_queries(query)
        seen_ids: set[int] = set()
        for q in queries:
            results = message_store.search_hybrid(q, limit=plan.max_messages)
            for r in results:
                rid = getattr(r, "id", None)
                if rid is not None and rid not in seen_ids:
                    seen_ids.add(rid)
                    candidates.extend(collect_candidates_from_messages([r]))

    memories = memory_store.search_hybrid(query, limit=6)
    fact_ids = {c.metadata.get("memory_id") for c in candidates if c.source == "fact"}
    filtered = [m for m in memories if m.id not in fact_ids]
    if filtered:
        candidates.extend(collect_candidates_from_memories(filtered))

    return candidates
