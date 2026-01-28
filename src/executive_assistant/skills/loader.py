"""Load skills from markdown files with support for on-demand loading."""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

from executive_assistant.skills.registry import Skill


class SkillLoadResult(NamedTuple):
    """Result of loading skills from a directory."""
    
    startup: list[Skill]  # Skills to load at startup (on_start/)
    on_demand: list[Skill]  # Skills available for on-demand loading (on_demand/*/)


def _parse_skill_file(file_path: Path) -> Skill:
    """Parse a skill markdown file into a Skill object.

    Expected format:
    ```markdown
    # Skill Name

    Description: Brief description (1-2 sentences)

    Tags: tag1, tag2, tag3

    ## Overview
    ...skill content...
    ```

    Args:
        file_path: Path to the skill markdown file.

    Returns:
        A Skill object.

    Raises:
        ValueError: If the file format is invalid.
    """
    content = file_path.read_text(encoding="utf-8")
    lines = content.split("\n")

    if len(lines) < 2:
        raise ValueError(f"Skill file {file_path} is too short")

    # Parse title (first line)
    title_line = lines[0]
    if not title_line.startswith("# "):
        raise ValueError(f"Skill file {file_path} must start with '# Title'")
    name = title_line[2:].strip().lower().replace(" ", "_")

    # Parse metadata
    description = ""
    tags: list[str] = []
    content_start = 0

    for i, line in enumerate(lines[1:], 1):
        if line.startswith("Description:"):
            description = line.split(":", 1)[1].strip()
        elif line.startswith("Tags:"):
            tags_str = line.split(":", 1)[1].strip()
            tags = [t.strip() for t in tags_str.split(",") if t.strip()]
        elif line.startswith("##"):
            content_start = i - 1
            break

    # Extract full content (from title onwards)
    full_content = "\n".join(lines[content_start:])

    if not description:
        # Use first paragraph after overview as description
        for i in range(content_start, len(lines)):
            if lines[i].startswith("## Overview"):
                # Get next non-empty, non-heading line
                for j in range(i + 1, len(lines)):
                    if lines[j].strip() and not lines[j].startswith("#"):
                        description = lines[j].strip()
                        break
                break

    if not description:
        description = f"Skill: {name}"

    return Skill(
        name=name,
        description=description,
        content=full_content,
        tags=tags,
    )


def load_skills_from_directory(directory: Path | str) -> SkillLoadResult:
    """Load skills from directory with on_start/on_demand separation.

    Directory structure:
        content/
        ├── on_start/          # Always loaded at startup
        │   └── *.md
        └── on_demand/         # Available for on-demand loading
            ├── analytics/
            ├── storage/
            ├── flows/
            └── ...

    Args:
        directory: Path to skills content directory.

    Returns:
        SkillLoadResult with startup and on_demand skills.
    """
    dir_path = Path(directory)
    if not dir_path.exists():
        return SkillLoadResult(startup=[], on_demand=[])

    startup_skills: list[Skill] = []
    on_demand_skills: list[Skill] = []

    # Load on_start skills (always included)
    on_start_dir = dir_path / "on_start"
    if on_start_dir.exists():
        for md_file in on_start_dir.rglob("*.md"):
            try:
                skill = _parse_skill_file(md_file)
                startup_skills.append(skill)
            except Exception as exc:
                print(f"Warning: Failed to load skill from {md_file}: {exc}")

    # Load on_demand skills (available but not in prompt)
    on_demand_dir = dir_path / "on_demand"
    if on_demand_dir.exists():
        for md_file in on_demand_dir.rglob("*.md"):
            try:
                skill = _parse_skill_file(md_file)
                on_demand_skills.append(skill)
            except Exception as exc:
                print(f"Warning: Failed to load skill from {md_file}: {exc}")

    return SkillLoadResult(startup=startup_skills, on_demand=on_demand_skills)


def load_and_register_skills(directory: Path | str) -> tuple[int, int]:
    """Load skills from directory and register them in the global registry.

    Startup skills are registered for immediate use (added to system prompt).
    On-demand skills are registered but marked as available for lazy loading.

    Args:
        directory: Path to skills content directory.

    Returns:
        Tuple of (startup_count, on_demand_count).
    """
    from executive_assistant.skills.registry import get_skills_registry

    result = load_skills_from_directory(directory)
    registry = get_skills_registry()

    # Register startup skills (will be in system prompt)
    for skill in result.startup:
        registry.register(skill)

    # Register on-demand skills (available but not in prompt)
    for skill in result.on_demand:
        # Mark as on-demand by adding a tag
        if "on_demand" not in skill.tags:
            skill.tags.append("on_demand")
        registry.register(skill)

    return len(result.startup), len(result.on_demand)
