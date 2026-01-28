"""Skills builder for progressive disclosure in system prompts."""

from executive_assistant.skills.registry import Skill, SkillsRegistry


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

    def _build_skills_prompt(self, ordered_skills: list[Skill] | None = None) -> str:
        """Build skills list for system prompt (brief descriptions only).

        Progressive disclosure: Only show skill names + brief descriptions.
        Full content loaded on-demand via load_skill().

        Returns:
            Formatted skills list for system prompt.
        """
        skills_list = []
        skills = ordered_skills if ordered_skills is not None else self.registry.list_all()
        for skill in skills:
            skills_list.append(f"- **{skill.name}**: {skill.description}")

        return "\n".join(skills_list)

    def build_prompt(self, base_prompt: str, ordered_skills: list[Skill] | None = None) -> str:
        """Build enhanced system prompt with skills information.

        This adds skill descriptions to the base system prompt, enabling
        progressive disclosure of skill content.

        Args:
            base_prompt: The base system prompt.

        Returns:
            Enhanced system prompt with skills information.
        """
        _ = ordered_skills  # Skills are loaded on-demand; keep system prompt lean.
        skills_section = """

Use load_skill("<skill_name>") when you need detailed guidance.
"""
        return base_prompt + skills_section
