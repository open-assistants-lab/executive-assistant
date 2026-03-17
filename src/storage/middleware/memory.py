"""Memory middleware for extracting and injecting learned behavioral patterns.

Features:
- Selective extraction: only extract when user explicitly corrects, expresses preference, or provides new info
- Two-layer memory: working (always injected) vs long-term (retrievable on demand)
- Memory types: preference, fact, workflow, correction
- Source tracking: explicit (user-set) vs learned (auto-extracted)
"""

import json
import logging
import threading
from datetime import UTC, datetime
from typing import Any, NotRequired

from langchain.agents.middleware import AgentMiddleware, AgentState, hook_config
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.runtime import Runtime

from src.app_logging import get_logger
from src.storage.memory import (
    DEFAULT_CONFIDENCE,
    MAX_CONFIDENCE,
    MEMORY_TYPE_CORRECTION,
    MEMORY_TYPE_FACT,
    MEMORY_TYPE_PREFERENCE,
    MEMORY_TYPE_WORKFLOW,
    SOURCE_EXPLICIT,
    SOURCE_LEARNED,
    get_memory_store,
)

logger = get_logger()

# Detection keywords for selective extraction
CORRECTION_KEYWORDS = [
    "no ",
    "don't ",
    "don't do",
    "not like",
    "wrong",
    "actually",
    "instead",
    "please don't",
    "never",
    "avoid",
    "not that",
    "i meant",
    "not what",
    "that's not",
    "stop",
    "dislike",
]

PREFERENCE_KEYWORDS = [
    "i prefer",
    "i like",
    "i want",
    "i love",
    "i hate",
    "i don't like",
    "always",
    "never",
    "usually",
    "i'm used to",
    "i'm comfortable with",
    "my favorite",
    "i'm a fan of",
    "better with",
    "instead of",
]

CORRECTION_KEYWORDS = [
    "no ",
    "don't ",
    "don't do",
    "not like",
    "wrong",
    "actually",
    "instead",
    "please don't",
    "never",
    "avoid",
    "not that",
    "i meant",
    "not what",
    "that's not",
    "stop",
    "dislike",
    "correction",
    "update:",
    "actually no",
    "wait ",
    "hold on",
]

NEW_INFO_KEYWORDS = [
    "i am ",
    "i'm ",
    "i was",
    "my name is",
    "i live in",
    "i work at",
    "i'm from",
    "i've been",
    "i do",
    "i'm a",
    "i'm an",
    "i speak",
    "speak ",
    "speaks ",
]


EXTRACTION_PROMPT = """You are a user pattern extraction system. Analyze the conversation and extract ONLY meaningful behavioral patterns.

## EXTRACTION RULES:
1. Only extract when user EXPLICITLY expresses a preference, makes a correction, or provides NEW personal information
2. Do NOT extract from normal conversational responses
3. Each memory must be actionable - something the AI should remember and act on

## MEMORY TYPES (pick one):

| Type | When to use |
|------|-------------|
| **preference** | User expresses what they want/prefer (likes, dislikes, wants) |
| **fact** | Factual info about user (name, location, job, etc) |
| **workflow** | User's working patterns or habits |
| **correction** | User corrects the AI ("no, not like that") |

## DOMAINS (for categorization):

| Domain | What to extract |
|--------|-----------------|
| personal | Name, age, family, bio |
| work | Role, company, team, seniority |
| location | City, country, timezone |
| interests | Topics, hobbies, passions |
| skills | Experience, expertise, tech stack |
| goals | Objectives, targets, ambitions |
| constraints | Limitations, requirements |
| communication | Style preferences (concise, bullet points, etc) |
| tools | Preferred tools, software |
| languages | Spoken/programming languages |
| correction | Corrections to AI responses |
| workflow | Habits, processes |
| lesson | Things taught to AI |
| dislikes | Explicitly unwanted |

## OUTPUT (JSON array):

```json
[
  {{"trigger": "when [situation]", "action": "what the user wants", "domain": "domain_name", "memory_type": "preference|fact|workflow|correction", "confidence": 0.0-1.0}}
]
```

Only return valid JSON with patterns that are WORTH remembering. Less is more.

Conversation:
{conversation}

Extracted patterns (JSON):"""

EXTRACTION_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "trigger": {"type": "string"},
            "action": {"type": "string"},
            "domain": {"type": "string"},
            "memory_type": {
                "type": "string",
                "enum": [
                    MEMORY_TYPE_PREFERENCE,
                    MEMORY_TYPE_FACT,
                    MEMORY_TYPE_WORKFLOW,
                    MEMORY_TYPE_CORRECTION,
                ],
            },
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "required": ["trigger", "action", "domain", "memory_type", "confidence"],
    },
}


class MemoryState(AgentState):
    """Custom state for tracking memory operations."""

    extracted_memories: NotRequired[list[dict[str, Any]]]
    last_extraction_time: NotRequired[datetime]


class MemoryMiddleware(AgentMiddleware[MemoryState]):
    """Middleware that extracts and injects learned memories.

    Features:
    - Selective extraction: only when meaningful patterns detected
    - Two-layer memory: working (high confidence) + long-term (all)
    - Memory type classification
    - Source tracking (explicit vs learned)
    """

    state_schema = MemoryState
    tools = []

    # Class-level extraction tracking
    _extraction_count: dict[str, int] = {}

    def __init__(self, user_id: str | None = None):
        self.user_id = user_id or "default"
        self.memory_store = get_memory_store(self.user_id)
        self._model: Any = None
        self._last_conversation_had_extraction = False

    def _get_model(self) -> Any | None:
        """Get the LLM model for extraction."""
        if self._model is None:
            try:
                from src.agents.manager import get_model

                self._model = get_model()
            except ImportError as e:
                logging.getLogger(__name__).warning(
                    f"Could not load model for memory extraction: {e}"
                )
                return None
        return self._model

    def _get_message_content(self, msg: Any) -> str:
        """Extract string content from a message."""
        content = getattr(msg, "content", "")
        if isinstance(content, str):
            return content
        elif isinstance(content, list):
            return " ".join(
                c.get("text", "") if isinstance(c, dict) else getattr(c, "text", "")
                for c in content
            )
        return str(content)

    def _should_extract(self, messages: list[Any]) -> bool:
        """Determine if extraction should happen based on conversation content.

        Only extract when:
        - User explicitly corrects the AI
        - User expresses clear preferences
        - User provides new personal information
        """
        if not messages:
            return False

        conversation_text = ""
        for msg in messages[-6:]:
            role = getattr(msg, "type", "unknown")
            content = self._get_message_content(msg)
            conversation_text += f"{role}: {content}\n"

        conversation_lower = conversation_text.lower()

        # Check for correction keywords
        correction_count = sum(1 for kw in CORRECTION_KEYWORDS if kw in conversation_lower)

        # Check for preference keywords
        preference_count = sum(1 for kw in PREFERENCE_KEYWORDS if kw in conversation_lower)

        # Check for new info keywords (but only from user)
        user_messages = [m for m in messages[-4:] if getattr(m, "type", "") == "human"]
        user_text = " ".join(self._get_message_content(m) for m in user_messages).lower()
        new_info_count = sum(1 for kw in NEW_INFO_KEYWORDS if kw in user_text)

        # Only extract if there's meaningful content
        has_meaningful_content = (
            correction_count >= 1 or preference_count >= 2 or new_info_count >= 1
        )

        return has_meaningful_content

    def _get_working_memory_context(self) -> str:
        """Build working memory context - always injected into context."""
        memories = self.memory_store.list_working_memories(min_confidence=0.3, limit=20)

        if not memories:
            return ""

        now = datetime.now(UTC)

        by_domain: dict[str, list[str]] = {}
        for memory in memories:
            domain = memory.domain
            if domain not in by_domain:
                by_domain[domain] = []

            days_old = (now - memory.updated_at).days
            if days_old < 7:
                recency = ""
            elif days_old > 90:
                recency = " (outdated)"
            else:
                recency = f" ({days_old}d ago)"

            source_marker = "★" if memory.source == SOURCE_EXPLICIT else ""
            by_domain[domain].append(
                f"  - {memory.trigger}: {memory.action}{recency}{source_marker}"
            )

        domain_order = [
            "personal",
            "work",
            "location",
            "interests",
            "skills",
            "goals",
            "constraints",
            "communication",
            "tools",
            "languages",
            "correction",
            "workflow",
            "lesson",
            "dislikes",
        ]

        parts = ["## User Profile & Preferences"]

        for domain in domain_order:
            if domain in by_domain:
                domain_display = domain.capitalize()
                parts.append(f"\n### {domain_display}")
                parts.extend(by_domain[domain])

        return "\n".join(parts)

    @hook_config()
    def before_agent(
        self,
        state: MemoryState,
        runtime: Runtime,
    ) -> dict[str, Any] | None:
        """Inject learned memories into context.

        Uses working memory (high confidence, recent) for context injection.
        """
        memory_context = self._get_working_memory_context()

        if not memory_context:
            return None

        current_messages = state.get("messages", [])

        system_found = False
        for msg in current_messages:
            if hasattr(msg, "type") and msg.type == "system":
                system_found = True
                break

        if system_found:
            for i, msg in enumerate(current_messages):
                if hasattr(msg, "type") and msg.type == "system":
                    content = self._get_message_content(msg)
                    if "## User Profile & Preferences" not in content:
                        updated_content = content + "\n\n" + memory_context
                        if hasattr(msg, "content"):
                            msg.content = updated_content
                        current_messages[i] = SystemMessage(content=updated_content)
                    break

        logger.debug(
            "memory.injected",
            {"context": memory_context[:100], "user_id": self.user_id},
            user_id=self.user_id,
        )

        return None

    @hook_config()
    def after_agent(
        self,
        state: MemoryState,
        runtime: Runtime,
    ) -> dict[str, Any] | None:
        """Extract behavioral patterns from conversation - SELECTIVELY.

        Only extracts when conversation contains:
        - User corrections
        - Explicit preferences
        - New personal information
        """
        messages = state.get("messages", [])
        if not messages:
            return None

        if not self._should_extract(messages):
            self._last_conversation_had_extraction = False
            return None

        # Track that this conversation had extraction
        self._last_conversation_had_extraction = True

        recent_messages = []
        for msg in messages[-8:]:
            role = getattr(msg, "type", "unknown")
            content = getattr(msg, "content", "")
            if content:
                recent_messages.append(f"{role}: {content[:500]}")

        if len(recent_messages) < 2:
            return None

        threading.Thread(
            target=self._extract_with_llm,
            args=(recent_messages,),
            daemon=True,
        ).start()

        # Check if should trigger consolidation (every N messages)
        self._check_and_trigger_consolidation()

        return None

    def _check_and_trigger_consolidation(self) -> None:
        """Trigger consolidation periodically based on message count."""
        try:
            from src.config import get_settings
            from src.storage.consolidation import on_conversation_end

            settings = get_settings()
            threshold = settings.memory.consolidate_after_messages

            if threshold <= 0:
                return

            if not hasattr(self, "_message_count"):
                self._message_count = 0
            self._message_count += 1

            if self._message_count >= threshold and self._message_count % threshold == 0:
                on_conversation_end(self.user_id, threshold)
        except Exception:
            pass

    def _extract_with_llm(self, messages: list[str]) -> None:
        """Extract patterns using LLM."""
        try:
            model = self._get_model()
            if model is None:
                return

            conversation = "\n\n".join(messages)
            prompt = EXTRACTION_PROMPT.format(conversation=conversation)

            response = model.invoke([HumanMessage(content=prompt)])

            content = response.content if hasattr(response, "content") else str(response)
            if not isinstance(content, str):
                content = str(content)

            patterns = self._parse_json_response(content)

            # Detect if this conversation contains a correction
            is_correction = self._detect_correction_in_messages(messages)

            for pattern in patterns:
                trigger = pattern.get("trigger", "")
                action = pattern.get("action", "")
                domain = pattern.get("domain", "preference")
                memory_type = pattern.get("memory_type", MEMORY_TYPE_PREFERENCE)
                confidence = pattern.get("confidence", DEFAULT_CONFIDENCE)

                if not trigger or not action:
                    continue

                # Check if similar memory exists (for corrections or updates)
                existing = self.memory_store.search_hybrid(trigger, limit=3)
                similar = [m for m in existing if m.domain == domain and not m.is_superseded]

                if is_correction and similar:
                    # Update existing memory instead of creating new
                    old_mem = similar[0]
                    new_mem = self.memory_store.update_memory(
                        old_mem.id,
                        new_trigger=trigger,
                        new_action=action,
                        new_domain=domain,
                    )
                    if new_mem:
                        self.memory_store.supersede_memory(old_mem.id, new_mem.id)
                        logger.info(
                            "memory.corrected",
                            {
                                "old_trigger": old_mem.trigger,
                                "new_trigger": trigger,
                                "old_action": old_mem.action,
                                "new_action": action,
                            },
                            user_id=self.user_id,
                        )
                else:
                    # Create new memory (normal case)
                    self.memory_store.add_memory(
                        trigger=trigger,
                        action=action,
                        confidence=min(confidence, MAX_CONFIDENCE),
                        domain=domain,
                        source=SOURCE_LEARNED,
                        memory_type=memory_type,
                    )

                    logger.info(
                        "memory.extracted",
                        {
                            "trigger": trigger,
                            "action": action,
                            "domain": domain,
                            "memory_type": memory_type,
                            "confidence": confidence,
                        },
                        user_id=self.user_id,
                    )

        except Exception as e:
            logger.warning(
                "memory.extraction_failed",
                {"error": str(e), "user_id": self.user_id},
                user_id=self.user_id,
            )

    def _detect_correction_in_messages(self, messages: list[str]) -> bool:
        """Detect if conversation contains user corrections."""
        conversation_text = " ".join(m[-500:] for m in messages if len(m) > 10).lower()
        return any(kw in conversation_text for kw in CORRECTION_KEYWORDS)

    def _parse_json_response(self, content: str) -> list[dict[str, Any]]:
        """Parse JSON from LLM response."""
        content = content.strip()

        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]

        content = content.strip()

        try:
            data = json.loads(content)
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            start = content.find("[")
            end = content.rfind("]") + 1
            if start >= 0 and end > start:
                try:
                    data = json.loads(content[start:end])
                    if isinstance(data, list):
                        return data
                except json.JSONDecodeError:
                    pass

        return []

    def retrieve_longterm_memories(self, query: str, limit: int = 10) -> list:
        """Retrieve relevant long-term memories for a query."""
        return self.memory_store.search_hybrid(query, limit=limit)

    def trigger_consolidation(self) -> None:
        """Trigger background consolidation manually."""
        try:
            from src.storage.consolidation import trigger_consolidation

            trigger_consolidation(self.user_id)
        except Exception:
            pass  # Silently fail if consolidation not available


__all__ = ["MemoryMiddleware", "MemoryState"]
