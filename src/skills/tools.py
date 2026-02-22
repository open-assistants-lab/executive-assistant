"""Load skill tool for on-demand skill content loading.

Based on LangChain docs: https://docs.langchain.com/oss/python/langchain/multi-agent/skills-sql-assistant
"""

from typing import Any

from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langgraph.types import Command

from src.skills.registry import SkillRegistry

# Global registry instance (can be overridden)
_registry: SkillRegistry | None = None


def set_skill_registry(registry: SkillRegistry) -> None:
    """Set the global skill registry for load_skill tool.

    Args:
        registry: SkillRegistry instance
    """
    global _registry
    _registry = registry


def get_skill_registry(system_dir: str = "src/skills", user_id: str | None = None) -> SkillRegistry:
    """Get or create skill registry.

    Args:
        system_dir: Path to system skills directory
        user_id: Optional user ID for user skills

    Returns:
        SkillRegistry instance
    """
    global _registry
    if _registry is None:
        _registry = SkillRegistry(system_dir=system_dir, user_id=user_id)
    return _registry


@tool
def load_skill(
    skill_name: str,
    runtime: Any | None = None,
) -> str | Command:
    """Load the full content of a skill into the agent's context.

    Use this when you need detailed information about handling a specific
    type of request. This will provide you with comprehensive instructions,
    policies, and guidelines for the skill area.

    Args:
        skill_name: The name of the skill to load (e.g., "pdf-processing", "sql-analytics")

    Returns:
        Full skill content as a ToolMessage, or error message if not found.
        When runtime is provided, also updates state to track loaded skill.
    """
    registry = get_skill_registry()

    skill = registry.get_skill(skill_name)

    if not skill:
        available = ", ".join(registry.list_skills())
        error_msg = f"Skill '{skill_name}' not found. Available skills: {available}"

        if runtime:
            tool_call_id = getattr(runtime, "tool_call_id", None)
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            content=error_msg,
                            tool_call_id=tool_call_id or "unknown",
                        )
                    ]
                }
            )
        return error_msg

    # Build skill content
    skill_content = f"# {skill['name']}\n\n{skill['content']}"

    if runtime:
        tool_call_id = getattr(runtime, "tool_call_id", None)
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=skill_content,
                        tool_call_id=tool_call_id or "unknown",
                    )
                ],
                "skills_loaded": [skill_name],
            }
        )

    return skill_content


def list_available_skills() -> str:
    """List all available skills.

    Returns:
        Formatted list of skill names and descriptions
    """
    registry = get_skill_registry()
    skills = registry.get_all_skills()

    if not skills:
        return "No skills available."

    lines = ["### Available Skills\n"]
    for skill in skills:
        lines.append(f"- **{skill['name']}**: {skill['description']}")

    return "\n".join(lines)


@tool
def list_skills() -> str:
    """List all available skills with their descriptions.

    Use this to see what skills are available before loading one.

    Returns:
        Formatted list of available skills
    """
    return list_available_skills()
