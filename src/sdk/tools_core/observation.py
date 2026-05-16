"""Observer and Reflector prompts + LLM runners for Observational Memory.

Design: docs/OBSERVATIONAL_MEMORY_DESIGN.md (sections 4.1, 4.2, 12.3)
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from src.app_logging import get_logger
from src.sdk.messages import Message

logger = get_logger()

OBSERVER_PROMPT = """You are an observer extracting precise facts from a conversation. Output ONLY facts that someone might ask about later — names, numbers, dates, locations, decisions, corrections.

FORMAT: A JSON array of observations. Each observation:
{{
  "id": "obs_<uuid>",
  "content": "subject verb object — exact value, no approximation",
  "priority": "🔴" | "🟡" | "🟢",
  "referenced_date": "ISO date if content mentions a specific date, else null",
  "facts_extracted": [{{"entity": "...", "attribute": "...", "value": "..."}}]
}}

PRIORITY RULES:
🔴 (high): Any fact with a precise value — personal info, numbers, locations, dates, names, decisions
🟡 (medium): Preferences, interests, opinions, plans
🟢 (low): Casual chat, greetings, meta-commentary — SKIP THESE

EXAMPLES of good observations:
❌ "User discussed their commute" — too vague
✅ "commute is 45 minutes each way" — exact value
✅ "works at TechCorp as Senior Backend Engineer" — job info
✅ "watched 22 MCU movies in 2 weeks" — exact count
✅ "graduated with Business Administration from University of Michigan in 2022" — all details

CRITICAL RULES:
1. VALUES MUST BE EXACT. "45 minutes" not "about an hour". "Target" not "a store". "Business Administration" not "a business degree". Copy the user's words verbatim for values.
2. Include ALL factual information — every name, number, date, location, decision. Better to over-extract than under-extract.
3. One fact per observation. Do NOT combine multiple events.
4. If a user provides conflicting information at different times, capture BOTH. The system will resolve which is latest.
5. Skip generic conversation — greetings, small talk, "how are you", acknowledgments.
6. For each fact_value in facts_extracted, use EXACTLY the same value as the observation content.

CONVERSATION:
{conversation}

Respond with ONLY the JSON array, no other text."""

REFLECTOR_PROMPT = """You are a reflector condensing observations into a denser format.

INPUT: A list of observations created over time.
OUTPUT: A JSON object with:
{{
  "id": "refl_<uuid>",
  "reflection_text": "condensed text preserving all key information",
  "dropped_observation_ids": ["obs_...", ...],
  "contradictions_resolved": [{{"entity": "...", "attribute": "...", "old_value": "...", "new_value": "...", "resolution": "explanation"}}],
  "patterns_identified": ["pattern 1", "pattern 2"]
}}

REFLECTION RULES:
1. Preserve ALL factual information — names, numbers, dates, locations
2. Merge observations about the same topic/event into single entries
3. When a correction contradicts an earlier observation, keep only the latest
4. Drop observations that are fully superseded (e.g., user moved A→B→C, keep C only)
5. Identify patterns across observations (e.g., "user regularly visits museums")
6. Keep temporal anchors — don't lose when things happened
7. The reflection should be readable as a standalone summary of what's been observed

OBSERVATIONS:
{observations}

Respond with ONLY the JSON object, no other text."""


def _parse_observer_json(text: str) -> list[dict[str, Any]] | None:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:]) if len(lines) > 1 else text
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    try:
        result = json.loads(text)
        if isinstance(result, list):
            for item in result:
                item["observation_ts"] = item.get(
                    "observation_ts", datetime.now(UTC).isoformat()
                )
            return result
    except json.JSONDecodeError:
        import re

        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group(0))
                if isinstance(result, list):
                    for item in result:
                        item["observation_ts"] = item.get(
                            "observation_ts", datetime.now(UTC).isoformat()
                        )
                    return result
            except json.JSONDecodeError:
                pass
    return None


def _parse_reflector_json(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:]) if len(lines) > 1 else text
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    try:
        result = json.loads(text)
        if isinstance(result, dict):
            result.setdefault("source_observation_range", "")
            result.setdefault(
                "observation_count", len(result.get("dropped_observation_ids", []))
            )
            result.setdefault(
                "token_count",
                len(str(result.get("reflection_text", ""))) // 4,
            )
            return result
    except json.JSONDecodeError:
        import re

        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group(0))
                if isinstance(result, dict):
                    return result
            except json.JSONDecodeError:
                pass
    return None


async def run_observer(
    messages: list[dict[str, Any]],
    provider: Any,
    previous_observations: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]] | None:
    conversation = "\n\n".join(
        f"[{m.get('role', 'user')}] [{m.get('ts', '')}] {m.get('content', '')}"
        for m in messages
    )

    if previous_observations:
        prev_text = "\n".join(
            f"[{o.get('priority', '🟡')}] {o.get('observation_ts', '')[:10]}: {o['content']}"
            for o in previous_observations[-50:]
        )
        prompt = (
            "PREVIOUS OBSERVATIONS (already extracted — do not repeat):\n"
            + prev_text + "\n\n"
            + "NEW CONVERSATION:\n"
            + conversation + "\n\n"
            + "Extract ONLY new facts from the NEW CONVERSATION above. If a fact contradicts "
            + "a previous observation, include the NEW value and mark it as a correction."
        )
    else:
        prompt = conversation

    full_prompt = OBSERVER_PROMPT.format(conversation=prompt)

    msgs = [
        Message.system("You are an Observer. Return only valid JSON."),
        Message.user(full_prompt),
    ]
    result = await provider.chat(msgs)

    if result is None:
        return None

    content = result.content if isinstance(result.content, str) else str(result.content or "")
    observations = _parse_observer_json(content)
    return observations


async def run_reflector(
    observations: list[dict[str, Any]],
    provider: Any,
) -> dict[str, Any] | None:
    prompt = REFLECTOR_PROMPT.format(
        observations=json.dumps(
            [
                {
                    "id": o.get("id", ""),
                    "content": o.get("content", ""),
                    "priority": o.get("priority", "🟢"),
                    "observation_ts": o.get("observation_ts", ""),
                    "referenced_date": o.get("referenced_date"),
                }
                for o in observations
            ],
            indent=2,
        )
    )

    msgs = [
        Message.system("You are a Reflector. Return only valid JSON."),
        Message.user(prompt),
    ]
    result = await provider.chat(msgs)

    if result is None:
        return None

    content = result.content if isinstance(result.content, str) else str(result.content or "")
    reflection = _parse_reflector_json(content)
    return reflection
