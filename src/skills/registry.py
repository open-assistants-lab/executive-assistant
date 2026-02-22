"""Skill registry that combines system and user skills."""

from src.skills.models import Skill
from src.skills.storage import SystemSkillStorage, UserSkillStorage


class SkillRegistry:
    """Registry that combines system and user skills."""

    def __init__(
        self,
        system_dir: str = "src/skills",
        user_id: str | None = None,
    ):
        """Initialize skill registry.

        Args:
            system_dir: Path to system skills directory
            user_id: Optional user ID for user-specific skills
        """
        self.system_storage = SystemSkillStorage(system_dir)
        self.user_storage = UserSkillStorage(user_id) if user_id else None
        self._system_skills: list[Skill] | None = None
        self._user_skills: list[Skill] | None = None

    def _load_system_skills(self) -> list[Skill]:
        """Load system skills (cached)."""
        if self._system_skills is None:
            self._system_skills = self.system_storage.load_skills()
        return self._system_skills

    def _load_user_skills(self) -> list[Skill]:
        """Load user skills (cached)."""
        if self._user_skills is None and self.user_storage:
            self._user_skills = self.user_storage.load_skills()
        return self._user_skills or []

    def reload(self) -> None:
        """Reload all skills (clear cache)."""
        self._system_skills = None
        self._user_skills = None

    def get_all_skills(self) -> list[Skill]:
        """Get all available skills (system + user).

        Returns:
            Combined list of all skills
        """
        system = self._load_system_skills()
        user = self._load_user_skills()
        return system + user

    def get_skill(self, skill_name: str) -> Skill | None:
        """Get a specific skill by name.

        Checks user skills first, then system skills.

        Args:
            skill_name: Name of the skill

        Returns:
            Skill dict or None if not found
        """
        # Check user skills first
        if self.user_storage:
            skill = self.user_storage.load_skill(skill_name)
            if skill:
                return skill

        # Check system skills
        return self.system_storage.load_skill(skill_name)

    def list_skills(self) -> list[str]:
        """List all available skill names.

        Returns:
            List of all skill names
        """
        skills = self.get_all_skills()
        return [s["name"] for s in skills]

    def get_skill_descriptions(self) -> list[str]:
        """Get formatted skill descriptions for system prompt.

        Returns:
            List of formatted skill entries
        """
        from src.skills.models import skill_to_system_prompt_entry

        skills = self.get_all_skills()
        return [skill_to_system_prompt_entry(s) for s in skills]
