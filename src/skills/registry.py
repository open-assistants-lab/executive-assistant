"""Skill registry — unified storage for all skills.

System skills (src/skills/) are seeded to ~/Executive Assistant/Skills/ on first run.
After seeding, system and user skills live in the same directory and are treated identically.
"""

import threading
from pathlib import Path

from src.skills.models import Skill
from src.skills.storage import SkillStorage

_registries: dict[str, "SkillRegistry"] = {}
_lock = threading.Lock()


def get_skill_registry(user_id: str = "default_user") -> "SkillRegistry":
    """Get or create a cached SkillRegistry for a user.

    All code should use this factory instead of constructing SkillRegistry
    directly, to ensure a single cached instance per user.
    """
    uid = user_id or "default_user"
    with _lock:
        if uid not in _registries:
            _registries[uid] = SkillRegistry(user_id=user_id)
        return _registries[uid]


def reset_skill_registries() -> None:
    """Clear all cached registries (useful for testing)."""
    with _lock:
        _registries.clear()


class SkillRegistry:
    """Registry for all skills (system + user) in one unified location.

    On first run, system skills are seeded from src/skills/ to
    the user's skills directory (~/Executive Assistant/Skills/).
    After seeding, all skills live in the same place and are treated identically.
    """

    def __init__(
        self,
        skills_dir: str | Path | None = None,
        user_id: str | None = None,
    ):
        from src.storage.paths import DataPaths

        paths = DataPaths(user_id=user_id)
        self.skills_dir = Path(skills_dir) if skills_dir else paths.skills_dir()
        self.storage = SkillStorage(self.skills_dir)
        self._loaded_skills: set[str] = set()
        self._seeded = False

    def _seed_system_skills(self) -> None:
        """Copy system skills to user skills directory on first run."""
        if self._seeded:
            return
        self._seeded = True

        import shutil

        system_src = Path("src/skills")
        if not system_src.exists():
            return

        self.skills_dir.mkdir(parents=True, exist_ok=True)

        for item in system_src.iterdir():
            if not item.is_dir():
                continue
            dest = self.skills_dir / item.name
            if not dest.exists():
                shutil.copytree(item, dest)

    def reload(self) -> None:
        """Reload all skills (clear cache, re-seed system skills)."""
        self._seeded = False

    def mark_skill_loaded(self, skill_name: str) -> None:
        """Track that a skill has been loaded into context."""
        self._loaded_skills.add(skill_name)

    def get_loaded_skills(self) -> list[str]:
        """Get list of skills loaded in current session."""
        return list(self._loaded_skills)

    def get_all_skills(self) -> list[Skill]:
        """Get all available skills."""
        self._seed_system_skills()
        return self.storage.load_skills()

    def get_skill(self, skill_name: str) -> Skill | None:
        """Get a specific skill by name."""
        self._seed_system_skills()
        return self.storage.load_skill(skill_name)

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
