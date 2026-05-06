"""Memory tools — SDK-native implementation."""

from datetime import date, timedelta
from typing import Any

from src.app_logging import get_logger
from src.sdk.memory_planner import plan_memory_query
from src.sdk.tools import ToolAnnotations, tool
from src.storage.memory import Memory, get_memory_store
from src.storage.messages import SearchResult, get_message_store

logger = get_logger()


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
    from pathlib import Path as _Path

    workspace_ids: list[str] = []
    ws_base = _Path.home() / "Executive Assistant" / "Workspaces"
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
def memory_get_history(
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


memory_get_history.annotations = ToolAnnotations(
    title="Get Conversation History", read_only=True, idempotent=True
)


@tool
def memory_search(
    query: str,
    user_id: str = "default_user",
    workspace_id: str = "personal",
) -> str:
    """Search through conversation history using keyword + semantic search.

    This is the most comprehensive search - combines exact keyword matching
    with semantic similarity for better results. Automatically generates
    query variants to improve recall across different phrasings.

    Use this when user asks about specific topics from past conversations.

    Args:
        query: Query to search for
        user_id: User identifier
        workspace_id: Workspace ID (defaults to current workspace)

    Returns:
        Search results
    """
    conversation = get_message_store(user_id, workspace_id)
    memory_store = get_memory_store(user_id, workspace_id)
    plan = plan_memory_query(query)
    is_aggregation = plan.intent == "aggregation"

    fact_limit = plan.max_facts if plan.intent != "unknown" else 5
    fact_results = memory_store.find_facts_for_query(query, limit=fact_limit)
    temporal_results = (
        memory_store.find_fact_history_for_query(query, limit=plan.max_history)
        if plan.needs_fact_history
        else []
    )

    # Graph-guided expansion: traverse connected memories for top facts
    connected_memories: list[Memory] = []
    connected_ids: set[str] = {m.id for m in fact_results}
    for fact in fact_results[:3]:
        try:
            neighbors = memory_store.traverse_memories(
                fact.id, max_depth=1, direction="both"
            )
            for n in neighbors:
                neighbor_id = n["node"]["id"]
                if neighbor_id in connected_ids:
                    continue
                connected_ids.add(neighbor_id)
                neighbor_mem = memory_store.get_memory(neighbor_id)
                if neighbor_mem and not neighbor_mem.is_superseded:
                    edge = n["edge"]
                    boost = 1.0 + edge.get("weight", 1.0) * 0.15
                    neighbor_mem._graph_boost = boost
                    neighbor_mem._connected_via = fact.id
                    connected_memories.append(neighbor_mem)
        except Exception:
            pass

    search_limit = 100 if is_aggregation else 8
    result_limit = 50 if is_aggregation else 10

    queries = _expand_queries(query)
    seen_ids: set[int | str] = set()
    all_results: list[SearchResult] = []
    cross_workspace_used: list[str] = []

    recency_keywords = ["current", "latest", "now", "after", "updated", "new",
                         "recently", "last", "nowadays", "these days"]
    recency_boost = any(kw in query.lower() for kw in recency_keywords)

    # Search current workspace even when facts are strong; facts summarize durable state,
    # while messages preserve context and supporting evidence.
    for q in queries:
        results = conversation.search_hybrid(
            q, limit=search_limit,
            recency_weight=0.7 if recency_boost else 0.3,
        )
        for r in results:
            if r.id not in seen_ids:
                seen_ids.add(r.id)
                all_results.append(r)

    # Auto-expand to all workspaces if results are weak
    if len(all_results) < 5:
        cross_workspace_used, cross_results = _search_all_workspaces(
            query, user_id, queries, primary_ws=workspace_id,
            search_limit=search_limit, recency_weight=0.3,
        )
        for r, ws_id in cross_results:
            rkey = f"xw:{ws_id}:{r.id}"
            if rkey not in seen_ids:
                seen_ids.add(rkey)
                r.score *= 0.95  # slight penalty for non-primary workspace
                setattr(r, "_workspace", ws_id)
                all_results.append(r)

    all_results.sort(key=lambda r: r.score, reverse=True)
    all_results = all_results[:result_limit]

    _mempalace_boost(all_results, query)

    all_results.sort(key=lambda r: r.score, reverse=True)
    all_results = all_results[:result_limit]

    if not fact_results and not temporal_results and not all_results:
        fallback = _get_history_fallback(query, conversation)
        if fallback:
            return fallback
        return f"No messages found for '{query}'"

    output = ""
    if fact_results:
        current_facts = [m for m in fact_results if not m.is_superseded]
        superseded_facts = [m for m in fact_results if m.is_superseded]

        facts_to_show = current_facts + superseded_facts
        active_count = len(current_facts)
        output += f"Found {active_count} active facts"
        if superseded_facts:
            output += f" (plus {len(superseded_facts)} outdated)"
        output += ":\n"

        for m in facts_to_show:
            sd = m.structured_data
            previous = sd.get("previous_value")
            previous_text = f" (previous: {previous})" if previous else ""
            superseded_marker = "[OUTDATED] " if m.is_superseded else ""

            replaced = ""
            if m.is_superseded:
                for cur in current_facts:
                    csd = cur.structured_data
                    if (csd.get("entity") == sd.get("entity") and
                        csd.get("attribute") == sd.get("attribute")):
                        replaced = f" → replaced by: {csd.get('value', 'unknown')}"
                        break

            output += (
                f"- {superseded_marker}"
                f"{sd.get('entity', 'user')}.{sd.get('attribute', m.trigger)} = "
                f"{sd.get('value', m.action)}{previous_text}"
                f"{replaced} "
                f"(conf: {min(m.confidence, 1.0):.0%})\n"
            )

    if temporal_results:
        output += f"Found {len(temporal_results)} temporal/update facts:\n"
        for m in temporal_results:
            sd = m.structured_data
            status = "current" if not m.is_superseded else "superseded"
            effective_at = sd.get("effective_at") or m.updated_at.date().isoformat()
            previous = sd.get("previous_value")
            previous_text = f"; previous={previous}" if previous else ""
            output += (
                f"- {effective_at} [{status}] "
                f"{sd.get('entity', 'user')}.{sd.get('attribute', m.trigger)} = "
                f"{sd.get('value', m.action)}{previous_text}\n"
            )

    if connected_memories:
        output += f"Found {len(connected_memories)} connected memories:\n"
        for m in connected_memories[:5]:
            boost_tag = f" [related via:{m._connected_via[:8]}]" if hasattr(m, "_connected_via") else ""
            output += (
                f"- [{m.domain}] {m.trigger}: {m.action}{boost_tag}"
                f" (conf: {min(m.confidence, 1.0):.0%})\n"
            )

    msg_ids = [r.id for r in all_results]
    session_ids = _fetch_session_ids(conversation, msg_ids)
    session_groups = _group_results_by_session(all_results, session_ids)

    has_grouped_sessions = any(sid for sid, _, _ in session_groups)
    if has_grouped_sessions:
        output += f"Found {len(session_groups)} sessions"
        if cross_workspace_used:
            output += f" (searched workspaces: {workspace_id}, {', '.join(cross_workspace_used)})"
        output += ":\n\n"

    if is_aggregation:
        count_output = _compute_aggregation_count(all_results, query, conversation)
        if count_output:
            output += count_output
            return output  # aggregation: skip raw data, return just the count
        output += "(aggregation — count all distinct items below)\n\n"

    if has_grouped_sessions:
        for i, (sid, count, entries) in enumerate(session_groups[:30], 1):
            ws_tag = (
                f"[{getattr(entries[0], '_workspace', workspace_id)}] "
                if hasattr(entries[0], "_workspace")
                else ""
            )
            sid_label = f"sid={sid[:16]}" if sid else f"msg#{entries[0].id}"
            preview = entries[0].content[:250]
            output += f"{i}. {ws_tag}{sid_label} ({count} msgs): {preview}\n"
        if len(session_groups) > 30:
            output += f"\n... ({len(session_groups)} sessions total, top 30 shown)\n"
    else:
        output += f"Found {len(all_results)} conversation matches"
        if cross_workspace_used:
            output += f" (searched: {workspace_id}, {', '.join(cross_workspace_used)})"
        output += ":\n"
        if is_aggregation:
            output += "(aggregation query — count all distinct items across these results)\n\n"
            for i, r in enumerate(all_results[:30], 1):
                ws_tag = f"[{getattr(r, '_workspace', workspace_id)}] " if hasattr(r, '_workspace') else ""
                output += f"{i}. {ws_tag}[{r.role}] {r.content[:250]}\n"
            if len(all_results) > 30:
                output += f"\n... ({len(all_results)} total, top 30 shown)\n"
        else:
            for r in all_results:
                ws_tag = f" [{getattr(r, '_workspace', '')}]" if hasattr(r, '_workspace') else ""
                output += f"- {r.role} ({r.ts.date()}){ws_tag}: {r.content} (score: {r.score:.2f})\n"

    try:
        from src.storage.observation import get_observation_store

        obs_store = get_observation_store(user_id, workspace_id)
        obs_results = obs_store.search_observations(query, limit=5)
        if obs_results:
            output += f"\nFound {len(obs_results)} observations:\n"
            for o in obs_results:
                output += f"[{o['priority']}] {o.get('observation_ts', '')[:10]}: {o['content']}\n"
        refl_results = obs_store.search_reflections(query, limit=2)
        if refl_results:
            output += f"\nFound {len(refl_results)} reflections:\n"
            for reflection in refl_results:
                output += reflection["content"][:200] + "\n"
    except Exception:
        pass

    return output


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
    Injected directly into memory_search output so the agent can't miss it.
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
    """Fall back to raw message history when memory_search finds nothing,
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


memory_search.annotations = ToolAnnotations(
    title="Search Conversations", read_only=True, idempotent=True
)


@tool
def memory_search_all(
    query: str,
    memories_limit: int = 5,
    messages_limit: int = 5,
    insights_limit: int = 3,
    user_id: str = "default_user",
    workspace_id: str = "personal",
) -> str:
    """Search across ALL memory sources simultaneously: facts, preferences, conversations, and insights.

    Use this for aggregation questions (how many, total, all the) or when you need
    comprehensive context about a topic. Searches memories (preferences, facts, workflows),
    conversation history, and synthesized insights in parallel.

    Best for: multi-session questions, preference profiles, total/aggregate queries.

    Args:
        query: Search query
        memories_limit: Max memory results (default: 5)
        messages_limit: Max message results (default: 5)
        insights_limit: Max insight results (default: 3)
        user_id: User identifier
        workspace_id: Workspace ID (defaults to current workspace)

    Returns:
        Unified search results
    """
    store = get_memory_store(user_id, workspace_id)
    plan = plan_memory_query(query)
    fact_limit = plan.max_facts if plan.intent != "unknown" else memories_limit
    fact_results = store.find_facts_for_query(query, limit=fact_limit)
    temporal_results = (
        store.find_fact_history_for_query(query, limit=plan.max_history)
        if plan.needs_fact_history
        else []
    )
    results = store.search_all(
        query,
        memories_limit=memories_limit,
        messages_limit=messages_limit,
        insights_limit=insights_limit,
        user_id=user_id,
        workspace_id=workspace_id,
    )

    parts = [f"## Unified Search Results for '{query}'"]

    if fact_results:
        parts.append(f"\n### Exact Facts ({len(fact_results)})")
        for m in fact_results:
            sd = m.structured_data
            previous = sd.get("previous_value")
            previous_text = f" (previous: {previous})" if previous else ""
            parts.append(
                f"- {sd.get('entity', 'user')}.{sd.get('attribute', m.trigger)} = "
                f"{sd.get('value', m.action)}{previous_text} "
                f"(conf: {min(m.confidence, 1.0):.0%})"
            )

    if temporal_results:
        parts.append(f"\n### Temporal / Update Facts ({len(temporal_results)})")
        for m in temporal_results:
            sd = m.structured_data
            status = "current" if not m.is_superseded else "superseded"
            effective_at = sd.get("effective_at") or m.updated_at.date().isoformat()
            previous = sd.get("previous_value")
            previous_text = f"; previous={previous}" if previous else ""
            parts.append(
                f"- {effective_at} [{status}] "
                f"{sd.get('entity', 'user')}.{sd.get('attribute', m.trigger)} = "
                f"{sd.get('value', m.action)}{previous_text}"
            )

    if results["memories"]:
        parts.append(f"\n### Learned Memories ({len(results['memories'])})")
        for m in results["memories"]:
            parts.append(
                f"- [{m.memory_type}] {m.trigger}: {m.action} (conf: {min(m.confidence, 1.0):.0%})"
            )

    if results["insights"]:
        parts.append(f"\n### Insights ({len(results['insights'])})")
        for i in results["insights"]:
            parts.append(f"- {i.summary} (conf: {min(i.confidence, 1.0):.0%})")

    if results["messages"]:
        parts.append(f"\n### Conversation Messages ({len(results['messages'])})")
        for m in results["messages"]:
            role = m.get("role", "?")
            content = m.get("content", "")
            score = m.get("score", 0)
            parts.append(f"- {role}: {content} (score: {score:.2f})")

    if (
        not fact_results
        and not temporal_results
        and not results["memories"]
        and not results["insights"]
        and not results["messages"]
    ):
        parts.append("\nNo results found across any source.")

    return "\n".join(parts)


memory_search_all.annotations = ToolAnnotations(
    title="Search All Memory", read_only=True, idempotent=True
)


@tool
def memory_search_all_workspaces(
    query: str,
    user_id: str = "default_user",
    workspace_id: str = "personal",
) -> str:
    """Search across ALL available workspaces for the user.

    Use this when you need to find information that might be in a different
    workspace, or when the user asks about something across all their contexts
    (e.g., "what's the total across all my projects?", "find all mentions of Q4 budget").

    Searches the current workspace first, then all others, merging results.

    Args:
        query: Query to search for
        user_id: User identifier
        workspace_id: Current workspace ID
    """
    from src.sdk.memory_planner import plan_memory_query

    plan = plan_memory_query(query)
    is_aggregation = plan.intent == "aggregation"
    search_limit = 100 if is_aggregation else 10

    queries = _expand_queries(query)
    seen_ids: set[int | str] = set()
    all_results: list[SearchResult] = []

    # Search current workspace
    conversation = get_message_store(user_id, workspace_id)
    for q in queries:
        results = conversation.search_hybrid(q, limit=search_limit, recency_weight=0.3)
        for r in results:
            if r.id not in seen_ids:
                seen_ids.add(r.id)
                all_results.append(r)

    # Search all other workspaces
    workspaces_used, cross_results = _search_all_workspaces(
        query, user_id, queries, primary_ws=workspace_id,
        search_limit=search_limit, recency_weight=0.3,
    )
    for r, ws_id in cross_results:
        rkey = f"xw:{ws_id}:{r.id}"
        if rkey not in seen_ids:
            seen_ids.add(rkey)
            setattr(r, "_workspace", ws_id)
            all_results.append(r)

    all_results.sort(key=lambda r: r.score, reverse=True)
    all_results = all_results[:50]

    all_ws = [workspace_id] + workspaces_used
    output = f"Searched workspaces: {', '.join(all_ws)}\n"
    output += f"Found {len(all_results)} matches:\n\n"
    for i, r in enumerate(all_results[:30], 1):
        ws = getattr(r, "_workspace", workspace_id)
        output += f"{i}. [{ws}] [{r.role}] {r.content[:200]}\n"
    if len(all_results) > 30:
        output += f"\n... ({len(all_results)} total, 30 shown)\n"

    return output


memory_search_all_workspaces.annotations = ToolAnnotations(
    title="Search All Workspaces", read_only=True, idempotent=True
)


@tool
def memory_count(
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


memory_count.annotations = ToolAnnotations(
    title="Count Matching Items", read_only=True, idempotent=True
)


@tool
def memory_search_insights(
    query: str,
    method: str = "hybrid",
    limit: int = 5,
    user_id: str = "default_user",
    workspace_id: str = "personal",
) -> str:
    """Search synthesized insights using keyword or semantic search.

    Insights are higher-order patterns discovered from grouping memories.
    Use this when looking for themes, trends, or synthesized knowledge.

    Args:
        query: Search query
        method: Search method (fts, semantic, or hybrid) - default: hybrid
        limit: Maximum results
        user_id: User identifier
        workspace_id: Workspace ID (defaults to current workspace)

    Returns:
        Search results
    """
    store = get_memory_store(user_id, workspace_id)

    if method == "fts":
        results = store.search_insights(query, limit=limit)
    elif method == "semantic":
        results = store.search_insights_semantic(query, limit=limit)
    else:
        fts_results = store.search_insights(query, limit=limit)
        if fts_results:
            results = fts_results
        else:
            results = store.search_insights_semantic(query, limit=limit)

    if not results:
        return f"No insights found for: {query}"

    parts = [f"## Insights for '{query}' ({method})"]
    for insight in results:
        parts.append(
            f"- [{insight.domain}] {insight.summary} (conf: {min(insight.confidence, 1.0):.0%})"
        )

    return "\n".join(parts)


memory_search_insights.annotations = ToolAnnotations(
    title="Search Insights", read_only=True, idempotent=True
)


@tool
def memory_connect(
    memory_id: str,
    target_id: str,
    relationship: str = "relates_to",
    strength: float = 1.0,
    user_id: str = "default_user",
    workspace_id: str = "personal",
) -> str:
    """Create a connection between two memories with a relationship label.

    Use this to link related memories, e.g., marking that one memory
    contradicts, updates, or builds on another.

    Args:
        memory_id: First memory ID
        target_id: Second memory ID
        relationship: Relationship type (relates_to, contradicts, updates, extends, corrects)
        strength: Connection strength 0-1 (default: 1.0)
        user_id: User identifier
        workspace_id: Workspace ID (defaults to current workspace)

    Returns:
        Confirmation message
    """
    store = get_memory_store(user_id, workspace_id)

    mem1 = store.get_memory(memory_id)
    mem2 = store.get_memory(target_id)

    if not mem1:
        return f"Memory not found: {memory_id}"
    if not mem2:
        return f"Memory not found: {target_id}"

    store.add_connection(memory_id, target_id, relationship=relationship, strength=strength)

    return f"Connected {memory_id} → {target_id} ({relationship}, strength: {strength})"


memory_connect.annotations = ToolAnnotations(title="Connect Memories")


@tool
def memory_get_profile(
    user_id: str = "default_user",
    workspace_id: str = "personal",
) -> str:
    """Return the current working memory — what the system knows about the user.

    Includes recent observations, reflections, and facts the Observer has collected.
    Use when: user asks 'what do you know about me?' or the agent needs to
    refresh its understanding of the user.
    """
    try:
        from src.storage.observation import get_observation_store

        obs_store = get_observation_store(user_id, workspace_id)
        recent = obs_store.get_recent_observations(days=7, limit=30)
        reflection = obs_store.get_latest_reflection()

        parts = []
        if recent:
            parts.append("## Recent Observations")
            for obs in recent:
                parts.append(
                    f"{obs['priority']} {obs.get('observation_ts', '')[:10]} {obs['content']}"
                )
        if reflection:
            parts.append(f"## Past Context\n{reflection['content']}")
        if not parts:
            return "No working memory available yet. The Observer has not processed any conversations."

        return "\n\n".join(parts)
    except Exception:
        return "Working memory unavailable. The observation system may not be initialized."


memory_get_profile.annotations = ToolAnnotations(
    title="Get User Profile", read_only=True, idempotent=True
)
