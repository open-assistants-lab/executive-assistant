"""Skill storage layer for loading skills from filesystem."""

from pathlib import Path

from src.skills.models import Skill, parse_skill_file


class SkillStorage:
    """File-based skill storage."""

    def __init__(self, base_dir: str | Path):
        self.base_dir = Path(base_dir)

    def load_skills(self) -> list[Skill]:
        skills: list[Skill] = []

        if not self.base_dir.exists():
            return skills

        for item in self.base_dir.iterdir():
            if not item.is_dir():
                continue

            skill_file = item / "SKILL.md"
            skill = parse_skill_file(skill_file)

            if skill:
                if skill["name"] != item.name:
                    continue
                skills.append(skill)

        return skills

    def load_skill(self, skill_name: str) -> Skill | None:
        skill_dir = self.base_dir / skill_name
        skill_file = skill_dir / "SKILL.md"

        return parse_skill_file(skill_file)

    def list_skills(self) -> list[str]:
        skills = self.load_skills()
        return [s["name"] for s in skills]


class SystemSkillStorage(SkillStorage):
    """Storage for system skills."""

    def __init__(self, base_dir: str | Path = "src/skills"):
        super().__init__(base_dir)


class UserSkillStorage(SkillStorage):
    """Storage for user-specific skills."""

    def __init__(self, user_id: str, base_dir: str | Path | None = None):
        if base_dir:
            storage_dir = Path(base_dir)
        else:
            from src.storage.paths import get_paths

            storage_dir = get_paths(user_id).skills_dir()

        super().__init__(storage_dir)
        self.user_id = user_id
