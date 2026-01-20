"""Load skill tool for on-demand skill loading."""

from langchain_core.tools import tool

from executive_assistant.skills.registry import get_skills_registry


@tool
def load_skill(skill_name: str) -> str:
    """Load a specialized skill into the agent's context.

    Use this when you need guidance on tool selection or workflow patterns.
    Skills teach WHEN to use which tool and HOW to combine tools effectively.

    Available Core Skills (Phase 1):
    - data_management: DB vs VS vs Files decision framework
    - record_keeping: Information lifecycle (Record → Organize → Retrieve)
    - progress_tracking: Measuring change over time
    - workflow_patterns: How to combine tools effectively
    - synthesis: Combining multiple information sources

    Available Personal Skills (Phase 1):
    - task_tracking: Timesheets, habits, expenses
    - information_retrieval: Finding past conversations, docs
    - report_generation: Data analysis & summaries
    - planning: Task breakdown, estimation
    - organization: Calendar, reminders, structure

    Args:
        skill_name: The name of the skill to load (e.g., "data_management")

    Returns:
        Full skill content with tool usage patterns and examples.
    """
    registry = get_skills_registry()

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
            f"✅ Available skills: {available}\n\n"
            f"💡 Use load_skill with one of the available skill names."
        )

    # Return from cache (no file I/O)
    content = registry.get_skill_content(skill.name)
    return f"# {skill.name.replace('_', ' ').title()} Skill\n\n{content}"


def get_skill_tool():
    """Get the load_skill tool for registration."""
    return load_skill
