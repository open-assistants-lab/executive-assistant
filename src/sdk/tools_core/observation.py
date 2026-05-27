"""Observer and Reflector prompts + LLM runners.

The Observer extracts facts from conversations as observations.
The Reflector discovers patterns and synthesizes reflections from observations.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from src.app_logging import get_logger
from src.sdk.messages import Message

logger = get_logger()

OBSERVER_PROMPT = """You are an observer agent. Your job is to extract key facts from a conversation and record them as precise, concise observations.

Input: A conversation log between a user and an AI assistant.

Output: A JSON array of observations. Each observation must have:
- "id": a unique ID like "obs_<uuid>"
- "content": ONE fact per observation, in plain English. Be exact with values (names, numbers, dates).
- "priority": one of "\U0001f534" (high — precise value like name, address, number), "\U0001f7e1" (medium — preference, opinion), "\U0001f7e2" (low — context, trivia)
- "referenced_date": the date mentioned in the observation content, or "" if none

CRITICAL RULES:
- One fact per observation. Do not combine multiple facts.
- Use exact values as stated. Never paraphrase numbers or proper nouns.
- If the user CORRECTS previously stated information, capture both as separate observations with different timestamps.
- Skip generic chat, greetings, and meta-commentary.
- Skip observations already observed (listed below as known).

{conversation}

{previous_context}

Return ONLY the JSON array, no markdown wrapping, no explanation."""

REFLECTOR_PROMPT = """You are a reflection agent. Your job is to think about what you know about a user and discover patterns, relationships, and deeper meaning.

Input: All observations collected about the user, plus any previous reflections for context.

Output: A JSON array of reflections. Each reflection must have:
- "id": a unique ID like "refl_<uuid>"
- "content": A synthesized insight — not a fact, but what the facts MEAN when considered together. Patterns, contradictions, values, trajectories, predictions.
- "domain": Category label (preference, career, lifestyle, relationship, skill, value, habit, health, finance, etc.)
- "linked_observation_ids": List of observation IDs that support this reflection

CRITICAL RULES:
- Do NOT repeat facts. Observations already say "lives in Denver." You say WHY it matters — "Has relocated twice for family; values school quality above career."
- Discover multi-observation patterns. Single facts do not need reflection.
- If observations contradict ("lives in Seattle" vs "lives in Denver"), note the change: "Previously in Seattle, now in Denver as of DATE. Reason: ..."
- Generate predictions where patterns warrant: "May relocate again within 2 years based on past behavior."
- Quality over quantity. 3-5 meaningful reflections are better than 15 trivial ones.

{observations}

{previous_reflections}

Return ONLY the JSON array, no markdown wrapping, no explanation."""


def _parse_json_array(text: str) -> list[dict[str, Any]] | None:
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


async def run_observer(
    messages: list[dict[str, Any]],
    provider: Any,
    previous_observations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    conversation = "\n\n".join(
        f"[{m.get('role', 'user')}] [{m.get('ts', '')}] {m.get('content', '')}"
        for m in messages
    )

    previous_context = ""
    if previous_observations:
        prev_text = "\n".join(
            f"[{o.get('priority', '\U0001f7e1')}] {o.get('observation_ts', '')[:10]}: {o['content']}"
            for o in previous_observations[-50:]
        )
        previous_context = (
            "KNOWN OBSERVATIONS (do not repeat):\n" + prev_text + "\n\n"
            "NEW CONVERSATION:\n"
            + conversation
        )
    else:
        previous_context = conversation

    full_prompt = OBSERVER_PROMPT.format(
        conversation=conversation,
        previous_context=previous_context,
    )

    msgs = [
        Message.system("You are an Observer. Return only valid JSON."),
        Message.user(full_prompt),
    ]
    result = await provider.chat(msgs)

    if result is None:
        return {"observations": []}

    content = result.content if isinstance(result.content, str) else str(result.content or "")
    observations = _parse_json_array(content)
    return {"observations": observations or []}


async def run_reflector(
    observations: list[dict[str, Any]],
    provider: Any,
    previous_reflections: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    obs_text = json.dumps(
        [
            {
                "id": o.get("id", ""),
                "content": o.get("content", ""),
                "priority": o.get("priority", "\U0001f7e2"),
                "observation_ts": o.get("observation_ts", ""),
                "referenced_date": o.get("referenced_date"),
            }
            for o in observations
        ],
        indent=2,
        default=str,
    )

    prev_text = ""
    if previous_reflections:
        prev_refs = [
            {"id": r.get("id", ""), "content": r.get("content", "")[:500]}
            for r in previous_reflections[-10:]
        ]
        prev_text = json.dumps(prev_refs, indent=2, default=str)

    prompt = REFLECTOR_PROMPT.format(
        observations=obs_text,
        previous_reflections=prev_text,
    )

    msgs = [
        Message.system("You discover patterns and meaning from observations."),
        Message.user(prompt),
    ]
    response = await provider.chat(msgs)

    if response is None:
        return {"reflections": []}

    content = response.content if isinstance(response.content, str) else str(response.content or "")
    reflections = _parse_json_array(content)
    return {"reflections": reflections or []}
