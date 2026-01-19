"""Skills for the Cassey agent."""

from cassey.skills.builder import SkillsBuilder
from cassey.skills.loader import load_and_register_skills, load_skills_from_directory
from cassey.skills.registry import Skill, SkillsRegistry, get_skills_registry, reset_skills_registry
from cassey.skills.tool import get_skill_tool, load_skill

__all__ = [
    # Core classes
    "Skill",
    "SkillsRegistry",
    "SkillsBuilder",
    # Registry functions
    "get_skills_registry",
    "reset_skills_registry",
    # Loader functions
    "load_skills_from_directory",
    "load_and_register_skills",
    # Tool
    "load_skill",
    "get_skill_tool",
]


# Legacy import (deprecated)
def get_sqlite_helper_tools():
    """Deprecated: Use load_skill tool instead.

    This function is kept for backward compatibility.
    """
    from warnings import warn

    warn("get_sqlite_helper_tools is deprecated. Use the load_skill tool instead.", DeprecationWarning, stacklevel=2)
    return []
