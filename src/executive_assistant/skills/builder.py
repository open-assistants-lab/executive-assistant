"""Skills builder for progressive disclosure in system prompts."""

from executive_assistant.skills.registry import SkillsRegistry


class SkillsBuilder:
    """Build system prompts with skill descriptions for progressive disclosure.

    This is a helper class used at agent initialization time to add
    skill descriptions to the system prompt.
    """

    def __init__(self, skills_registry: SkillsRegistry):
        """Initialize the skills builder.

        Args:
            skills_registry: The skills registry to use.
        """
        self.registry = skills_registry
        self.skills_prompt = self._build_skills_prompt()

    def _build_skills_prompt(self) -> str:
        """Build skills list for system prompt (brief descriptions only).

        Progressive disclosure: Only show skill names + brief descriptions.
        Full content loaded on-demand via load_skill().

        Returns:
            Formatted skills list for system prompt.
        """
        skills_list = []
        for skill in self.registry.list_all():
            skills_list.append(f"- **{skill.name}**: {skill.description}")

        return "\n".join(skills_list)

    def build_prompt(self, base_prompt: str) -> str:
        """Build enhanced system prompt with skills information.

        This adds skill descriptions to the base system prompt, enabling
        progressive disclosure of skill content.

        Args:
            base_prompt: The base system prompt.

        Returns:
            Enhanced system prompt with skills information.
        """
        skills_section = f"""

**Available Skills (load with load_skill):**

**Core Infrastructure** (how to use tools):
{self.skills_prompt}

**When to load skills:**
- When you're unsure which tool to use for a task
- When you need guidance on combining tools effectively
- When tackling complex multi-step tasks

**Tool Selection Guidance (Internal):**
- **Database (DB)**: Structured, queryable data (timesheets, expenses, habits)
- **Vector Store (VS)**: Semantic search, qualitative knowledge (docs, notes, conversations)
- **Files**: Reports, outputs, reference materials

All storage (DB, VS, Files) is persisted - not temporary.
"""
        return base_prompt + skills_section
