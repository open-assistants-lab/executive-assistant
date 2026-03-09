"""Profile middleware for extracting and injecting user profile."""

import json
from typing import Any

from langchain.agents.middleware import AgentMiddleware, AgentState, hook_config
from langgraph.runtime import Runtime

from src.app_logging import get_logger
from src.storage.profile import get_profile_store

logger = get_logger()

EXTRACTION_PROMPT = """You are a user profile extraction system. Analyze the conversation below and extract information about the user.

Extract these types of information:
1. **Basic info** - name, role, company, city/location
2. **Communication preferences** - how they want to be addressed, detail level, tone
3. **Interests** - topics they care about
4. **Background** - experience level, industry, skills
5. **Explicit statements** - anything they explicitly told you about themselves

For each piece of information found, return a JSON object with these exact keys (use null if not found):
{{
  "name": "John" (if mentioned),
  "role": "developer" (if mentioned),
  "company": "Acme Inc" (if mentioned),
  "city": "Tokyo" (if mentioned),
  "bio": "experienced developer focused on AI" (if mentioned),
  "interests": ["Python", "machine learning"] (extract 2-5 topics),
  "preferences": {{"communication_style": "concise", "format": "markdown"}} (how they like to communicate),
  "background": {{"years_exp": 10, "industry": "tech"}} (any background info)
}}

Only return valid JSON with these exact keys (use null if not found), no other text.

Conversation:
{conversation}

Profile (JSON):"""


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
        self._model = None

    def _get_model(self):
        """Get the LLM model for extraction."""
        if self._model is None:
            from src.agents.manager import get_model

            self._model = get_model()
        return self._model

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

        if profile.interests:
            parts.append(f"Interests: {profile.interests}")

        if profile.preferences:
            parts.append(f"Preferences: {profile.preferences}")

        if profile.background:
            parts.append(f"Background: {profile.background}")

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
        """Extract profile information from conversation using LLM.

        This is a non-blocking extraction - profile info is analyzed
        asynchronously after the response is sent.
        """
        messages = state.get("messages", [])
        if not messages:
            return None

        recent = []
        for msg in messages[-8:]:
            role = getattr(msg, "type", "unknown")
            content = getattr(msg, "content", "")
            if content:
                recent.append(f"{role}: {content[:600]}")

        if len(recent) < 2:
            return None

        self._extract_with_llm(recent)

        return None

    def _extract_with_llm(self, messages: list[str]) -> None:
        """Extract profile information using LLM."""
        try:
            conversation = "\n\n".join(messages)
            prompt = EXTRACTION_PROMPT.format(conversation=conversation)

            model = self._get_model()

            response = model.invoke([{"type": "human", "content": prompt}])

            content = response.content if hasattr(response, "content") else str(response)

            profile_data = self._parse_json_response(content)

            if not profile_data:
                return

            updates_made = False

            if profile_data.get("name"):
                self.profile_store.update_field(
                    "name",
                    profile_data["name"],
                    confidence=0.7,
                    source="extracted",
                )
                updates_made = True

            if profile_data.get("role"):
                self.profile_store.update_field(
                    "role",
                    profile_data["role"],
                    confidence=0.6,
                    source="extracted",
                )
                updates_made = True

            if profile_data.get("company"):
                self.profile_store.update_field(
                    "company",
                    profile_data["company"],
                    confidence=0.6,
                    source="extracted",
                )
                updates_made = True

            if profile_data.get("city"):
                self.profile_store.update_field(
                    "city",
                    profile_data["city"],
                    confidence=0.6,
                    source="extracted",
                )
                updates_made = True

            if profile_data.get("bio"):
                self.profile_store.update_field(
                    "bio",
                    profile_data["bio"],
                    confidence=0.5,
                    source="extracted",
                )
                updates_made = True

            if profile_data.get("interests") and isinstance(profile_data["interests"], list):
                self.profile_store.update_field(
                    "interests",
                    json.dumps(profile_data["interests"]),
                    confidence=0.5,
                    source="extracted",
                )
                updates_made = True

            if profile_data.get("preferences") and isinstance(profile_data["preferences"], dict):
                self.profile_store.update_field(
                    "preferences",
                    json.dumps(profile_data["preferences"]),
                    confidence=0.5,
                    source="extracted",
                )
                updates_made = True

            if profile_data.get("background") and isinstance(profile_data["background"], dict):
                self.profile_store.update_field(
                    "background",
                    json.dumps(profile_data["background"]),
                    confidence=0.5,
                    source="extracted",
                )
                updates_made = True

            if updates_made:
                logger.info(
                    "profile.extracted",
                    {"fields": list(profile_data.keys()), "user_id": self.user_id},
                    user_id=self.user_id,
                )

        except Exception as e:
            logger.warning(
                "profile.extraction_failed",
                {"error": str(e), "user_id": self.user_id},
                user_id=self.user_id,
            )

    def _parse_json_response(self, content: str) -> dict[str, Any] | None:
        """Parse JSON from LLM response."""
        content = content.strip()

        if content.startswith("```"):
            parts = content.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                elif part:
                    try:
                        return json.loads(part)
                    except json.JSONDecodeError:
                        continue

        if content.startswith("{"):
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                pass

        return None
