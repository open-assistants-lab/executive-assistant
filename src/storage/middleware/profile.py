"""Profile middleware for extracting and injecting user profile."""

from typing import Any

from langchain.agents.middleware import AgentMiddleware, AgentState, hook_config
from langgraph.runtime import Runtime

from src.app_logging import get_logger
from src.storage.profile import get_profile_store

logger = get_logger()


class ProfileState(AgentState):
    """Custom state for tracking profile."""


class ProfileMiddleware(AgentMiddleware[ProfileState]):
    """Middleware that extracts and injects user profile into context.

    Uses before_agent hook to inject user profile into context,
    and after_agent hook to extract new profile information.
    """

    state_schema = ProfileState
    tools = []

    def __init__(self, user_id: str | None = None):
        self.user_id = user_id or "default"
        self.profile_store = get_profile_store(self.user_id)

    def _get_profile_context(self) -> str:
        """Build the profile context for injection."""
        profile = self.profile_store.get_profile()

        if not profile:
            return ""

        parts = ["## User Information"]
        if profile.name:
            parts.append(f"Name: {profile.name}")
        if profile.role:
            parts.append(f"Role: {profile.role}")
        if profile.company:
            parts.append(f"Company: {profile.company}")
        if profile.city:
            parts.append(f"Location: {profile.city}")
        if profile.bio:
            parts.append(f"Bio: {profile.bio}")
        if profile.preferences:
            parts.append(f"Preferences: {profile.preferences}")
        if profile.interests:
            parts.append(f"Interests: {profile.interests}")

        if len(parts) == 1:
            return ""

        return "\n".join(parts)

    @hook_config()
    def before_agent(
        self,
        state: ProfileState,
        runtime: Runtime,
    ) -> dict[str, Any] | None:
        """Inject user profile into context."""
        profile_context = self._get_profile_context()

        if not profile_context:
            return None

        current_messages = state.get("messages", [])

        for i, msg in enumerate(current_messages):
            if hasattr(msg, "type") and msg.type == "system":
                content = msg.content if hasattr(msg, "content") else str(msg)
                if "## User Information" not in content:
                    updated_content = content + "\n\n" + profile_context
                    if hasattr(msg, "content"):
                        msg.content = updated_content
                    current_messages[i] = type(msg)(content=updated_content)
                break

        logger.debug(
            "profile.injected",
            {"user_id": self.user_id},
            user_id=self.user_id,
        )

        return None

    @hook_config()
    def after_agent(
        self,
        state: ProfileState,
        runtime: Runtime,
        response: Any,
    ) -> dict[str, Any] | None:
        """Extract profile information from conversation.

        This is a simplified version - in production, this would
        use an LLM to analyze and extract profile information.
        """
        messages = state.get("messages", [])
        if not messages:
            return None

        recent = []
        for msg in messages[-4:]:
            if hasattr(msg, "content"):
                recent.append(msg.content)

        if len(recent) < 2:
            return None

        self._extract_profile(recent)

        return None

    def _extract_profile(self, messages: list[str]) -> None:
        """Extract profile information from recent messages."""
        full_text = " ".join(messages)

        name_indicators = ["my name is", "i am", "i'm"]
        for indicator in name_indicators:
            if indicator in full_text.lower():
                idx = full_text.lower().find(indicator)
                potential = full_text[idx : idx + 50].split(".")[0].strip()
                if len(potential) > 3 and len(potential) < 50:
                    name = potential.replace(indicator, "").strip().title()
                    if name:
                        self.profile_store.update_field(
                            "name", name, confidence=0.7, source="extracted"
                        )
                        break

        role_keywords = {
            "developer": ["developer", "engineer", "programmer", "coder"],
            "manager": ["manager", "lead", "director", "head of"],
            "designer": ["designer", "ui", "ux", "artist"],
            "writer": ["writer", "author", "blogger", "content"],
        }

        for role, keywords in role_keywords.items():
            for keyword in keywords:
                if keyword in full_text.lower():
                    self.profile_store.update_field(
                        "role", role, confidence=0.6, source="extracted"
                    )
                    break

        logger.info(
            "profile.extracted",
            {"user_id": self.user_id},
            user_id=self.user_id,
        )
