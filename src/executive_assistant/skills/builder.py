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
        """Build skills list for system prompt.

        Progressive disclosure:
        - Startup skills (on_start/): FULL CONTENT included in prompt
        - On-demand skills (on_demand/): Only names listed, content loaded via load_skill()

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
        
        # Include FULL CONTENT of startup skills in prompt
        if startup_skills:
            sections.append("\n## Core Skills (Always Available)\n")
            for skill in startup_skills:
                sections.append(f"\n### {skill.name}\n")
                sections.append(f"*{skill.description}*\n")
                sections.append(skill.content)
        
        # Mention on-demand skills are available
        if on_demand_skills:
            sections.append("\n## Additional Skills (Load on Demand)\n")
            sections.append("Use `load_skill(\"<skill_name>\")` to access detailed guidance.\n")
            
            # Group by category if available
            categories: dict[str, list[Skill]] = {}
            for skill in on_demand_skills:
                category = "general"
                for tag in skill.tags:
                    if tag in ["analytics", "storage", "flows", "web", "personal", "core"]:
                        category = tag
                        break
                categories.setdefault(category, []).append(skill)
            
            for category, cat_skills in sorted(categories.items()):
                skill_names = [s.name for s in cat_skills]
                sections.append(f"- **{category}**: {', '.join(skill_names)}")

        result = "\n".join(sections)
        return result

    def build_prompt(self, base_prompt: str, ordered_skills: list[Skill] | None = None) -> str:
        """Build enhanced system prompt with skills information.

        This adds skill content to the base system prompt:
        - Startup skills: Full content included
        - On-demand skills: Names listed, load via load_skill()

        Args:
            base_prompt: The base system prompt.
            ordered_skills: Optional list of skills in priority order.

        Returns:
            Enhanced system prompt with skills information.
        """
        skills_section = self._build_skills_prompt(ordered_skills)
        
        if skills_section:
            return base_prompt + "\n\n" + skills_section
        else:
            return base_prompt
