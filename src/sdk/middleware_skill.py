"""Skill middleware for injecting skill descriptions into system prompt.

SDK-native implementation: replaces src/middleware/skill.py.
Uses SDK Middleware base class instead of LangChain AgentMiddleware.
"""

from typing import Any

from src.sdk.messages import Message
from src.sdk.middleware import Middleware
from src.sdk.state import AgentState
from src.storage.paths import get_paths


class SkillMiddleware(Middleware):
    """Middleware that injects skill descriptions into the system prompt.

    Uses before_agent hook to load skills dynamically on each request,
    enabling live refresh when skills are added or modified.

    SDK-native: extends Middleware instead of LangChain AgentMiddleware.
    """

    def __init__(self, system_dir: str = "src/skills", user_id: str | None = None):
        from src.skills.registry import SkillRegistry

        self.registry = SkillRegistry(system_dir=system_dir, user_id=user_id)
        self.user_id = user_id

    def _get_user_skills_dir(self) -> str:
        return (
            str(get_paths(self.user_id).skills_dir())
            if self.user_id
            else str(get_paths("default").skills_dir())
        )

    def _build_skills_prompt(self) -> str:
        skill_entries = self.registry.get_skill_descriptions()

        if not skill_entries:
            return ""

        skills_list = "\n".join(skill_entries)
        user_skills_dir = self._get_user_skills_dir()

        return (
            f"\n\n## Available Skills\n\n"
            f"{skills_list}\n\n"
            f"## User Skills Directory\n\n"
            f"User-specific skills are stored in: `{user_skills_dir}/`\n"
            f"When creating or modifying skills for a user, use this directory.\n\n"
            f"Use the skills_load tool when you need detailed information "
            f"about handling a specific type of request."
        )

    def before_agent(self, state: AgentState) -> dict[str, Any] | None:
        skills_prompt = self._build_skills_prompt()

        if not skills_prompt:
            return None

        messages = state.messages

        if not messages:
            return None

        system_idx = None
        for i, msg in enumerate(messages):
            if msg.role == "system":
                system_idx = i
                break

        if system_idx is None:
            return None

        sys_msg = messages[system_idx]
        content = sys_msg.content
        if isinstance(content, str):
            new_content = content + skills_prompt
        elif isinstance(content, list):
            new_content = list(content) + [{"type": "text", "text": skills_prompt}]
        else:
            new_content = str(content) + skills_prompt

        messages[system_idx] = (
            Message.system(new_content)
            if isinstance(new_content, str)
            else Message(role="system", content=new_content)
        )

        return {"messages": messages}


__all__ = ["SkillMiddleware"]
