"""Memory tools for the Executive Assistant agent.

Implements progressive disclosure pattern with 3 layers:
- Layer 1: memory_search - Compact index (~50-100 tokens/result)
- Layer 2: memory_timeline - Chronological context (~100-200 tokens)
- Layer 3: memory_get - Full details (~500-1000 tokens per memory)

ALWAYS follow the 3-layer workflow to minimize token usage.
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from pathlib import Path
from typing import Any

from langchain_core.tools import tool

from src.memory import (
    MemoryStore,
    MemoryCreate,
    MemorySearchParams,
    MemoryTimelineParams,
    MemoryType,
    MemorySource,
)


_store_cache: dict[str, MemoryStore] = {}


def _get_store(user_id: str, data_path: Path) -> MemoryStore:
    """Get or create MemoryStore for user."""
    if user_id not in _store_cache:
        _store_cache[user_id] = MemoryStore(user_id=user_id, data_path=data_path)
    return _store_cache[user_id]


def _format_search_results(results: list[Any]) -> str:
    """Format search results as compact table."""
    if not results:
        return "No memories found."

    lines = [
        "## Memory Search Results",
        "",
        "| ID | Type | Title | Project | Date |",
        "|----|------|-------|---------|------|",
    ]

    for r in results:
        project = r.project or "-"
        date = r.occurred_at[:10] if r.occurred_at else r.created_at[:10]
        lines.append(f"| {r.id} | {r.type} | {r.title[:40]} | {project} | {date} |")

    lines.append("")
    lines.append(f"Found {len(results)} memories. Use `memory_get` with IDs to fetch full details.")

    return "\n".join(lines)


def _format_timeline(timeline: dict[str, Any]) -> str:
    """Format timeline results."""
    lines = ["## Memory Timeline", ""]

    if timeline.get("before"):
        lines.append("### Before:")
        for entry in timeline["before"]:
            title = entry.get("title", "")[:50]
            date = entry.get("occurred_at", "")[:10] if entry.get("occurred_at") else ""
            facts = entry.get("facts", [])
            facts_str = f" - {facts[0]}" if facts else ""
            lines.append(f"- [{date}] {title}{facts_str}")
        lines.append("")

    if timeline.get("anchor"):
        lines.append("### Anchor:")
        anchor = timeline["anchor"]
        title = anchor.get("title", "")
        subtitle = anchor.get("subtitle", "")
        lines.append(f"**{title}**")
        if subtitle:
            lines.append(f"*{subtitle}*")
        lines.append("")

    if timeline.get("after"):
        lines.append("### After:")
        for entry in timeline["after"]:
            title = entry.get("title", "")[:50]
            date = entry.get("occurred_at", "")[:10] if entry.get("occurred_at") else ""
            facts = entry.get("facts", [])
            facts_str = f" - {facts[0]}" if facts else ""
            lines.append(f"- [{date}] {title}{facts_str}")
        lines.append("")

    return "\n".join(lines)


def _format_memory_details(memories: list[Any]) -> str:
    """Format full memory details."""
    if not memories:
        return "No memories found with those IDs."

    lines = ["## Memory Details", ""]

    for m in memories:
        lines.append(f"### {m.title}")
        lines.append(f"**ID**: {m.id}")
        lines.append(f"**Type**: {m.type.value}")
        lines.append(f"**Confidence**: {m.confidence}")
        if m.project:
            lines.append(f"**Project**: {m.project}")
        if m.occurred_at:
            lines.append(f"**Occurred**: {m.occurred_at.strftime('%Y-%m-%d %H:%M')}")
        lines.append("")

        if m.subtitle:
            lines.append(f"*{m.subtitle}*")
            lines.append("")

        if m.narrative:
            lines.append(m.narrative)
            lines.append("")

        if m.facts:
            lines.append("**Facts:**")
            for fact in m.facts:
                lines.append(f"- {fact}")
            lines.append("")

        if m.concepts:
            lines.append(f"**Concepts**: {', '.join(m.concepts)}")
            lines.append("")

        if m.entities:
            lines.append(f"**Entities**: {', '.join(m.entities)}")
            lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)


# Memory store context - set by agent factory (context-local to avoid cross-request leakage)
_current_store_var: ContextVar[MemoryStore | None] = ContextVar("memory_store", default=None)


def set_memory_store(store: MemoryStore) -> Token[MemoryStore | None]:
    """Set the current memory store context for this execution context."""
    return _current_store_var.set(store)


def reset_memory_store(token: Token[MemoryStore | None]) -> None:
    """Reset the current memory store context using a token from set_memory_store."""
    _current_store_var.reset(token)


def get_memory_store() -> MemoryStore | None:
    """Get the current memory store context."""
    return _current_store_var.get()


@tool
def memory_search(
    query: str | None = None,
    type: str | None = None,
    project: str | None = None,
    date_start: str | None = None,
    date_end: str | None = None,
    limit: int = 20,
) -> str:
    """Search memories and get a compact index with IDs.

    LAYER 1 of progressive disclosure (~50-100 tokens per result).
    ALWAYS start with this tool to find relevant memories.

    Args:
        query: Search query (supports FTS5 syntax: AND, OR, NOT, "phrases")
        type: Filter by memory type: profile, contact, preference, schedule,
              task, decision, insight, context, goal, chat, feedback, personal
        project: Filter by project name
        date_start: Filter by start date (YYYY-MM-DD)
        date_end: Filter by end date (YYYY-MM-DD)
        limit: Maximum results (default 20, max 100)

    Returns:
        Compact table with IDs, titles, types, dates. Use memory_get with
        IDs to fetch full details.

    Example:
        memory_search(query="authentication decision", type="decision", limit=10)
        # Returns IDs, then use: memory_get(ids=["mem-abc123", "mem-def456"])
    """
    store = get_memory_store()
    if store is None:
        return "Error: Memory store not initialized."

    try:
        memory_type = MemoryType(type) if type else None
    except ValueError:
        valid_types = [t.value for t in MemoryType]
        return f"Invalid type '{type}'. Valid types: {', '.join(valid_types)}"

    params = MemorySearchParams(
        query=query,
        type=memory_type,
        project=project,
        date_start=date_start,
        date_end=date_end,
        limit=min(limit, 100),
    )

    results = store.search(params)
    return _format_search_results(results)


@tool
def memory_timeline(
    anchor_id: str | None = None,
    query: str | None = None,
    depth_before: int = 3,
    depth_after: int = 3,
    project: str | None = None,
) -> str:
    """Get chronological context around a memory or search result.

    LAYER 2 of progressive disclosure (~100-200 tokens).
    Use after memory_search to understand narrative context.

    Args:
        anchor_id: Memory ID to center timeline around (optional if query provided)
        query: Search to find anchor automatically (optional if anchor_id provided)
        depth_before: Number of memories before anchor (default 3, max 20)
        depth_after: Number of memories after anchor (default 3, max 20)
        project: Filter by project name

    Returns:
        Timeline showing what happened before/during/after the anchor point.

    Example:
        memory_timeline(anchor_id="mem-abc123", depth_before=5, depth_after=5)
    """
    store = get_memory_store()
    if store is None:
        return "Error: Memory store not initialized."

    if not anchor_id and not query:
        return "Error: Either anchor_id or query must be provided."

    params = MemoryTimelineParams(
        anchor_id=anchor_id,
        query=query,
        depth_before=min(depth_before, 20),
        depth_after=min(depth_after, 20),
        project=project,
    )

    try:
        timeline = store.timeline(params)
        return _format_timeline(timeline)
    except ValueError as e:
        return f"Error: {e}"


@tool
def memory_get(ids: list[str]) -> str:
    """Fetch full details for specific memories by IDs.

    LAYER 3 of progressive disclosure (~500-1000 tokens per memory).
    ALWAYS batch multiple IDs in a single call.
    ONLY use after filtering with memory_search.

    Args:
        ids: List of memory IDs from memory_search results (REQUIRED)

    Returns:
        Complete memory details including narrative, facts, concepts, entities.

    Example:
        # After memory_search returns IDs:
        memory_get(ids=["mem-abc123", "mem-def456", "mem-ghi789"])

    WARNING: Avoid fetching many memories at once. Start with memory_search
    to identify the most relevant IDs, then fetch only those.
    """
    store = get_memory_store()
    if store is None:
        return "Error: Memory store not initialized."

    if not ids:
        return "Error: No memory IDs provided."

    if len(ids) > 20:
        return f"Error: Too many IDs ({len(ids)}). Maximum 20 per call. Use memory_search to filter first."

    memories = store.get_batch(ids)

    if not memories:
        return f"No memories found with IDs: {ids}"

    return _format_memory_details(memories)


@tool
def memory_save(
    title: str,
    type: str,
    narrative: str | None = None,
    project: str | None = None,
    facts: list[str] | None = None,
    concepts: list[str] | None = None,
    entities: list[str] | None = None,
    occurred_at: str | None = None,
    confidence: float = 0.7,
    source: str = "learned",
) -> str:
    """Save a new memory observation.

    Use this to store any information worth remembering about the user,
    their work, their preferences, or their context.

    Args:
        title: Short summary (~10 words, REQUIRED)
        type: Memory type (REQUIRED):
            - profile: About the user themselves
            - contact: About other people
            - preference: User preferences
            - schedule: Time commitments, meetings
            - task: Todos, deadlines, deliverables
            - decision: Decisions made with rationale
            - insight: Patterns observed about user
            - context: Background info, project context
            - goal: Goals, aspirations
            - chat: Casual sharing, venting
            - feedback: User's feelings about the agent
            - personal: Family, health, hobbies
        narrative: Full description (~200 words)
        project: Associated project name
        facts: Key facts extracted (list of strings)
        concepts: Tags or concepts (list of strings)
        entities: Named entities - people, companies, etc. (list of strings)
        occurred_at: When the event happened (ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM)
        confidence: Confidence level 0.0-1.0 (default 0.7)
        source: How memory was acquired: explicit, learned, inferred (default learned)

    Returns:
        ID of created memory.

    Example:
        memory_save(
            title="Prefers async communication",
            type="preference",
            narrative="User prefers async communication over real-time meetings for non-urgent matters.",
            facts=["Prefers Slack over Zoom", "Responds faster to written messages"],
            concepts=["communication", "productivity"],
            confidence=0.9,
        )
    """
    store = get_memory_store()
    if store is None:
        return "Error: Memory store not initialized."

    try:
        memory_type = MemoryType(type)
    except ValueError:
        valid_types = [t.value for t in MemoryType]
        return f"Invalid type '{type}'. Valid types: {', '.join(valid_types)}"

    try:
        memory_source = MemorySource(source)
    except ValueError:
        valid_sources = [s.value for s in MemorySource]
        return f"Invalid source '{source}'. Valid sources: {', '.join(valid_sources)}"

    from datetime import datetime

    occurred_dt = None
    if occurred_at:
        try:
            if "T" in occurred_at:
                occurred_dt = datetime.fromisoformat(occurred_at.replace("Z", "+00:00"))
            else:
                occurred_dt = datetime.fromisoformat(occurred_at)
        except ValueError:
            return f"Invalid date format: {occurred_at}. Use YYYY-MM-DD or YYYY-MM-DDTHH:MM"

    data = MemoryCreate(
        title=title,
        type=memory_type,
        narrative=narrative,
        project=project,
        facts=facts or [],
        concepts=concepts or [],
        entities=entities or [],
        occurred_at=occurred_dt,
        confidence=confidence,
        source=memory_source,
    )

    memory = store.add(data)

    return f"Memory saved successfully.\n\nID: {memory.id}\nType: {memory.type.value}\nTitle: {memory.title}"


@tool
def memory_delete(
    memory_id: str,
) -> str:
    """Delete (archive) a memory by ID.

    Args:
        memory_id: The ID of the memory to delete (e.g., "mem-abc123")

    Returns:
        Confirmation message.

    Example:
        memory_delete(memory_id="mem-abc123")
    """
    store = get_memory_store()
    if store is None:
        return "Error: Memory store not initialized."

    success = store.delete(memory_id)

    if success:
        return f"Memory {memory_id} has been deleted (archived)."
    else:
        return f"Memory {memory_id} not found or already deleted."


MEMORY_WORKFLOW = """
## Memory Search Workflow (ALWAYS FOLLOW)

1. **memory_search(query)** → Get index with IDs (~50-100 tokens/result)
   - Start here to find relevant memories
   - Review results and identify interesting IDs

2. **memory_timeline(anchor_id)** → Get context (~100-200 tokens)
   - Optional: Use when narrative context matters
   - Shows what happened before/after

3. **memory_get(ids=[...])** → Fetch full details (~500-1000 tokens per memory)
   - ONLY for filtered, relevant IDs
   - Batch multiple IDs in single call
   - NEVER fetch without filtering first

4. **memory_delete(memory_id)** → Delete archived memory
   - Use to remove incorrect or outdated memories

**Token savings**: 3-layer approach uses ~10x fewer tokens than fetching everything.
"""
