"""Skills registry for managing available skills."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Skill:
    """A skill that teaches tool usage patterns.

    Skills teach meta-knowledge about tool usage:
    - When to use which tool
    - How to combine tools effectively
    - Best practices for common workflows
    """

    name: str  # Unique identifier (e.g., "data_management")
    description: str  # 1-2 sentences (shown in system prompt)
    content: str  # Full skill content (loaded on-demand)
    author: str = "Executive Assistant Team"  # Who maintains this skill
    version: str = "1.0.0"  # Skill version
    tags: list[str] = ()  # For categorization and search


class SkillsRegistry:
    """Manage available skills with caching."""

    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}
        self._content_cache: dict[str, str] = {}  # Cache skill content in memory

    def register(self, skill: Skill) -> None:
        """Register a skill and cache its content.

        Args:
            skill: The skill to register.
        """
        self._skills[skill.name] = skill
        # Cache content in memory on startup (skills rarely change)
        self._content_cache[skill.name] = skill.content

    def get(self, name: str) -> Skill | None:
        """Get skill by name (from cache).

        Args:
            name: The skill name.

        Returns:
            The skill if found, None otherwise.
        """
        return self._skills.get(name)

    def get_skill_content(self, name: str) -> str | None:
        """Get skill content from cache (no file I/O).

        Args:
            name: The skill name.

        Returns:
            The skill content if found, None otherwise.
        """
        return self._content_cache.get(name)

    def list_all(self) -> list[Skill]:
        """List all available skills.

        Returns:
            List of all registered skills.
        """
        return list(self._skills.values())

    def search(self, query: str) -> list[Skill]:
        """Search skills by name/description/tags.

        Args:
            query: Search query.

        Returns:
            List of matching skills.
        """
        query_lower = query.lower()
        results = []
        for skill in self._skills.values():
            if (
                query_lower in skill.name.lower()
                or query_lower in skill.description.lower()
                or any(query_lower in tag.lower() for tag in skill.tags)
            ):
                results.append(skill)
        return results


# Global registry instance
_registry: SkillsRegistry | None = None


def get_skills_registry() -> SkillsRegistry:
    """Get the global skills registry.

    Returns:
        The global SkillsRegistry instance.
    """
    global _registry
    if _registry is None:
        _registry = SkillsRegistry()
    return _registry


def reset_skills_registry() -> None:
    """Reset the global skills registry (for testing)."""
    global _registry
    _registry = None
