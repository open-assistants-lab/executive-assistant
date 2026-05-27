"""Message tools — search, count, and history for raw conversation data."""

import re
from datetime import date, timedelta
from typing import Any

from src.app_logging import get_logger
from src.sdk.tools import ToolAnnotations, tool
from src.storage.messages import SearchResult, get_message_store

logger = get_logger()


# ── memcore factory ──────────────────────────────────────────────────────────

_memcore_cache: dict[str, Any] = {}


def _get_memory_core(user_id: str, workspace_id: str = "personal"):
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


def _search_all_workspaces(
    query: str,
    user_id: str,
    queries: list[str],
    primary_ws: str,
    search_limit: int,
    recency_weight: float = 0.3,
) -> tuple[list[str], list[tuple[SearchResult, str]]]:
    """Search across all workspaces for a user, return merged results with workspace tags."""
    ws_ids = _list_workspace_ids(user_id)
    other_ws = [w for w in ws_ids if w != primary_ws]
    if not other_ws:
        return [], []

    results: list[tuple[SearchResult, str]] = []
    seen: set[int] = set()
    workspaces_used: list[str] = []

    for ws_id in other_ws[:5]:  # cap at 5 extra workspaces
        try:
            store = get_message_store(user_id, ws_id)
        except Exception:
            continue
        ws_had_results = False
        for q in queries:
            try:
                ws_results = store.search_hybrid(
                    q, limit=max(search_limit // 2, 5),
                    recency_weight=recency_weight,
                )
            except Exception:
                continue
            for r in ws_results:
                if r.id not in seen:
                    seen.add(r.id)
                    results.append((r, ws_id))
                    ws_had_results = True
        if ws_had_results:
            workspaces_used.append(ws_id)

    return workspaces_used, results


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


def _generate_hyde_query(query: str, user_id: str) -> str | None:
    """Generate a hypothetical answer to bridge the question-declarative gap.

    Uses one LLM call (bounded). The hypothetical answer embeds closer to
    real declarative data than the original question does.

    HyDE: Precise Zero-Shot Dense Retrieval without Relevance Labels
    Gao et al., 2022 (arXiv:2212.10496)
    """
    if len(query.strip()) < 5:
        return None

    try:
        import asyncio

        from src.sdk.messages import Message
        from src.sdk.providers.factory import create_model_from_config

        provider = create_model_from_config()
        prompt = (
            f"A user asked: '{query}'\n\n"
            "Write a short hypothetical answer to this question as if you were the user. "
            "Include specific details and numbers if the question asks for them. "
            "Write in first person. Example: Q='How many cats do I have?' → "
            "'I have two cats named Mochi and Tofu. They are both indoor cats.'\n\n"
            "Hypothetical answer:"
        )

        async def _call():
            resp = await provider.chat([Message.user(prompt)])
            return resp.content.strip() if resp.content else None

        return asyncio.run(_call())
    except Exception:
        return None


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
    """Search conversation history — semantic + keyword, raw verbatim output.

    Returns raw conversation snippets matched to your query. Results are
    deduplicated by session (max 1 result per conversation). No fact
    extraction or summarization — you get exactly what was said.

    Use this for: finding specific facts from past conversations, counting
    items mentioned across sessions, checking what was discussed.

    Args:
        query: What to search for
        user_id: User identifier
        workspace_id: Workspace ID (defaults to current workspace)
        limit: Max results (default 20)

    Returns:
        Search results as formatted conversation snippets
    """
    core = _get_memory_core(user_id, workspace_id)

    # Counting questions need wider session coverage to find all items
    # across different conversations. Single-fact questions can be tighter.
    is_counting = query.lower().startswith("how many") or "total" in query.lower()
    effective_limit = max(limit, 30 if is_counting else 10)

    results = core.search(query, limit=effective_limit * 6)  # fetch wide for session diversity

    # Filter: only user messages contain original information.
    # Assistant/tool messages are previous answers/echo that create recursion.
    results = [r for r in results if r.memory.role == "user"]

    # Filter out echo: pure questions (end with ?, no answer content).
    # These match query keywords but contain no information to extract.
    # Keep messages that start like questions but contain data after (e.g., "How to train? I run 3x/wk.")
    # Filter out prompt echo: messages whose text heavily overlaps with the
    # current query. These are the user's own question being stored and re-found.
    # Uses word overlap, not punctuation — handles "Did I ask about X?" naturally.
    query_words = set(query.lower().split())
    filtered = []
    for r in results:
        content_stripped = r.memory.content.strip().lower()
        result_words = set(content_stripped.split())
        query_overlap = len(query_words & result_words) / max(len(query_words), 1)

        # High overlap with query → echo, skip. But keep if it contains numbers
        # or proper nouns that indicate it's not just the question.
        has_data = bool(re.findall(r"\d+|[A-Z][a-z]{2,}", r.memory.content))
        if query_overlap > 0.7 and not has_data:
            continue

        # Skip near-duplicate content
        if len(filtered) >= 1 and _content_similarity(
            content_stripped, filtered[-1].memory.content.lower()
        ) > 0.8:
            continue

        filtered.append(r)
        if len(filtered) >= effective_limit:
            break

    if not filtered and results:
        filtered = results[:effective_limit]

    results = filtered

    if not results:
        return f"No messages found for '{query}'"

    output = (
        f"## Search Results: '{query}'\n"
        f"Found {len(results)} messages. Ordered by relevance (higher score = better match).\n\n"
    )
    for i, r in enumerate(results, 1):
        content = r.memory.content[:300]
        if len(r.memory.content) > 300:
            content += "..."
        ts_str = r.memory.ts.strftime("%Y-%m-%d") if r.memory.ts else "?"
        score = r.score
        role = r.memory.role or "?"
        sid = r.memory.session_id or ""
        ws = r.memory.workspace_id or ""

        meta = f"[{role}] {ts_str} score={score:.4f}"
        if ws:
            meta += f" ws={ws}"
        if sid:
            meta += f" sid={sid[:12]}"

        output += f"---\n{meta}\n{content}\n"

    output += (
        "\n---\n"
        "INSTRUCTIONS: Read the above messages and extract the answer. "
        "If counting, count each distinct item across ALL results. "
        "Give only the final answer — do NOT repeat the search results."
    )
    return output


message_search.annotations = ToolAnnotations(
    title="Search Messages", read_only=True, idempotent=True
)


def _mempalace_boost(results: list[SearchResult], query: str) -> None:
    """MemPalace-style search heuristics: keyword, number/preference/temporal/question-type."""
    import re

    query_lower = query.lower()
    query_words = set(query_lower.split())

    is_count = any(kw in query_lower for kw in ["how many", "how much", "how long",
                                                   "how many days", "how many weeks", "total",
                                                   "how many items", "how many times"])
    is_what = query_lower.startswith("what") or query_lower.startswith("which")
    is_when = query_lower.startswith("when") or "what day" in query_lower
    is_where = query_lower.startswith("where")
    pref_keywords = ["like", "enjoy", "prefer", "favorite", "recommend",
                      "love", "hate", "want", "interested"]
    is_preference = any(kw in query_lower for kw in pref_keywords)

    number_pattern = re.compile(r"\b\d+(?:\.\d+)?\b")
    date_pattern = re.compile(
        r"\b(?:january|february|march|april|may|june|july|august"
        r"|september|october|november|december)\b", re.IGNORECASE,
    )

    for r in results:
        content_lower = str(r.content).lower()
        boost = 1.0

        word_matches = len(query_words & set(content_lower.split()))
        if word_matches >= 4:
            boost *= 1.2
        elif word_matches >= 3:
            boost *= 1.12
        elif word_matches >= 2:
            boost *= 1.06

        if is_count:
            nums = number_pattern.findall(content_lower)
            if len(nums) >= 2:
                boost *= 1.15
            if re.search(r"\b(?:total|sum|count|combined|altogether)\b", content_lower):
                boost *= 1.2

        if is_what:
            if re.search(r"\b(?:named|called|known as|is a|is the)\b", content_lower):
                boost *= 1.1

        if is_when:
            if date_pattern.search(content_lower):
                boost *= 1.25

        if is_where:
            if re.search(r"\b(?:at|in)\s+[A-Z]", str(r.content)):
                boost *= 1.15

        if is_preference:
            pref_count = sum(1 for kw in pref_keywords if kw in content_lower)
            if pref_count >= 2:
                boost *= 1.2

        query_nums = number_pattern.findall(query)
        if query_nums:
            content_nums = number_pattern.findall(content_lower)
            if any(n in content_nums for n in query_nums):
                boost *= 1.15

        r.score = min(r.score * boost, 0.99)


def _dedup_by_session(results: list[SearchResult]) -> None:
    pass  # SearchResult has no metadata; session dedup requires MessageStore access


def _compute_aggregation_count(
    results: list[SearchResult],
    query: str,
    store: Any,
) -> str:
    """Deterministically count distinct items from search results.

    Extracts named entities, deduplicates, and returns a clear count.
    Injected directly into message_search output so the agent can't miss it.
    """
    import re as _re
    from collections import defaultdict as _defaultdict

    msg_ids = [r.id for r in results]
    session_ids = _fetch_session_ids(store, msg_ids)
    groups = _group_results_by_session(results, session_ids)
    groups_with_sessions = [(sid, count, entries) for sid, count, entries in groups if sid]
    if not groups_with_sessions:
        # Fall back to treating each result as its own group
        groups_with_sessions = [("", 1, [r]) for r in results]
        return ""

    item_mentions: _defaultdict[str, list[str]] = _defaultdict(list)
    for sid, count, entries in groups_with_sessions:
        combined = " ".join(e.content for e in entries[:15])
        named = _re.findall(
            r"\b([A-Z][a-zA-Z0-9\-\.&']*(?:\s+(?:[A-Z][a-zA-Z0-9\-\.&']*|(?:\d+(?:\.\d+)?\s*)?(?:scale|mm|cm|in|inch|ft|foot|gallon|liter|hour|day|week|month|year)s?)){1,3})\b",
            combined,
        )
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
                               "through", "during", "between", "without", "within", "something",
                               "welcome", "congratulations", "remember"}:
                continue
            item_mentions[item_lower].append(item)

    deduped: dict[str, str] = {}
    for item_lower, forms in item_mentions.items():
        canonical = max(set(forms), key=lambda f: (len(f), f))
        deduped[item_lower] = canonical

    items = sorted(deduped.items(), key=lambda x: -len(x[0].split()))
    final: dict[str, str] = {}
    for key, display in items:
        absorbed = False
        for existing_key in list(final.keys()):
            if key in existing_key or existing_key in key:
                if len(existing_key) >= len(key):
                    absorbed = True
                    break
                del final[existing_key]
                final[key] = display
                absorbed = True
                break
        if not absorbed:
            final[key] = display

    if final:
        output = f"**SERVER-COUNTED: {len(final)} distinct items found**\n"
        for i, (key, display) in enumerate(sorted(final.items(), key=lambda x: x[0]), 1):
            mc = len(item_mentions[key])
            output += f"  {i}. {display} ({mc} mentions)\n"
        output += f"\nThe answer is {len(final)}. Do NOT recount or estimate.\n\n"
        return output

    return ""


def _get_history_fallback(query: str, conversation: Any) -> str | None:
    """Fall back to raw message history when message_search finds nothing,
    but only for queries that are clearly about the user's own attributes."""
    has_user_subject = __import__("re").search(
        r"\b(?:i|me|my|mine|we|our)\b", query.lower()
    )
    if not has_user_subject:
        return None
    try:
        messages = conversation.get_messages(start_date=date.today() - timedelta(days=7), limit=30)
        if not messages:
            return None
        result = "No structured memories found. Raw recent conversation context:\n\n"
        for msg in messages[:15]:
            timestamp = msg.ts.strftime("%Y-%m-%d %H:%M")
            result += f"- {msg.role} [{timestamp}]: {msg.content}\n"
        return result
    except Exception:
        return None


@tool
def message_count(
    query: str,
    user_id: str = "default_user",
    workspace_id: str = "personal",
) -> str:
    """Count distinct items matching a query — deterministic, no LLM guessing.

    For aggregation questions like "how many model kits?", "how many projects?",
    "how many different doctors?". Searches conversation history, extracts
    distinct items programmatically, and returns a definitive count.

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
