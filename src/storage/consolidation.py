"""Background memory consolidation.

Consolidation runs after N messages to:
1. Find memories with similar triggers/domains
2. Detect contradictions via LLM analysis
3. Mark old memories as superseded, link to new ones
4. Generate insights from grouped memories
"""

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

    # Get all non-superseded memories
    memories = store.list_memories(limit=200)

    if len(memories) < 5:
        logger.debug(
            "memory.consolidation.skipped",
            {"reason": "too_few_memories", "count": len(memories)},
            user_id=user_id,
        )
        return {"status": "skipped", "reason": "too_few_memories", "count": len(memories)}

    # Group by domain
    by_domain: dict[str, list[Memory]] = {}
    for mem in memories:
        if mem.domain not in by_domain:
            by_domain[mem.domain] = []
        by_domain[mem.domain].append(mem)

    contradictions_found = 0
    insights_generated = 0

    # Process each domain
    for domain, domain_memories in by_domain.items():
        if len(domain_memories) < 2:
            continue

        result = await _consolidate_domain(store, domain, domain_memories)
        contradictions_found += result.get("contradictions", 0)
        insights_generated += result.get("insights", 0)

    logger.info(
        "memory.consolidation.completed",
        {
            "total_memories": len(memories),
            "domains_processed": len(by_domain),
            "contradictions_found": contradictions_found,
            "insights_generated": insights_generated,
        },
        user_id=user_id,
    )

    return {
        "status": "completed",
        "total_memories": len(memories),
        "domains_processed": len(by_domain),
        "contradictions_found": contradictions_found,
        "insights_generated": insights_generated,
    }


async def _consolidate_domain(
    store: Any,
    domain: str,
    memories: list[Memory],
) -> dict[str, Any]:
    """Consolidate memories within a single domain using LLM.

    Uses LLM to detect contradictions and generate insights.
    """
    # Get LLM model
    try:
        from langchain_core.messages import HumanMessage

        from src.agents.manager import get_model
    except ImportError:
        return {"contradictions": 0, "insights": 0}

    model = get_model()
    if model is None:
        return {"contradictions": 0, "insights": 0}

    # Prepare memory summary for LLM
    memory_summary = "\n".join(
        [
            f"- {m.action} (confidence: {m.confidence}, observations: {m.observations})"
            for m in memories
        ]
    )

    prompt = f"""Analyze these memories about "{domain}" and find:

1. CONTRADICTIONS: If any memories contradict each other (e.g., "uses Google Workspace" vs "uses Microsoft 365")
2. MERGE CANDIDATES: If multiple memories could be combined
3. INSIGHTS: If there's a pattern or preference to synthesize

Memories:
{memory_summary}

Respond in JSON format:
{{
    "contradictions": [
        {{"older_action": "...", "newer_action": "...", "keep_newer": true/false}}
    ],
    "merge_candidates": [
        {{"actions": ["...", "..."], "merged_action": "..."}}
    ],
    "insights": ["insight1", "insight2"]
}}

If no contradictions or merge candidates, return empty arrays."""

    try:
        response = model.invoke([HumanMessage(content=prompt)])
        content = response.content if hasattr(response, "content") else str(response)

        # Try to parse JSON
        content_str: str = str(content)
        result = _extract_json(content_str)

        if not result:
            return {"contradictions": 0, "insights": 0}

        contradictions = 0
        insights = 0

        # Handle contradictions
        for contr in result.get("contradictions", []):
            older = contr.get("older_action", "")
            newer = contr.get("newer_action", "")
            keep_newer = contr.get("keep_newer", True)

            # Find matching memories
            older_mem = _find_memory_by_action(memories, older)
            newer_mem = _find_memory_by_action(memories, newer)

            if older_mem and newer_mem:
                if keep_newer:
                    store.supersede_memory(older_mem.id, newer_mem.id)
                else:
                    store.supersede_memory(newer_mem.id, older_mem.id)
                contradictions += 1

                logger.info(
                    "memory.contradiction.resolved",
                    {
                        "domain": domain,
                        "older": older,
                        "newer": newer,
                    },
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

        return {"contradictions": contradictions, "insights": insights}

    except Exception as e:
        logger.warning(
            "memory.consolidation.error",
            {"domain": domain, "error": str(e)},
        )
        return {"contradictions": 0, "insights": 0}


def _find_memory_by_action(memories: list[Memory], action: str) -> Memory | None:
    """Find memory by action text (partial match)."""
    action_lower = action.lower()
    for mem in memories:
        if action_lower in mem.action.lower():
            return mem
    return None


def _extract_json(content: str) -> dict | None:
    """Extract JSON from LLM response."""
    import json

    # Ensure content is string
    if not isinstance(content, str):
        content = str(content)

    # Try direct parse
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # Try to find JSON in markdown
    import re

    match = re.search(r"\{[\s\S]*\}", content)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return None


def trigger_consolidation(user_id: str) -> dict[str, Any]:
    """Manually trigger consolidation for a user (sync wrapper)."""
    import asyncio

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If we're in an async context, schedule the job
            # Create a task to run consolidation without blocking
            asyncio.create_task(run_consolidation(user_id))
            return {"status": "scheduled"}
        else:
            return asyncio.run(run_consolidation(user_id))
    except RuntimeError:
        return asyncio.run(run_consolidation(user_id))


# Track message counts per user
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
