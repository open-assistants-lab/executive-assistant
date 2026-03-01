"""Skills system for progressive disclosure.

Based on:
- https://docs.langchain.com/oss/python/langchain/multi-agent/skills-sql-assistant
- https://agentskills.io/specification
- https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview
"""

from src.skills.middleware import SkillMiddleware, SkillState
from src.skills.models import Skill, SkillMetadata, parse_skill_file, skill_to_system_prompt_entry
from src.skills.registry import SkillRegistry
from src.skills.storage import SkillStorage, SystemSkillStorage, UserSkillStorage
from src.skills.tools import (
    get_skill_registry,
    list_available_skills,
    set_skill_registry,
    skills_list,
    skills_load,
)

__all__ = [
    # Models
    "Skill",
    "SkillMetadata",
    "parse_skill_file",
    "skill_to_system_prompt_entry",
    # Storage
    "SkillStorage",
    "SystemSkillStorage",
    "UserSkillStorage",
    # Registry
    "SkillRegistry",
    # Middleware
    "SkillMiddleware",
    "SkillState",
    # Tools
    "skills_load",
    "skills_list",
    "list_available_skills",
    "set_skill_registry",
    "get_skill_registry",
]
