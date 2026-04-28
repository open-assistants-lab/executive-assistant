"""Skill registry that combines system and user skills."""

import threading

from src.skills.models import Skill
from src.skills.storage import SystemSkillStorage, UserSkillStorage

_registries: dict[str, "SkillRegistry"] = {}
_lock = threading.Lock()


def get_skill_registry(user_id: str = "default_user", system_dir: str = "src/skills") -> "SkillRegistry":
    """Get or create a cached SkillRegistry for a user.

    All code should use this factory instead of constructing SkillRegistry
    directly, to ensure a single cached instance per user.
    """
    uid = user_id or "default_user"
    with _lock:
        if uid not in _registries:
            _registries[uid] = SkillRegistry(system_dir=system_dir, user_id=user_id)
        return _registries[uid]


def reset_skill_registries() -> None:
    """Clear all cached registries (useful for testing)."""
    with _lock:
        _registries.clear()


class SkillRegistry:
    """Registry that combines system and user skills."""

    def __init__(
        self,
        system_dir: str = "src/skills",
        user_id: str | None = None,
    ):
        self.system_storage = SystemSkillStorage(system_dir)
        self.user_storage = UserSkillStorage(user_id) if user_id else None
        self._system_skills: list[Skill] | None = None
        self._user_skills: list[Skill] | None = None
        self._loaded_skills: set[str] = set()

    def _load_system_skills(self) -> list[Skill]:
        if self._system_skills is None:
            self._system_skills = self.system_storage.load_skills()
        return self._system_skills

    def _load_user_skills(self) -> list[Skill]:
        if self._user_skills is None and self.user_storage:
            self._user_skills = self.user_storage.load_skills()
        return self._user_skills or []

    def reload(self) -> None:
        """Reload all skills (clear cache)."""
        self._system_skills = None
        self._user_skills = None

    def mark_skill_loaded(self, skill_name: str) -> None:
        """Track that a skill has been loaded into context."""
        self._loaded_skills.add(skill_name)

    def get_loaded_skills(self) -> list[str]:
        """Get list of skills loaded in current session."""
        return list(self._loaded_skills)

    def get_all_skills(self) -> list[Skill]:
        """Get all available skills (system + user)."""
        system = self._load_system_skills()
        user = self._load_user_skills()
        return system + user

    def get_system_skills(self) -> list[Skill]:
        """Get system skills only."""
        return self._load_system_skills()

    def get_skill(self, skill_name: str) -> Skill | None:
        """Get a specific skill by name.

        Checks user skills first, then system skills.

        Args:
            skill_name: Name of the skill

        Returns:
            Skill dict or None if not found
        """
        if self.user_storage:
            skill = self.user_storage.load_skill(skill_name)
            if skill:
                return skill

        return self.system_storage.load_skill(skill_name)

    def list_skills(self) -> list[str]:
        """List all available skill names."""
        skills = self.get_all_skills()
        return [s["name"] for s in skills]

    def search_skills(self, query: str) -> list[Skill]:
        """Search for skills matching a query string."""
        query_lower = query.lower()
        all_skills = self.get_all_skills()
        return [
            s
            for s in all_skills
            if query_lower in s["name"].lower()
            or query_lower in s.get("description", "").lower()
            or query_lower in s.get("content", "").lower()
        ]

    def get_skill_descriptions(self) -> list[str]:
        """Get formatted skill descriptions for system prompt."""
        from src.skills.models import skill_to_system_prompt_entry

        skills = self.get_all_skills()
        return [skill_to_system_prompt_entry(s) for s in skills]
