"""Structured summary extractor for updating conversation summaries.

Extracts facts, decisions, tasks, and open questions from messages
and updates the structured summary following the schema.
"""

import hashlib
import json
from datetime import datetime
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage

from cassey.agent.topic_classifier import (
    TopicClassifier,
    StructuredSummaryBuilder,
    should_create_new_topic,
)


def get_stable_message_id(msg: BaseMessage) -> str:
    """
    Generate a stable message ID from message content.

    Uses SHA-256 hash of (role + content + timestamp) to create
    a persistent ID that survives across summarization cycles.

    Args:
        msg: The message to generate ID for

    Returns:
        Stable message ID (16 hex characters)
    """
    content = msg.content or ""
    role = "human" if isinstance(msg, HumanMessage) else "ai"

    # Include timestamp if available for uniqueness
    timestamp = getattr(msg, "timestamp", None)
    timestamp_str = str(timestamp) if timestamp else ""

    # Create stable hash
    hash_input = f"{role}:{content}:{timestamp_str}"
    return "msg_" + hashlib.sha256(hash_input.encode()).hexdigest()[:16]


async def extract_conversation_elements(
    messages: list[BaseMessage],
    model: BaseChatModel,
) -> dict[str, Any]:
    """
    Extract conversation elements (facts, decisions, tasks, questions) from messages.

    Uses LLM to analyze the conversation and extract structured information.
    Each extracted item is bound to specific source message indices.

    Args:
        messages: List of conversation messages (Human/AI only)
        model: LLM for extraction

    Returns:
        Dict with extracted elements:
        {
            "facts": [{"text": str, "message_ids": [str]}],
            "decisions": [{"text": str, "message_ids": [str]}],
            "tasks": [{"text": str, "message_ids": [str]}],
            "open_questions": [{"text": str, "message_ids": [str]}],
            "constraints": [{"text": str, "message_ids": [str]}],
        }
    """
    # Build conversation text for analysis with numbered indices
    conversation_text = ""
    message_map = {}  # Track index to stable message_id mapping

    for i, msg in enumerate(messages):
        if isinstance(msg, (HumanMessage, AIMessage)):
            role = "User" if isinstance(msg, HumanMessage) else "Assistant"
            content = msg.content or ""
            # Number messages for LLM reference: [1] User: ...
            conversation_text += f"[{i}] {role}: {content}\n\n"
            # Generate stable message ID
            message_map[i] = get_stable_message_id(msg)

    if not conversation_text:
        return {
            "facts": [],
            "decisions": [],
            "tasks": [],
            "open_questions": [],
            "constraints": [],
        }

    extract_prompt = """Analyze this conversation and extract key elements.

IMPORTANT: For each item, specify which message(s) it comes from using the [number] references.

Respond ONLY with valid JSON in this exact format:
{
    "facts": [{"text": "statement1", "sources": [0, 1]}],
    "decisions": [{"text": "decision1", "sources": [2]}],
    "tasks": [{"text": "task1", "sources": [0]}],
    "open_questions": [{"text": "question1", "sources": [1]}],
    "constraints": [{"text": "constraint1", "sources": [0, 2]}]
}

Rules:
- facts: Statements of fact or information shared
- decisions: Clear decisions made or conclusions reached
- tasks: Action items to be done (only if user explicitly accepted)
- open_questions: Unresolved questions that need answers
- constraints: Limitations or restrictions mentioned
- sources: Array of message indices [0, 1, 2, etc] that support this item (1-3 relevant messages)

Keep each item concise (1 sentence). Extract only important items.

Conversation:
{conversation}"""

    try:
        response = await model.ainvoke([
            SystemMessage(content="You are a conversation analyzer. Respond only with valid JSON."),
            HumanMessage(content=extract_prompt.format(conversation=conversation_text[:8000]))  # Limit length
        ])

        result = json.loads(response.content.strip())

        # Map message indices to stable IDs for each extracted item
        def map_sources(items: list) -> list[dict[str, Any]]:
            mapped = []
            for item in (items or []):
                text = item.get("text", "") if isinstance(item, dict) else item
                source_indices = item.get("sources", []) if isinstance(item, dict) else []

                # Map indices to stable message IDs
                message_ids = []
                for idx in source_indices:
                    if idx in message_map:
                        message_ids.append(message_map[idx])

                # If no sources specified, use the last 2 messages as fallback
                if not message_ids and message_map:
                    last_indices = sorted(message_map.keys())[-2:]
                    message_ids = [message_map[i] for i in last_indices]

                mapped.append({"text": text, "message_ids": message_ids})
            return mapped

        return {
            "facts": map_sources(result.get("facts", [])),
            "decisions": map_sources(result.get("decisions", [])),
            "tasks": map_sources(result.get("tasks", [])),
            "open_questions": map_sources(result.get("open_questions", [])),
            "constraints": map_sources(result.get("constraints", [])),
        }

    except (json.JSONDecodeError, Exception):
        # Return empty on error
        return {
            "facts": [],
            "decisions": [],
            "tasks": [],
            "open_questions": [],
            "constraints": [],
        }


async def update_structured_summary(
    current_summary: dict[str, Any] | None,
    messages: list[BaseMessage],
    model: BaseChatModel,
    thread_id: str,
) -> dict[str, Any]:
    """
    Update the structured summary with new messages.

    Follows the schema update rules:
    1. Classify topic for latest message
    2. Set active_request from latest user message
    3. Extract facts/decisions/tasks/questions
    4. Mark old topics inactive if new topic dominates

    Args:
        current_summary: Existing structured summary or None
        messages: All messages in the conversation
        model: LLM for extraction/classification
        thread_id: Thread identifier for context

    Returns:
        Updated structured summary dict
    """
    # Start with empty or existing summary
    summary = current_summary or StructuredSummaryBuilder.create_empty()

    # Get only Human and AI messages
    conversation_messages = [m for m in messages if isinstance(m, (HumanMessage, AIMessage))]

    if not conversation_messages:
        return summary

    # Get latest user message with stable ID
    latest_human = None
    latest_message_id = None
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            latest_human = msg
            latest_message_id = get_stable_message_id(msg)
            break

    if not latest_human:
        return summary

    query = latest_human.content or ""

    # Classify intent for the new query
    intent = TopicClassifier.classify_intent(query)

    # Check if we should create a new topic (domain changed or low similarity)
    current_topic_id = get_topic_id_from_summary(summary)
    new_topic_created = False

    # Determine topic_id: reuse current if same topic, generate new if different
    if should_create_new_topic(query, current_topic_id):
        # Create new topic ID
        topic_id = TopicClassifier.generate_topic_id(query)
        new_topic_created = True

        # Mark old topic inactive if it exists and has no unresolved tasks
        if current_topic_id:
            old_topic = None
            for t in summary.get("topics", []):
                if t.get("topic_id") == current_topic_id:
                    old_topic = t
                    break

            if old_topic:
                # Only mark inactive if no unresolved tasks
                unresolved_tasks = [
                    t for t in old_topic.get("tasks", [])
                    if not t.get("completed", False)
                ]
                if not unresolved_tasks:
                    StructuredSummaryBuilder.mark_topic_inactive(
                        summary,
                        current_topic_id,
                        f"superseded_by:{topic_id}"
                    )
    else:
        # Reuse current topic ID (same topic continues)
        topic_id = current_topic_id or TopicClassifier.generate_topic_id(query)

    # Set active request (always from latest user message)
    StructuredSummaryBuilder.set_active_request(
        summary,
        query,
        topic_id,
        [latest_message_id] if latest_message_id else []
    )

    # Extract conversation elements from recent messages
    # Only analyze messages since last summary update
    recent_messages = conversation_messages[-10:]  # Last 10 messages max
    elements = await extract_conversation_elements(recent_messages, model)

    # Add extracted elements to the active topic
    topic = StructuredSummaryBuilder.get_or_create_topic(summary, topic_id)

    # Add facts (with source tracking)
    for fact in elements.get("facts", []):
        # Avoid duplicates by text
        if not any(f.get("text") == fact.get("text") for f in topic["facts"]):
            topic["facts"].append(fact)
            # Track sources
            topic["sources"].extend(fact.get("message_ids", []))

    # Add decisions (with source tracking)
    for decision in elements.get("decisions", []):
        if not any(d.get("text") == decision.get("text") for d in topic["decisions"]):
            topic["decisions"].append(decision)
            topic["sources"].extend(decision.get("message_ids", []))

    # Add tasks (with source tracking)
    for task in elements.get("tasks", []):
        if not any(t.get("text") == task.get("text") for t in topic["tasks"]):
            topic["tasks"].append(task)
            topic["sources"].extend(task.get("message_ids", []))

    # Add open questions (with source tracking)
    for question in elements.get("open_questions", []):
        if len(topic["open_questions"]) < 3:
            if not any(q.get("text") == question.get("text") for q in topic["open_questions"]):
                topic["open_questions"].append(question)
                topic["sources"].extend(question.get("message_ids", []))

    # Add constraints (with source tracking)
    for constraint in elements.get("constraints", []):
        if not any(c.get("text") == constraint.get("text") for c in topic["constraints"]):
            topic["constraints"].append(constraint)
            topic["sources"].extend(constraint.get("message_ids", []))

    # Dedupe sources
    if topic["sources"]:
        topic["sources"] = list(set(topic["sources"]))

    # Update timestamp and intent
    topic["last_updated"] = datetime.utcnow().isoformat() + "Z"
    topic["intent"] = intent  # Track intent for routing

    return summary


def get_topic_id_from_summary(
    structured_summary: dict[str, Any] | None,
) -> str | None:
    """Extract the active topic ID from a structured summary."""
    if not structured_summary:
        return None

    active_request = structured_summary.get("active_request", {})
    if isinstance(active_request, dict):
        return active_request.get("topic_id")

    return None


def should_use_kb_first(
    structured_summary: dict[str, Any] | None,
    query: str,
) -> bool:
    """
    Determine if KB should be consulted before conversation summary.

    Rules:
    - If intent is "factual" → KB first
    - If intent is "conversational" → conversation summary first
    - If intent is "hybrid" → both

    Args:
        structured_summary: The structured summary
        query: The user's query

    Returns:
        True if KB should be checked first
    """
    intent = TopicClassifier.classify_intent(query)
    return intent == "factual" or intent == "hybrid"
