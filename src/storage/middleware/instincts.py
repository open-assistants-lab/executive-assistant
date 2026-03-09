"""Instincts middleware for extracting and injecting learned behavioral patterns."""

from datetime import datetime
from typing import Any, NotRequired

from langchain.agents.middleware import AgentMiddleware, AgentState, hook_config
from langchain_core.messages import SystemMessage
from langgraph.runtime import Runtime

from src.app_logging import get_logger
from src.storage.instincts import get_instincts_store

logger = get_logger()


class InstinctsState(AgentState):
    """Custom state for tracking instincts."""

    extracted_instincts: NotRequired[list[dict[str, Any]]]


class InstinctsMiddleware(AgentMiddleware[InstinctsState]):
    """Middleware that extracts and injects learned behavioral patterns.

    Uses after_agent hook to extract patterns from user corrections,
    and before_agent hook to inject relevant instincts into context.
    """

    state_schema = InstinctsState
    tools = []

    def __init__(self, user_id: str | None = None):
        self.user_id = user_id or "default"
        self.instincts_store = get_instincts_store(self.user_id)

    def _get_instincts_context(self) -> str:
        """Build the instincts context for injection."""
        instincts = self.instincts_store.list_instincts(min_confidence=0.3, limit=20)

        if not instincts:
            return ""

        parts = ["## Learned User Preferences"]
        for instinct in instincts:
            recency = ""
            days_old = (datetime.now() - instinct.updated_at).days
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
        """Extract behavioral patterns from conversation.

        This is a non-blocking extraction - patterns are analyzed
        asynchronously after the response is sent.
        """
        messages = state.get("messages", [])
        if not messages:
            return None

        recent_messages = []
        for msg in messages[-6:]:
            if hasattr(msg, "content"):
                recent_messages.append(
                    {
                        "role": getattr(msg, "type", "unknown"),
                        "content": msg.content,
                    }
                )

        if len(recent_messages) < 2:
            return None

        self._extract_patterns(recent_messages)

        return None

    def _extract_patterns(self, messages: list[dict[str, Any]]) -> None:
        """Extract behavioral patterns from messages.

        This is a simplified version - in production, this would
        use an LLM to analyze patterns.
        """
        correction_patterns = [
            ("no, don't", "correction"),
            ("don't do that", "correction"),
            ("instead, use", "correction"),
            ("wrong, try", "correction"),
            ("not like that", "correction"),
        ]

        user_msgs = [m for m in messages if m.get("role") == "user"]
        assistant_msgs = [m for m in messages if m.get("role") == "ai"]

        if not user_msgs or not assistant_msgs:
            return

        last_user = user_msgs[-1].get("content", "") if user_msgs else ""

        for pattern, domain in correction_patterns:
            if pattern.lower() in last_user.lower():
                trigger = "when user corrects me"
                action = last_user.replace(pattern, "").strip()[:100]

                if len(action) > 10:
                    self.instincts_store.add_instinct(
                        trigger=trigger,
                        action=action,
                        confidence=0.5,
                        domain=domain,
                        source="correction",
                    )

                    logger.info(
                        "instinct.extracted",
                        {"trigger": trigger, "action": action, "domain": domain},
                        user_id=self.user_id,
                    )
                break
