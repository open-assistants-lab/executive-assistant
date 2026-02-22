"""Skill middleware for injecting skill descriptions into system prompt.

Based on LangChain docs: https://docs.langchain.com/oss/python/langchain/multi-agent/skills-sql-assistant
"""

from typing import Any, NotRequired

from langchain.agents.middleware import AgentMiddleware, AgentState, hook_config
from langchain_core.messages import SystemMessage
from langgraph.runtime import Runtime

from src.skills.registry import SkillRegistry


class SkillState(AgentState):
    """Custom state for tracking loaded skills."""

    skills_loaded: NotRequired[list[str]]


class SkillMiddleware(AgentMiddleware[SkillState]):
    """Middleware that injects skill descriptions into the system prompt.

    Uses before_agent hook to load skills dynamically on each request,
    enabling live refresh when skills are added or modified.
    """

    state_schema = SkillState
    tools = []

    def __init__(
        self,
        system_dir: str = "src/skills",
        user_id: str | None = None,
    ):
        """Initialize skill middleware.

        Args:
            system_dir: Path to system skills directory
            user_id: Optional user ID for user-specific skills
        """
        self.registry = SkillRegistry(system_dir=system_dir, user_id=user_id)

    def _build_skills_prompt(self) -> str:
        """Build the skills prompt section.

        Returns:
            Formatted skills prompt for system message
        """
        skill_entries = self.registry.get_skill_descriptions()

        if not skill_entries:
            return ""

        skills_list = "\n".join(skill_entries)

        return (
            f"\n\n## Available Skills\n\n"
            f"{skills_list}\n\n"
            f"Use the load_skill tool when you need detailed information "
            f"about handling a specific type of request."
        )

    @hook_config()
    def before_agent(
        self,
        state: SkillState,
        runtime: Runtime,
    ) -> dict[str, Any] | None:
        """Inject skill descriptions into system prompt.

        This hook runs before each agent invocation, loading skills dynamically
        to support live refresh (new skills, modified skills).
        """
        skills_prompt = self._build_skills_prompt()

        if not skills_prompt:
            return None

        # Get current messages
        messages = state.get("messages", [])

        if not messages:
            return None

        # Find the last SystemMessage
        system_messages = [m for m in messages if isinstance(m, SystemMessage)]

        if not system_messages:
            return None

        last_system = system_messages[-1]

        # Append skills to system message content
        if hasattr(last_system, "content_blocks") and isinstance(last_system.content_blocks, list):
            # New content blocks format
            new_content_blocks = list(last_system.content_blocks) + [
                {"type": "text", "text": skills_prompt}
            ]
            new_content = new_content_blocks
        else:
            # String format (legacy)
            existing_content = last_system.content
            if isinstance(existing_content, str):
                new_content = existing_content + skills_prompt
            else:
                new_content = existing_content

        # Create updated system message
        if isinstance(new_content, list):
            new_system_message = SystemMessage(content=new_content)
        else:
            new_system_message = SystemMessage(content=new_content)

        # Find and replace the system message in state
        new_messages = []
        for msg in messages:
            if msg is last_system:
                new_messages.append(new_system_message)
            else:
                new_messages.append(msg)

        return {"messages": new_messages}
