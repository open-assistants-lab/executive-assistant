"""Load skill tool for on-demand skill loading."""

from langchain_core.tools import tool

from executive_assistant.skills.registry import get_skills_registry
from executive_assistant.storage.file_sandbox import get_thread_id
from executive_assistant.storage.user_storage import UserPaths


@tool
def load_skill(skill_name: str) -> str:
    """Load a named skill guide into context (tool usage + patterns).

    Priority: User skills → Global registry

    User skills are stored in data/users/{thread_id}/skills/on_demand/
    and take precedence over system skills with the same name.
    """
    from executive_assistant.skills.loader import _parse_skill_file

    registry = get_skills_registry()
    skill = None

    # ─────────────────────────────────────────────────────────────
    # STEP 1: Check user skills first (if logged in)
    # ─────────────────────────────────────────────────────────────
    thread_id = get_thread_id()
    if thread_id:
        # Normalize skill name to filename
        user_skill_path = UserPaths.get_skill_path(thread_id, skill_name)

        if user_skill_path.exists():
            try:
                # Parse and return user skill
                parsed_skill = _parse_skill_file(user_skill_path)
                return f"# {parsed_skill.name.replace('_', ' ').title()} Skill (User)\n\n{parsed_skill.content}"
            except Exception as exc:
                return f"❌ Failed to load user skill '{skill_name}': {exc}"

    # ─────────────────────────────────────────────────────────────
    # STEP 2: Fall back to global registry
    # ─────────────────────────────────────────────────────────────
    # Try exact match first
    skill = registry.get(skill_name)

    # If not found, try fuzzy match
    if not skill:
        all_skills = registry.list_all()
        skill_names = [s.name for s in all_skills]

        # Simple fuzzy match: check if skill_name is a substring
        for s in all_skills:
            if skill_name.lower() in s.name.lower():
                skill = s
                break

        # Check if skill_name contains skill name (reverse match)
        if not skill:
            for s in all_skills:
                if s.name.lower() in skill_name.lower():
                    skill = s
                    break

    if not skill:
        # Graceful error handling with helpful message
        available = ", ".join(s.name for s in registry.list_all())
        return (
            f"❌ Skill '{skill_name}' not found.\n\n"
            f"✅ Available system skills: {available}\n\n"
            f"💡 Use load_skill with one of the available skill names."
        )

    # Return from cache (no file I/O)
    content = registry.get_skill_content(skill.name)
    return f"# {skill.name.replace('_', ' ').title()} Skill\n\n{content}"


def get_skill_tool():
    """Get the load_skill tool for registration."""
    return load_skill
