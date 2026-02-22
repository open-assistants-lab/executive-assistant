"""Skill storage layer for loading skills from filesystem."""

from pathlib import Path

from src.skills.models import Skill, parse_skill_file


class SkillStorage:
    """File-based skill storage."""

    def __init__(self, base_dir: str | Path):
        """Initialize skill storage.

        Args:
            base_dir: Base directory containing skill folders
        """
        self.base_dir = Path(base_dir)

    def load_skills(self) -> list[Skill]:
        """Load all skills from the base directory.

        Returns:
            List of skills found in the directory
        """
        skills = []

        if not self.base_dir.exists():
            return skills

        # Scan for skill directories
        for item in self.base_dir.iterdir():
            if not item.is_dir():
                continue

            skill_file = item / "SKILL.md"
            skill = parse_skill_file(skill_file)

            if skill:
                # Validate skill name matches directory name
                if skill["name"] != item.name:
                    continue
                skills.append(skill)

        return skills

    def load_skill(self, skill_name: str) -> Skill | None:
        """Load a specific skill by name.

        Args:
            skill_name: Name of the skill to load

        Returns:
            Skill dict or None if not found
        """
        skill_dir = self.base_dir / skill_name
        skill_file = skill_dir / "SKILL.md"

        return parse_skill_file(skill_file)

    def list_skills(self) -> list[str]:
        """List all available skill names.

        Returns:
            List of skill names
        """
        skills = self.load_skills()
        return [s["name"] for s in skills]


class SystemSkillStorage(SkillStorage):
    """Storage for system skills."""

    def __init__(self, base_dir: str | Path = "src/skills"):
        """Initialize system skill storage.

        Args:
            base_dir: Path to system skills directory
        """
        super().__init__(base_dir)


class UserSkillStorage(SkillStorage):
    """Storage for user-specific skills."""

    def __init__(self, user_id: str, base_dir: str | Path | None = None):
        """Initialize user skill storage.

        Args:
            user_id: User ID for path construction
            base_dir: Optional base directory override
        """
        if base_dir:
            storage_dir = Path(base_dir)
        else:
            storage_dir = Path(f"data/users/{user_id}/skills")

        super().__init__(storage_dir)
        self.user_id = user_id
