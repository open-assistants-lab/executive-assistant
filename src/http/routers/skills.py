from fastapi import APIRouter

router = APIRouter(prefix="/skills", tags=["skills"])


@router.get("")
async def list_skills(user_id: str = "default"):
    """List all available skills."""
    from src.skills.registry import SkillRegistry

    registry = SkillRegistry(system_dir="src/skills", user_id=user_id)
    all_skills = registry.get_all_skills()
    system_skills = registry.get_system_skills()
    system_names = {s["name"] for s in system_skills}

    skills = []
    for s in all_skills:
        skills.append(
            {
                "name": s["name"],
                "description": s["description"],
                "is_system": s["name"] in system_names,
            }
        )

    return {"skills": skills}


@router.post("")
async def create_skill(name: str, description: str, content: str, user_id: str = "default"):
    """Create a new skill."""
    from src.skills.storage import UserSkillStorage

    storage = UserSkillStorage(user_id)
    skill_dir = storage.base_dir / name
    skill_dir.mkdir(parents=True, exist_ok=True)

    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(content, encoding="utf-8")

    return {"status": "created", "name": name, "path": str(skill_dir)}


@router.delete("/{skill_name}")
async def delete_skill(skill_name: str, user_id: str = "default"):
    """Delete a user skill."""
    import shutil

    from src.skills.storage import UserSkillStorage

    storage = UserSkillStorage(user_id)
    skill_dir = storage.base_dir / skill_name
    if skill_dir.exists():
        shutil.rmtree(skill_dir)

    return {"status": "deleted", "name": skill_name}
