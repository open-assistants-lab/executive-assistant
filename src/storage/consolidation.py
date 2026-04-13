"""Background memory consolidation.

Consolidation runs after N messages to:
1. Find memories with similar triggers/domains
2. Detect contradictions via LLM analysis
3. Mark old memories as superseded, link to new ones
4. Merge similar memories into combined ones
5. Generate insights from grouped memories
6. Consolidate insights themselves (find overlapping/stale insights)
"""

import json
from typing import Any

from src.app_logging import get_logger
from src.storage.memory import Memory, get_memory_store

logger = get_logger()


async def run_consolidation(user_id: str) -> dict[str, Any]:
    """Run memory consolidation for a user.

    Returns:
        Summary of consolidation results
    """
    logger.info("memory.consolidation.started", {"user_id": user_id}, user_id=user_id)

    store = get_memory_store(user_id)

    memories = store.list_memories(limit=200)

    if len(memories) < 5:
        logger.debug(
            "memory.consolidation.skipped",
            {"reason": "too_few_memories", "count": len(memories)},
            user_id=user_id,
        )
        return {"status": "skipped", "reason": "too_few_memories", "count": len(memories)}

    by_domain: dict[str, list[Memory]] = {}
    for mem in memories:
        if mem.domain not in by_domain:
            by_domain[mem.domain] = []
        by_domain[mem.domain].append(mem)

    contradictions_found = 0
    merges_found = 0
    insights_generated = 0

    for domain, domain_memories in by_domain.items():
        if len(domain_memories) < 2:
            continue

        result = await _consolidate_domain(store, domain, domain_memories, user_id=user_id)
        contradictions_found += result.get("contradictions", 0)
        merges_found += result.get("merges", 0)
        insights_generated += result.get("insights", 0)

    insights = store.list_insights(limit=50, include_superseded=False)
    if len(insights) >= 2:
        insight_result = await _consolidate_insights(store, insights)
        insights_generated += insight_result.get("insights_merged", 0)

    logger.info(
        "memory.consolidation.completed",
        {
            "total_memories": len(memories),
            "domains_processed": len(by_domain),
            "contradictions_found": contradictions_found,
            "merges_found": merges_found,
            "insights_generated": insights_generated,
        },
        user_id=user_id,
    )

    return {
        "status": "completed",
        "total_memories": len(memories),
        "domains_processed": len(by_domain),
        "contradictions_found": contradictions_found,
        "merges_found": merges_found,
        "insights_generated": insights_generated,
    }


async def _consolidate_domain(
    store: Any,
    domain: str,
    memories: list[Memory],
    user_id: str = "default",
) -> dict[str, Any]:
    """Consolidate memories within a single domain using LLM."""
    try:
        from langchain_core.messages import HumanMessage

        from src.agents.manager import get_model
    except ImportError:
        return {"contradictions": 0, "merges": 0, "insights": 0}

    model = get_model()
    if model is None:
        return {"contradictions": 0, "merges": 0, "insights": 0}

    memory_summary = "\n".join(
        [
            f"- [{m.id[:8]}] {m.trigger}: {m.action} (conf: {m.confidence:.1f}, obs: {m.observations}, type: {m.memory_type})"
            for m in memories
        ]
    )

    prompt = f"""Analyze these memories about "{domain}" and find:

1. CONTRADICTIONS: If any memories contradict each other (e.g., "uses Google Workspace" vs "uses Microsoft 365")
2. MERGE CANDIDATES: If multiple memories could be combined into one
3. INSIGHTS: If there's a pattern or preference to synthesize

Memories:
{memory_summary}

Respond in JSON format:
{{
    "contradictions": [
        {{"older_id": "...", "newer_id": "...", "keep_newer": true/false}}
    ],
    "merge_candidates": [
        {{"ids": ["...", "..."], "merged_trigger": "when ...", "merged_action": "...", "merged_type": "preference|fact|workflow|correction", "structured_data": {{}}}}
    ],
    "insights": ["insight1", "insight2"]
}}

If no contradictions or merge candidates, return empty arrays. Use the short IDs (first 8 chars) for cross-referencing."""

    try:
        response = model.invoke([HumanMessage(content=prompt)])
        content = response.content if hasattr(response, "content") else str(response)

        content_str: str = str(content)
        result = _extract_json(content_str)

        if not result:
            return {"contradictions": 0, "merges": 0, "insights": 0}

        contradictions = 0
        merges = 0
        insights = 0

        # Build ID lookup (short ID -> full ID)
        id_map = {m.id[:8]: m.id for m in memories}

        for contr in result.get("contradictions", []):
            older_id_short = contr.get("older_id", "")
            newer_id_short = contr.get("newer_id", "")
            keep_newer = contr.get("keep_newer", True)

            older_id = id_map.get(older_id_short, older_id_short)
            newer_id = id_map.get(newer_id_short, newer_id_short)

            older_mem = store.get_memory(older_id)
            newer_mem = store.get_memory(newer_id)

            if older_mem and newer_mem:
                if keep_newer:
                    store.supersede_memory(older_id, newer_id)
                else:
                    store.supersede_memory(newer_id, older_id)

                store.add_connection(newer_id, older_id, relationship="contradicts")
                contradictions += 1

                logger.info(
                    "memory.contradiction.resolved",
                    {"domain": domain, "older": older_id, "newer": newer_id},
                    user_id=user_id,
                )

        # Process merge candidates (was previously silently ignored)
        for merge in result.get("merge_candidates", []):
            ids_short = merge.get("ids", [])
            merged_trigger = merge.get("merged_trigger", "")
            merged_action = merge.get("merged_action", "")
            merged_type = merge.get("merged_type", "preference")
            merged_data = merge.get("structured_data", {})

            if not merged_trigger or not merged_action or len(ids_short) < 2:
                continue

            full_ids = [id_map.get(sid, sid) for sid in ids_short]
            source_memories = [store.get_memory(fid) for fid in full_ids]
            source_memories = [m for m in source_memories if m is not None]

            if len(source_memories) < 2:
                continue

            avg_confidence = sum(m.confidence for m in source_memories) / len(source_memories)
            connections = []
            for m in source_memories:
                connections.append(
                    {"target_id": m.id, "relationship": "merged_from", "strength": m.confidence}
                )

            new_mem = store.add_memory(
                trigger=merged_trigger,
                action=merged_action,
                confidence=min(avg_confidence + 0.1, 1.0),
                domain=domain,
                source="learned",
                memory_type=merged_type,
                structured_data=merged_data if merged_data else None,
                connections=connections,
            )

            for m in source_memories:
                store.supersede_memory(m.id, new_mem.id)

            merges += 1
            logger.info(
                "memory.merged",
                {"domain": domain, "merged_ids": full_ids, "new_id": new_mem.id},
                user_id=user_id,
            )

        # Generate insights
        for insight in result.get("insights", []):
            if insight:
                store.add_insight(
                    summary=insight,
                    linked_memories=[m.id for m in memories[:5]],
                    confidence=0.6,
                )
                insights += 1

        return {"contradictions": contradictions, "merges": merges, "insights": insights}

    except Exception as e:
        logger.warning(
            "memory.consolidation.error",
            {"domain": domain, "error": str(e)},
            user_id=user_id,
        )
        return {"contradictions": 0, "merges": 0, "insights": 0}


async def _consolidate_insights(
    store: Any,
    insights: list[Any],
) -> dict[str, Any]:
    """Consolidate overlapping or stale insights."""
    if len(insights) < 2:
        return {"insights_merged": 0}

    merged = 0
    seen_summaries: set[str] = set()

    for i, insight in enumerate(insights):
        summary_words = set(insight.summary.lower().split())
        key = " ".join(sorted(summary_words)[:5])

        if key in seen_summaries:
            continue
        seen_summaries.add(key)

        for j in range(i + 1, len(insights)):
            other = insights[j]
            other_words = set(other.summary.lower().split())
            overlap = len(summary_words & other_words) / max(
                len(summary_words), len(other_words), 1
            )

            if overlap > 0.6:
                combined_linked = list(set(insight.linked_memories + other.linked_memories))
                store.add_insight(
                    summary=insight.summary,
                    linked_memories=combined_linked[:10],
                    confidence=max(insight.confidence, other.confidence),
                    domain=insight.domain,
                )
                merged += 1
                break

    return {"insights_merged": merged}


def _find_memory_by_action(memories: list[Memory], action: str) -> Memory | None:
    """Find memory by action text (word-boundary aware match)."""
    action_lower = action.lower().strip()
    action_words = set(action_lower.split())
    for mem in memories:
        mem_words = set(mem.action.lower().split())
        # Require at least 60% word overlap to avoid false matches
        # (e.g., "uses Google" should not match "refuses Google to...")
        if not action_words:
            continue
        overlap = len(action_words & mem_words)
        if overlap / len(action_words) >= 0.6:
            return mem
    return None


def _extract_json(content: str) -> dict[str, Any] | None:
    """Extract JSON from LLM response."""
    if not isinstance(content, str):
        content = str(content)

    try:
        result: dict[str, Any] | None = json.loads(content)
        return result
    except json.JSONDecodeError:
        pass

    import re

    # Find all top-level {...} blocks and try parsing each
    # Start from each '{' and match balanced braces to avoid greedy over-capture
    for match in re.finditer(r"\{", content):
        start = match.start()
        depth = 0
        for i in range(start, len(content)):
            if content[i] == "{":
                depth += 1
            elif content[i] == "}":
                depth -= 1
                if depth == 0:
                    candidate = content[start : i + 1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        break

    return None


def trigger_consolidation(user_id: str) -> dict[str, Any]:
    """Manually trigger consolidation for a user (sync wrapper).

    Handles running from daemon threads or inside a running event loop
    by spawning a separate thread when needed.
    """
    import asyncio
    import concurrent.futures

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Running inside an event loop (HTTP/Telegram server).
        # Can't call asyncio.run() here — use a thread.
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, run_consolidation(user_id))
            try:
                return future.result(timeout=60)
            except Exception as e:
                logger.warning(
                    "memory.consolidation.thread_error",
                    {"user_id": user_id, "error": str(e)},
                    user_id=user_id,
                )
                return {"status": "error", "error": str(e)}
    else:
        return asyncio.run(run_consolidation(user_id))


_message_counts: dict[str, int] = {}


def on_conversation_end(user_id: str, threshold: int) -> None:
    """Call after each message to potentially trigger consolidation every N messages."""
    global _message_counts

    count = _message_counts.get(user_id, 0) + 1
    _message_counts[user_id] = count

    if count >= threshold and count % threshold == 0:
        logger.info(
            "memory.consolidation.triggered",
            {"user_id": user_id, "message_count": count},
            user_id=user_id,
        )
        trigger_consolidation(user_id)


__all__ = [
    "run_consolidation",
    "trigger_consolidation",
    "on_conversation_end",
]
