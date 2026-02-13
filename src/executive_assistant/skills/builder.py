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

    @staticmethod
    def _shorten_description(text: str, max_words: int = 18) -> str:
        """Trim descriptions so startup skill index remains compact."""
        words = text.split()
        if len(words) <= max_words:
            return text
        return " ".join(words[:max_words]).rstrip(",;:.") + "..."

    @staticmethod
    def _skill_category(skill: Skill) -> str:
        """Infer display category from skill tags."""
        for tag in skill.tags:
            if tag in {"analytics", "storage", "flows", "web", "personal", "core"}:
                return tag
        return "general"

    def _build_skills_prompt(
        self,
        ordered_skills: list[Skill] | None = None,
        include_startup_content: bool = False,
    ) -> str:
        """Build skills section for system prompt.

        Progressive disclosure:
        - Startup skills (on_start/): Compact index by default
        - On-demand skills (on_demand/): Names grouped by category
        - Full content is loaded via load_skill() on demand

        Returns:
            Formatted skills section for system prompt.
        """
        sections = []
        skills = ordered_skills if ordered_skills is not None else self.registry.list_all()

        startup_skills = []
        on_demand_skills = []

        for skill in skills:
            if "on_demand" in skill.tags:
                on_demand_skills.append(skill)
            else:
                startup_skills.append(skill)

        if not startup_skills and not on_demand_skills:
            return ""

        sections.append("## Skill Index")
        sections.append('Load detailed guidance only when needed via `load_skill("<skill_name>")`.')
        sections.append("")

        # Keep startup skills compact by default to control prompt size.
        if startup_skills:
            sections.append("### Core Skills")
            for skill in sorted(startup_skills, key=lambda s: s.name):
                desc = self._shorten_description(skill.description or f"Skill: {skill.name}")
                sections.append(f"- `{skill.name}`: {desc}")
            sections.append("")

            if include_startup_content:
                sections.append("### Core Skill Details")
                for skill in sorted(startup_skills, key=lambda s: s.name):
                    sections.append(f"#### {skill.name}")
                    sections.append(skill.content)
                    sections.append("")

        if on_demand_skills:
            sections.append("### On-Demand Skills")

            # Group by category.
            categories: dict[str, list[Skill]] = {}
            for skill in on_demand_skills:
                category = self._skill_category(skill)
                categories.setdefault(category, []).append(skill)

            for category, cat_skills in sorted(categories.items()):
                skill_names = [s.name for s in sorted(cat_skills, key=lambda s: s.name)]
                sections.append(f"- **{category}**: {', '.join(skill_names)}")

        return "\n".join(sections).strip()

    def build_prompt(
        self,
        base_prompt: str,
        ordered_skills: list[Skill] | None = None,
        include_startup_content: bool = False,
    ) -> str:
        """Build enhanced system prompt with skills information.

        This adds skills metadata to the base system prompt.

        Args:
            base_prompt: The base system prompt.
            ordered_skills: Optional list of skills in priority order.
            include_startup_content: Include full startup skill content in prompt.

        Returns:
            Enhanced system prompt with skills information.
        """
        skills_section = self._build_skills_prompt(
            ordered_skills=ordered_skills,
            include_startup_content=include_startup_content,
        )

        if skills_section:
            return base_prompt + "\n\n" + skills_section
        return base_prompt

    def build_skills_section(
        self,
        ordered_skills: list[Skill] | None = None,
        include_startup_content: bool = False,
    ) -> str:
        """Build only the skills section without prepending a base prompt."""
        return self._build_skills_prompt(
            ordered_skills=ordered_skills,
            include_startup_content=include_startup_content,
        )
