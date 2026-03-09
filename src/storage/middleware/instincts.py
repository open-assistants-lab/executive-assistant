"""Instincts middleware for extracting and injecting learned behavioral patterns."""

import json
import logging
import threading
from datetime import UTC, datetime
from typing import Any, NotRequired

from langchain.agents.middleware import AgentMiddleware, AgentState, hook_config
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.runtime import Runtime

from src.app_logging import get_logger
from src.storage.instincts import get_instincts_store

logger = get_logger()

EXTRACTION_PROMPT = """You are a user pattern extraction system. Analyze the conversation and extract ALL behavioral patterns the user has expressed.

## DOMAINS (must use exactly these):

| Domain | What to extract | Examples |
|--------|-----------------|-----------|
| **personal** | Name, age, family, bio | "I'm John", "married with kids", "been coding for 10 years" |
| **work** | Role, company, team, seniority | "senior developer at Acme", "lead a team", "tech lead" |
| **location** | City, country, timezone | "in Tokyo", "PST timezone", "based in SF" |
| **interests** | Topics, hobbies, passions | "into AI", "love hiking", "interested in ML" |
| **skills** | Experience, expertise, tech stack | "10 years Python", "expert at React", "know Go" |
| **goals** | Objectives, targets, ambitions | "building a startup", "learning to code", "launching soon" |
| **constraints** | Limitations, requirements | "small budget", "tight deadline", "need it simple" |
| **communication** | Style preferences | "be concise", "use bullet points", "explain like I'm 5" |
| **tools** | Preferred tools, software | "use VS Code", "prefer PostgreSQL", "like Figma" |
| **languages** | Spoken/programming | "speak English", "code in Python", "like TypeScript" |
| **correction** | Corrections to AI | "no don't do X", "use Y instead", "wrong, try this" |
| **workflow** | Habits, processes | "always test first", "start with plan", "review before commit" |
| **lesson** | Things taught to AI | "validate input first", "check errors", "use type hints" |
| **dislikes** | Explicitly unwanted | "hate meetings", "no buzzwords", "avoid AI slop" |

Extract EVERYTHING you can from the conversation. Return JSON array:

```json
[
  {{"trigger": "when [situation]", "action": "what the user wants", "domain": "domain_name", "confidence": 0.0-1.0}},
  ...
]
```

- trigger: what triggers this pattern (e.g., "when I ask about code", "when writing Python")
- action: what the user wants/prefers
- domain: MUST be one of the 14 domains above
- confidence: how sure you are (0-1)

Only return valid JSON, no other text.

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
            "domain": {
                "type": "string",
                "enum": [
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
                ],
            },
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "required": ["trigger", "action", "domain", "confidence"],
    },
}


class InstinctsState(AgentState):
    """Custom state for tracking instincts."""

    extracted_instincts: NotRequired[list[dict[str, Any]]]


class InstinctsMiddleware(AgentMiddleware[InstinctsState]):
    """Middleware that extracts and injects learned behavioral patterns.

    Uses after_agent hook to extract patterns from user corrections/preferences,
    and before_agent hook to inject relevant instincts into context.
    """

    state_schema = InstinctsState
    tools = []

    def __init__(self, user_id: str | None = None):
        self.user_id = user_id or "default"
        self.instincts_store = get_instincts_store(self.user_id)
        self._model: Any = None

    def _get_model(self) -> Any | None:
        """Get the LLM model for extraction."""
        if self._model is None:
            try:
                from src.agents.manager import get_model

                self._model = get_model()
            except ImportError as e:
                logging.getLogger(__name__).warning(
                    f"Could not load model for instincts extraction: {e}"
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

    def _get_instincts_context(self) -> str:
        """Build the instincts context for injection, grouped by domain."""
        instincts = self.instincts_store.list_instincts(min_confidence=0.2, limit=30)

        if not instincts:
            return ""

        now = datetime.now(UTC)

        by_domain: dict[str, list[str]] = {}
        for instinct in instincts:
            domain = instinct.domain
            if domain not in by_domain:
                by_domain[domain] = []

            days_old = (now - instinct.updated_at).days
            if days_old < 7:
                recency = " (recent)"
            elif days_old > 90:
                recency = " (outdated)"
            else:
                recency = ""

            by_domain[domain].append(f"  - {instinct.trigger}: {instinct.action}{recency}")

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
        state: InstinctsState,
        runtime: Runtime,
    ) -> dict[str, Any] | None:
        """Inject learned instincts into context.

        Modifies the state messages in-place to add instincts context.
        Returns None as per LangChain middleware pattern - state modifications
        are applied directly to the messages in the state.
        """
        instincts_context = self._get_instincts_context()

        if not instincts_context:
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
                        updated_content = content + "\n\n" + instincts_context
                        if hasattr(msg, "content"):
                            msg.content = updated_content
                        current_messages[i] = SystemMessage(content=updated_content)
                    break

        logger.debug(
            "instincts.injected",
            {"context": instincts_context[:100], "user_id": self.user_id},
            user_id=self.user_id,
        )

        return None

    @hook_config()
    def after_agent(
        self,
        state: InstinctsState,
        runtime: Runtime,
    ) -> dict[str, Any] | None:
        """Extract behavioral patterns from conversation using LLM.

        This is a non-blocking extraction - patterns are analyzed
        asynchronously after the response is sent.
        """
        messages = state.get("messages", [])
        if not messages:
            return None

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

        return None

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

            for pattern in patterns:
                trigger = pattern.get("trigger", "")
                action = pattern.get("action", "")
                domain = pattern.get("domain", "preference")
                confidence = pattern.get("confidence", 0.5)

                if trigger and action:
                    self.instincts_store.add_instinct(
                        trigger=trigger,
                        action=action,
                        confidence=min(confidence, 0.9),
                        domain=domain,
                        source="auto-learned",
                    )

                    logger.info(
                        "instinct.extracted",
                        {
                            "trigger": trigger,
                            "action": action,
                            "domain": domain,
                            "confidence": confidence,
                        },
                        user_id=self.user_id,
                    )

        except Exception as e:
            logger.warning(
                "instinct.extraction_failed",
                {"error": str(e), "user_id": self.user_id},
                user_id=self.user_id,
            )

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


__all__ = ["InstinctsMiddleware", "InstinctsState"]
