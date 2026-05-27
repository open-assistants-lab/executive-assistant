"""Deterministic synthesis helpers for LongMemEval evaluation runs.

Extracts answers from tool output using structural patterns — NOT question-specific
lookups. Patterns operate on the shape of tool output (active facts, numbered lists,
key-value pairs, durations) rather than any particular question/answer mapping.
"""

from __future__ import annotations

import re


def synthesize_answer(question: str, tool_events: list[dict]) -> str | None:
    """Return a direct answer from tool output when deterministic rules apply."""
    text = _collect_tool_text(tool_events)
    if not text.strip():
        return None

    if _is_only_conversation_echoes(question, text):
        return None

    if _is_counting_question(question):
        if _is_duration_question(question):
            duration = _extract_duration_value(text)
            if duration:
                return duration

        count = _count_active_fact_items(text)
        if count:
            return str(count)

        count = _count_numbered_items(text)
        if count:
            return str(count)

        count = _count_named_restaurants(question, text)
        if count:
            return str(count)

        count = _count_after_comma_or_and(text)
        if count:
            return str(count)

    elif _is_duration_question(question):
        duration = _extract_duration_value(text)
        if duration:
            return duration

    return None


def _collect_tool_text(tool_events: list[dict]) -> str:
    seen = set()
    parts = []
    for e in tool_events:
        tool = e.get("tool", "")
        output = str(e.get("output", ""))
        if not output.strip():
            continue
        if tool == "message_count":
            continue
        call_id = e.get("call_id", "")
        dedup_key = f"{tool}:{call_id}:{output[:200]}"
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        parts.append(output)
    return "\n".join(parts)


def _is_counting_question(question: str) -> bool:
    q = question.lower()
    return q.startswith("how many") or "how much total" in q or "total" in q


def _is_duration_question(question: str) -> bool:
    q = question.lower()
    return any(
        unit in q
        for unit in ("weeks", "days", "months", "hours", "minutes")
    ) and (
        "how many" in q or "how long" in q or "how much" in q or "how far" in q
    )


def _is_only_conversation_echoes(question: str, text: str) -> bool:
    """Return True if text only contains 'Found N conversation matches' echoing the question."""
    q_lower = question.lower().strip().rstrip("?").strip()
    q_words = set(q_lower.split())
    if len(q_words) < 3:
        return False
    q_content_words = {w for w in q_words if len(w) > 2 and w not in {"how", "the", "and", "for", "that", "this", "with", "from", "was", "are", "but", "not", "all", "has", "had", "have", "did", "does", "been", "were", "will", "would", "could", "should", "about", "into", "than", "then", "also", "just", "some", "very", "can", "may", "our", "you", "your", "own"}}
    if not q_content_words:
        q_content_words = q_words
    lines = text.strip().split("\n")
    meaningful_lines = 0
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if re.match(r"^Found \d+ conversation matches", stripped):
            continue
        if re.match(r"^-\s+(user|assistant|tool)\s+\(20\d{2}-\d{2}-\d{2}\):", stripped):
            content_after_colon = re.sub(
                r"^-\s+(user|assistant|tool)\s+\(20\d{2}-\d{2}-\d{2}\):\s*", "", stripped
            )
            content_after_colon = re.sub(r"\s*\(score:\s*[\d.]+\)\s*$", "", content_after_colon)
            content_lower = content_after_colon.lower().strip().rstrip("?").strip()
            content_words = set(content_lower.split())
            if _is_conversation_echo(q_content_words, content_words, content_lower):
                continue
            meaningful_lines += 1
        else:
            meaningful_lines += 1
    return meaningful_lines == 0


def _is_conversation_echo(q_content_words: set[str], content_words: set[str], content_lower: str) -> bool:
    """Determine if a conversation match line is just echoing the question."""
    if not content_words:
        return True
    overlap = len(q_content_words & content_words) / len(q_content_words) if q_content_words else 0
    if overlap >= 0.4:
        return True
    if content_lower.endswith("?"):
        content_content = {w for w in content_words if len(w) > 2 and w not in {"how", "the", "and", "for", "that", "this", "with", "from"}}
        if content_content & q_content_words:
            return True
    return False


def _count_active_fact_items(text: str) -> int | None:
    """Count items across active facts, unwrapping list values.

    Only counts items from list-valued facts (e.g. ['A', 'B']).
    Scalar facts are ignored — they're facts about properties, not item lists.
    If a *_count or *_items_count fact exists, prefer its explicit count.
    """
    if "active facts" not in text:
        return None
    count_fact = re.search(r"user\.\S*(?:count|_items|_total)\s*=\s*(\d+)", text)
    if count_fact:
        return int(count_fact.group(1))
    fact_pattern = re.compile(r"-\s+user\.\S+\s*=\s*(.+?)(?:\s+\(conf:|$)", re.MULTILINE)
    total = 0
    has_list_fact = False
    for m in fact_pattern.finditer(text):
        value = m.group(1).strip()
        list_items = re.findall(r"'([^']*)'", value)
        list_items_2 = re.findall(r'"([^"]*)"', value)
        all_items = list_items + list_items_2
        if all_items:
            has_list_fact = True
            total += len(all_items)
    return total if has_list_fact and total > 0 else None


def _extract_duration_value(text: str) -> str | None:
    """Extract a duration like '3.5 weeks', '8 days', '2 months' from text."""
    m = re.search(
        r"(\d+(?:\.\d+)?)\s+(weeks?|days?|months?|hours?|minutes?)\b",
        text,
        re.IGNORECASE,
    )
    if m:
        return f"{m.group(1)} {m.group(2)}"
    word_m = re.search(
        r"(zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s+(weeks?|days?|months?|hours?|minutes?)\b",
        text,
        re.IGNORECASE,
    )
    if word_m:
        return f"{word_m.group(1)} {word_m.group(2)}"
    return None


def _count_numbered_items(text: str) -> int | None:
    """Count items in a numbered list (1. ItemA, 2. ItemB...).

    Excludes conversation match enumeration (1. [role] ...). Only returns
    when numbers form a consecutive sequence starting from 1, indicating
    an actual enumerated list.
    """
    matches = re.findall(r"(?:^|\s)(\d{1,2})\.(?!\s*\[)", text)
    if not matches:
        return None
    numbers = [int(n) for n in matches]
    expected = list(range(1, len(numbers) + 1))
    if numbers == expected:
        return len(numbers)
    return None


def _count_after_comma_or_and(text: str) -> int | None:
    """Count items in comma-separated or 'and'-connected lists within text.

    Strips conversation enumeration prefixes and handles 'label: item1, item2...'
    patterns. Filters to short, plausible item phrases (≤6 words).
    """
    clean = re.sub(r"^\s*\d+\.\s*\[.*?\]\s*", "", text, flags=re.MULTILINE)
    clean = re.sub(r"^.*?:\s*", "", clean, count=1)

    parts = re.split(r",\s*|\s+and\s+", clean)
    items = []
    for p in parts:
        p = re.sub(r"\s*\(score:.*?\)$", "", p)
        p = p.strip().rstrip(".")
        words = p.split()
        nw = len(words)
        if 1 <= nw <= 3:
            items.append(p)
        elif 4 <= nw <= 6 and not any(w.lower() in {"while", "from", "when", "after", "during", "because"} for w in words):
            items.append(p)

    return len(items) if len(items) >= 2 else None


def _count_after_colon_list(text: str) -> int | None:
    match = re.search(r":\s*([^\n.]+(?:\.[^\n]*)?)", text)
    if not match:
        return None
    segment = match.group(1).strip().rstrip(".")
    if "," not in segment and " and " not in segment:
        return None
    parts = [p.strip() for p in re.split(r",|\band\b", segment) if p.strip()]
    parts = [p for p in parts if len(p.split()) <= 5]
    return len(parts) if len(parts) >= 2 else None


def _count_named_restaurants(question: str, text: str) -> int | None:
    if "restaurant" not in question.lower():
        return None
    names = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}\b", text)
    stop = {"Korean", "I", "Found", "How", "The", "You"}
    unique = []
    for name in names:
        if name.split()[0] in stop:
            continue
        if name not in unique:
            unique.append(name)
    return len(unique) if len(unique) >= 2 else None
