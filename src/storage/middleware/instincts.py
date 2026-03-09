"""Instincts middleware for extracting and injecting learned behavioral patterns."""

import json
from datetime import UTC, datetime
from typing import Any, NotRequired

from langchain.agents.middleware import AgentMiddleware, AgentState, hook_config
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.runtime import Runtime

from src.app_logging import get_logger
from src.storage.instincts import get_instincts_store

logger = get_logger()

EXTRACTION_PROMPT = """You are a pattern extraction system. Analyze the conversation below and extract any behavioral patterns, preferences, or corrections that the user has expressed.

Look for:
1. **Corrections** - When user corrects the AI (e.g., "no, don't do X", "use Y instead")
2. **Preferences** - User preferences (e.g., "I prefer concise answers", "use markdown")
3. **Workflow habits** - How the user likes to work (e.g., "always start with a plan")
4. **Lessons learned** - Things the user taught the AI
5. **Dislikes** - Things user explicitly doesn't want

For each pattern found, return a JSON array with this structure:
[
  {
    "trigger": "when [situation]",
    "action": "what to do",
    "domain": "preference|correction|workflow|lesson|dislike",
    "confidence": 0.0-1.0
  }
]

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
                "enum": ["preference", "correction", "workflow", "lesson", "dislike"],
            },
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "required": ["trigger", "action", "domain"],
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
        self._model = None

    def _get_model(self):
        """Get the LLM model for extraction."""
        if self._model is None:
            from src.agents.manager import get_model

            self._model = get_model()
        return self._model

    def _get_instincts_context(self) -> str:
        """Build the instincts context for injection."""
        instincts = self.instincts_store.list_instincts(min_confidence=0.3, limit=20)

        if not instincts:
            return ""

        parts = ["## Learned User Preferences"]
        for instinct in instincts:
            recency = ""
            days_old = (datetime.now(UTC) - instinct.updated_at).days
            if days_old < 7:
                recency = " (recent)"
            elif days_old > 90:
                recency = " (outdated)"

            parts.append(f"- {instinct.trigger}: {instinct.action}{recency}")

        return "\n".join(parts)

    @hook_config()
    def before_agent(
        self,
        state: InstinctsState,
        runtime: Runtime,
    ) -> dict[str, Any] | None:
        """Inject learned instincts into context."""
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
                    content = msg.content if hasattr(msg, "content") else str(msg)
                    if "## Learned User Preferences" not in content:
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
        response: Any,
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

        self._extract_with_llm(recent_messages)

        return None

    def _extract_with_llm(self, messages: list[str]) -> None:
        """Extract patterns using LLM."""
        try:
            conversation = "\n\n".join(messages)
            prompt = EXTRACTION_PROMPT.format(conversation=conversation)

            model = self._get_model()

            response = model.invoke([HumanMessage(content=prompt)])

            content = response.content if hasattr(response, "content") else str(response)

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
            return json.loads(content)
        except json.JSONDecodeError:
            start = content.find("[")
            end = content.rfind("]") + 1
            if start >= 0 and end > start:
                try:
                    return json.loads(content[start:end])
                except json.JSONDecodeError:
                    pass

        return []
