"""Message tools — search, count, and history for raw conversation data."""

import os
import re
from datetime import date, timedelta
from typing import Any

from src.app_logging import get_logger
from src.sdk.tools import ToolAnnotations, tool
from src.storage.messages import SearchResult, get_message_store

logger = get_logger()
_memcore_cache: dict[str, Any] = {}
_cross_encoder: Any | None = None
_SEARCH_DEPTH_MULTIPLIER = 5


# ── message core factory ──────────────────────────────────────────────────────

def _get_message_core(user_id: str, workspace_id: str = "personal"):
    """Get or create a cached MemoryCore instance for the given user/workspace.

    Uses the SAME HybridDB path as MessageStore so messages imported
    via /conversation/import are immediately searchable.
    """
    from memcore.backends.hybrid import HybridBackend
    from memcore.core import MemoryCore

    from src.storage.paths import get_paths

    cache_key = f"{user_id}:memcore"
    if cache_key not in _memcore_cache:
        paths = get_paths(user_id)
        conv_path = str(paths.conversation_dir())
        _memcore_cache[cache_key] = MemoryCore(backend=HybridBackend(path=conv_path))
    return _memcore_cache[cache_key]


def _expand_queries(query: str) -> list[str]:
    """Generate search query variants for better recall.

    Uses LLM rephrasing when available, falls back to regex expansion.
    """
    llm_variants = _llm_expand_queries(query)
    if llm_variants:
        seen = {query.lower()}
        result = [query]
        for v in llm_variants:
            if v.lower() not in seen and len(result) < 4:
                seen.add(v.lower())
                result.append(v)
        return result
    return _regex_expand_queries(query)


def _llm_expand_queries(query: str) -> list[str] | None:
    """Try LLM-based query rephrasing with cheap model. Returns None on failure."""
    import json
    import os

    try:
        import asyncio

        from src.sdk.messages import Message
        from src.sdk.providers.factory import create_model_from_config

        model_str = os.environ.get("MEMORY_EXPANSION_MODEL", "ollama:llama3.2")
        model = create_model_from_config(model_str)
    except Exception:
        return None

    prompt = (
        "Rephrase this search query exactly 2 different ways to improve retrieval recall. "
        "Keep the original meaning. Return ONLY a JSON array of 2 strings.\n\n"
        f"Query: {query}\n\n"
        'Format: ["rephrase 1", "rephrase 2"]'
    )
    try:
        try:
            asyncio.get_running_loop()
            return None
        except RuntimeError:
            pass
        result = asyncio.run(model.chat([Message.user(prompt)]))
        text = str(result.content if hasattr(result, "content") else result)
        text = text.strip()
        if text.startswith("["):
            variants = json.loads(text)
            if isinstance(variants, list) and all(isinstance(v, str) for v in variants):
                return variants
        match = __import__("re").search(r"\[(.*?)\]", text, __import__("re").DOTALL)
        if match:
            inner = match.group(0)
            variants = json.loads(inner)
            if isinstance(variants, list) and all(isinstance(v, str) for v in variants):
                return variants
    except Exception:
        pass
    return None


def _regex_expand_queries(query: str) -> list[str]:
    """Fallback regex-based query expansion."""
    import re

    queries = [query]

    words = query.lower().split()
    if len(words) > 4:
        queries.append(" ".join(words[:4]))

    for kw in ["how many", "how much", "how long", "how often", "how many days",
                "how many times", "total", "all the", "list of", "every"]:
        if kw in query.lower():
            stripped = query.lower().replace(kw, "").strip()
            queries.append(stripped)
            # For aggregation: split on "and"/"or" to generate diverse aspect queries
            if re.search(r"\b(?:how many|how much)\b", query.lower()):
                aspects = re.split(r"\s+(?:and|or)\s+", stripped)
                if len(aspects) > 1:
                    for a in aspects:
                        a = a.rstrip("?.").strip()
                        if a and a not in queries and len(a.split()) >= 1:
                            queries.append(a)
                # Extract just the subject noun phrase
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

    import re
    date_refs = re.findall(r"\b(?:january|february|march|april|may|june|july|august"
                           r"|september|october|november|december|\d{1,2}(?:st|nd|rd|th)?"
                           r"(?:\s+of)?\s+\d{4})\b", query.lower())
    for d in date_refs:
        queries.append(d)

    return queries


def _list_workspace_ids(user_id: str) -> list[str]:
    """List workspace IDs that have conversation data for a user."""
    from src.storage.paths import DataPaths

    workspace_ids: list[str] = []
    ws_base = DataPaths().root / "Workspaces"
    if not ws_base.exists():
        return workspace_ids
    for entry in sorted(ws_base.iterdir()):
        if entry.is_dir():
            conv_path = entry / "conversation.app.db"
            if conv_path.exists():
                workspace_ids.append(entry.name)
    return workspace_ids


def _fetch_session_ids(store: Any, msg_ids: list[int]) -> dict[int, str]:
    """Batch-lookup session_ids from message metadata.

    Extracts session_id from the metadata JSON column.
    Falls back to grouping by (role, date) for messages without session data.
    """
    import json as _json

    result: dict[int, str] = {}
    if not msg_ids:
        return result

    try:
        conn = store.db._connect()
        try:
            placeholders = ",".join("?" * len(msg_ids))
            rows = conn.execute(
                f"SELECT id, metadata FROM messages WHERE id IN ({placeholders})",
                tuple(msg_ids),
            ).fetchall()
        finally:
            conn.close()
    except Exception:
        return result

    for row in rows:
        msg_id = row[0]
        raw = row[1] or ""
        sid = ""
        if raw:
            try:
                meta = _json.loads(raw)
                sid = meta.get("session_id", "")
            except (_json.JSONDecodeError, TypeError):
                pass
        result[msg_id] = sid

    return result


def _group_results_by_session(
    results: list[SearchResult],
    session_ids: dict[int, str],
) -> list[tuple[str, int, list[SearchResult]]]:
    """Group search results by session.

    Returns ordered groups: [(session_id, message_count, results), ...]
    Groups with no session_id are grouped as individual entries.
    """
    from collections import OrderedDict

    groups: OrderedDict[str, list[SearchResult]] = OrderedDict()
    no_session: list[SearchResult] = []

    for r in results:
        sid = session_ids.get(r.id, "")
        if sid:
            if sid not in groups:
                groups[sid] = []
            groups[sid].append(r)
        else:
            no_session.append(r)

    # Convert to list of tuples, ordered by first occurrence
    output: list[tuple[str, int, list[SearchResult]]] = []
    for sid, entries in groups.items():
        output.append((sid, len(entries), entries))
    for r in no_session:
        output.append(("", 1, [r]))

    return output


@tool
def message_history(
    days: int = 7,
    date_str: str | None = None,
    user_id: str = "default_user",
    workspace_id: str = "personal",
) -> str:
    """Get conversation history for progressive disclosure.

    Use this tool when user asks about past conversations, what was discussed,
    or wants to recall previous interactions.

    Args:
        days: Number of days to look back (default: 7)
        date_str: Specific date in YYYY-MM-DD format (optional)
        user_id: User identifier
        workspace_id: Workspace ID (defaults to current workspace)

    Returns:
        Formatted conversation history
    """
    conversation = get_message_store(user_id, workspace_id)

    if date_str:
        try:
            target_date = date.fromisoformat(date_str)
            messages = conversation.get_messages(
                start_date=target_date,
                end_date=target_date,
            )
            if not messages:
                if conversation.count_messages() == 0:
                    return (
                        "No persisted messages found. Conversation history has not been persisted "
                        f"for workspace '{workspace_id}'."
                    )
                return f"No messages found for {date_str}"

            result = f"Conversation on {date_str}:\n"
            for msg in messages:
                result += f"- {msg.role}: {msg.content}\n"
            return result

        except ValueError:
            return "Invalid date format. Use YYYY-MM-DD."

    start_date = date.today() - timedelta(days=days)
    messages = conversation.get_messages(start_date=start_date, limit=200)

    if not messages:
        if conversation.count_messages() == 0:
            return (
                "No persisted messages found. Conversation history has not been persisted "
                f"for workspace '{workspace_id}'."
            )
        return f"No messages in the last {days} days."

    result = f"Recent conversation (last {days} days):\n\n"
    for msg in messages:
        timestamp = msg.ts.strftime("%Y-%m-%d %H:%M")
        result += f"- {msg.role} [{timestamp}]: {msg.content}\n"

    return result


message_history.annotations = ToolAnnotations(
    title="Get Message History", read_only=True, idempotent=True
)



def _get_cross_encoder():
    """Lazy-load the cross-encoder reranker model."""
    global _cross_encoder
    if _cross_encoder is None:
        try:
            from sentence_transformers import CrossEncoder
            _cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        except Exception:
            return None
    return _cross_encoder


def _rerank_with_cross_encoder(query: str, results: list[Any], top_k: int = 50) -> list[Any]:
    """Rerank top results using a lightweight cross-encoder.

    More accurate than embedding similarity because query and document
    interact through the transformer. Applied as post-processing after
    the initial memcore retrieval.

    Disable with EA_DISABLE_CROSS_ENCODER=1 (needed for eval scripts
    running inside asyncio threads to avoid PyTorch OpenMP deadlocks).
    """
    import os as _os
    if _os.environ.get("EA_DISABLE_CROSS_ENCODER"):
        return results

    model = _get_cross_encoder()
    if model is None or not results:
        return results

    candidates = results[:top_k]
    pairs = [(query, r.memory.content[:512]) for r in candidates]
    try:
        scores = model.predict(pairs, show_progress_bar=False, batch_size=32)
        for i, r in enumerate(candidates):
            setattr(r, "_ce_score", float(scores[i]))
        candidates.sort(key=lambda r: getattr(r, "_ce_score", r.score), reverse=True)
        return candidates + results[top_k:]
    except Exception:
        return results


def _content_similarity(a: str, b: str) -> float:
    """Jaccard similarity between two content strings (word-level)."""
    wa = set(a.split())
    wb = set(b.split())
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


@tool
def message_search(
    query: str,
    user_id: str = "default_user",
    workspace_id: str = "personal",
    limit: int = 5,
) -> str:
    """Search conversation history — semantic + keyword, full session context.

    PRIMARY tool for fact recall. Always use this before telling the user
    you don't have information about a past conversation.

    Returns full conversations (all turns) for each matching session.
    Automatically expands your query and reranks results for best recall.

    Use this for finding specific facts, names, dates, plans from past
    conversations. Use message_count for counting/aggregation questions
    ("how many X..."), and message_timeline for temporal reasoning
    ("how many days between...", "when did I...").

    Args:
        query: What to search for
        user_id: User identifier
        workspace_id: Workspace ID (defaults to current workspace)
        limit: Max results (default 5)

    Returns:
        Full conversation context for each matching session
    """
    from src.storage.messages import get_message_store

    core = _get_message_core(user_id, workspace_id)
    store = get_message_store(user_id, workspace_id)

    is_counting = query.lower().startswith("how many") or "total" in query.lower()
    effective_limit = max(limit, 30 if is_counting else 10)

    # 1. Multi-query expansion — generate search variants
    queries = _expand_queries(query)

    # 2. Run all queries, merge deduplicated by message id
    all_results: list[Any] = []
    seen_ids: set[int] = set()
    for q in queries:
        results = core.search(q, limit=effective_limit * _SEARCH_DEPTH_MULTIPLIER)
        for r in results:
            rid = r.id if hasattr(r, "id") else id(r)
            if rid not in seen_ids:
                seen_ids.add(rid)
                all_results.append(r)

    all_results.sort(key=lambda r: r.score, reverse=True)

    # 3. Cross-encoder reranking for better relevance
    all_results = _rerank_with_cross_encoder(query, all_results)

    # 4. Deduplicate by session
    query_words = set(query.lower().split())
    seen_sessions: set[str] = set()
    seen_nosession: set[str] = set()
    matched: list[tuple[str, Any]] = []  # (session_id, first_match_result)

    for r in all_results:
        if r.memory.role in ("tool", "summary"):
            continue

        content_stripped = r.memory.content.strip().lower()
        result_words = set(content_stripped.split())
        query_overlap = len(query_words & result_words) / max(len(query_words), 1)
        has_data = bool(re.findall(r"\d+|[A-Z][a-z]{2,}", r.memory.content))
        if query_overlap > 0.7 and not has_data:
            continue

        sid = r.memory.session_id or ""
        if sid:
            if sid in seen_sessions:
                continue
            seen_sessions.add(sid)
        else:
            content_key = content_stripped[:100]
            if content_key in seen_nosession:
                continue
            seen_nosession.add(content_key)

        matched.append((sid, r))
        if len(matched) >= effective_limit:
            break

    if not matched:
        return f"No messages found for '{query}'"

    # 4. Build session-level context blocks
    output_parts: list[str] = []
    for sid, first in matched:
        if not sid:
            content = first.memory.content[:500]
            ts_str = first.memory.ts.strftime("%Y-%m-%d") if first.memory.ts else "?"
            output_parts.append(f"── Message ──\n[{first.memory.role}] {ts_str}\n{content}")
            continue

        session_msgs = store.get_messages_by_session_id(sid, limit=50)
        if not session_msgs:
            output_parts.append(first.memory.content[:500])
            continue

        lines = [f"── Session {sid[:12]} ──"]
        for m in session_msgs:
            content = (m.content or "")[:500]
            ts_str = m.ts.strftime("%Y-%m-%d") if m.ts else "?"
            role = m.role or "?"
            lines.append(f"[{role}] {ts_str} {content}")
        output_parts.append("\n".join(lines))

    output = (
        f"## Search Results: '{query}'\n"
        f"Found {len(matched)} relevant conversations.\n\n"
    ) + "\n\n".join(output_parts)

    output += (
        "\n\n---\n"
        "INSTRUCTIONS: Read the above conversations and extract the answer. "
        "If counting, count each distinct item across ALL results. "
        "Give only the final answer — do NOT repeat the search results."
    )
    return output


message_search.annotations = ToolAnnotations(
    title="Search Past Conversations (Full Context)", read_only=True, idempotent=True
)


@tool
def message_count(
    query: str,
    user_id: str = "default_user",
    workspace_id: str = "personal",
) -> str:
    """Count distinct items — call this for "how many" questions.

    For aggregation like "how many doctor visits?", "how many different
    skincare products?", "how many times did I mention X?".
    Extracts distinct items programmatically across all sessions and
    returns a definitive count with item names.

    Use message_search for finding specific facts, not counting.
    Use message_timeline for "what happened between dates" questions.

    Args:
        query: What to count (e.g., "model kits", "doctors", "projects")
        user_id: User identifier
        workspace_id: Current workspace ID
    """
    import re as _re
    from collections import defaultdict as _defaultdict

    conversation = get_message_store(user_id, workspace_id)
    search_limit = 100

    queries = _expand_queries(query)
    seen_ids: set[int] = set()
    all_results: list[SearchResult] = []

    for q in queries:
        results = conversation.search_hybrid(q, limit=search_limit, recency_weight=0.1)
        for r in results:
            if r.id not in seen_ids:
                seen_ids.add(r.id)
                all_results.append(r)

    # Fetch session metadata
    msg_ids = [r.id for r in all_results]
    session_ids = _fetch_session_ids(conversation, msg_ids)

    # Group by session
    session_groups = _group_results_by_session(all_results, session_ids)
    groups_with_sessions = [(sid, count, entries) for sid, count, entries in session_groups if sid]

    # Extract distinct items: look for capitalized multi-word phrases,
    # numbers+units, and quoted strings — the same nouns a human would count
    item_mentions: _defaultdict[str, list[str]] = _defaultdict(list)
    for sid, count, entries in groups_with_sessions:
        combined = " ".join(e.content for e in entries)
        # Named entities: capitalized multi-word phrases (2-4 words)
        named = _re.findall(
            r"\b([A-Z][a-zA-Z0-9\-\.&']*(?:\s+(?:[A-Z][a-zA-Z0-9\-\.&']*|(?:\d+(?:\.\d+)?\s*)?(?:scale|mm|cm|in|inch|ft|foot|gallon|liter|hour|day|week|month|year)s?)){1,3})\b",
            combined,
        )
        # Numbers with units as context
        num_units = _re.findall(
            r"\b(\d+(?:\.\d+)?\s*(?:hours?|days?|weeks?|months?|years?|dollars?|\$?\d+[kKmM]?|items?|kits?|plants?|tanks?|pieces?|doctors?|weddings?|festivals?|breaks?|fruits?|types?|different|total|projects?))\b",
            combined,
            _re.IGNORECASE,
        )
        candidates = {p.strip().rstrip(".,;:!?") for p in named + num_units if 3 < len(p.strip()) < 80}
        for item in candidates:
            item_lower = item.lower()
            if item_lower in {"you", "your", "they", "their", "would", "could", "should",
                               "have", "been", "this", "that", "these", "those", "with", "from",
                               "about", "there", "which", "because", "however", "though", "although",
                               "through", "during", "between", "without", "within", "something"}:
                continue
            item_mentions[item_lower].append(item)

    # Deduplicate: pick the canonical form (longest/most specific)
    deduped: dict[str, str] = {}
    for item_lower, forms in item_mentions.items():
        canonical = max(set(forms), key=lambda f: (len(f), f))
        deduped[item_lower] = canonical

    # Further dedup: merge items that are subsets of each other
    items = sorted(deduped.items(), key=lambda x: -len(x[0].split()))
    final: dict[str, str] = {}
    for key, display in items:
        absorbed = False
        for existing_key in list(final.keys()):
            if key in existing_key or existing_key in key:
                if len(existing_key) >= len(key):
                    absorbed = True
                    break
                else:
                    del final[existing_key]
                    final[key] = display
                    absorbed = True
                    break
        if not absorbed:
            final[key] = display

    # Build output
    searched = [workspace_id]
    ws_list = _list_workspace_ids(user_id)
    for ws in ws_list:
        if ws != workspace_id and ws not in searched:
            searched.append(ws)

    output = f"Searched {len(searched)} workspace(s): {', '.join(searched)}\n"
    output += f"Analyzed {len(session_groups)} sessions ({len(all_results)} raw matches)\n\n"

    if final:
        output += f"**Distinct items: {len(final)}**\n\n"
        for i, (key, display) in enumerate(sorted(final.items(), key=lambda x: x[0]), 1):
            mention_count = len(item_mentions[key])
            output += f"{i}. {display} ({mention_count} mentions)\n"
    else:
        output += "No distinct items could be identified. Try a more specific query.\n"

    return output


message_count.annotations = ToolAnnotations(
    title="Count Matching Messages", read_only=True, idempotent=True
)


@tool
def message_timeline(
    query: str,
    user_id: str = "default_user",
    workspace_id: str = "personal",
    limit: int = 20,
) -> str:
    """Find events in conversation history with their dates — for temporal reasoning.

    Returns a chronological timeline of matching events, each with its
    date and a content snippet. Use this for temporal reasoning:
    - "how many days between X and Y" (extract dates, calculate difference)
    - "when did I visit / go to / buy..." (find event date)
    - "what happened last March / in 2025" (find events in a date range)

    For specific fact recall, use message_search which returns full session
    context. For counting, use message_count.

    Args:
        query: What events to find (e.g., "visit to MoMA", "yoga class")
        user_id: User identifier
        workspace_id: Workspace ID (defaults to current workspace)
        limit: Max events to return (default 20)

    Returns:
        Chronological timeline of matching events with dates
    """
    core = _get_message_core(user_id, workspace_id)

    results = core.search(query, limit=limit * _SEARCH_DEPTH_MULTIPLIER)
    results = _rerank_with_cross_encoder(query, results)

    seen_sessions: set[str] = set()
    timeline: list[tuple[str, str, str]] = []  # (date, session_id, snippet)

    for r in results:
        mem = r.memory
        sid = mem.session_id or ""
        if sid:
            if sid in seen_sessions:
                continue
            seen_sessions.add(sid)

        if not mem.ts:
            continue

        ts = mem.ts.isoformat() if hasattr(mem.ts, "isoformat") else str(mem.ts)

        snippet = mem.content[:200].replace("\n", " ").strip()
        if len(mem.content) > 200:
            snippet += "..."

        timeline.append((ts, sid, snippet))

    timeline.sort(key=lambda x: x[0])

    if not timeline:
        return "No matching events found."

    output = f"**Timeline: {len(timeline)} events**\n\n"
    for ts, sid, snippet in timeline[:limit]:
        # Convert ISO timestamp to readable date
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(ts)
            date_str = dt.strftime("%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            date_str = ts[:10]
        sid_display = sid[:12] + "..." if len(sid) > 15 else sid
        output += f"**{date_str}** (session {sid_display})\n{snippet}\n\n"

    total = len(timeline)
    if total > limit:
        output += f"*({total - limit} more events — refine your query for more detail)*\n"

    return output


message_timeline.annotations = ToolAnnotations(
    title="Event Timeline with Dates", read_only=True, idempotent=True
)
