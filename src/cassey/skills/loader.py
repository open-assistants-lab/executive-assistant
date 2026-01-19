"""Load skills from markdown files."""

from __future__ import annotations

from pathlib import Path

from cassey.skills.registry import Skill


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


def load_skills_from_directory(directory: Path | str) -> list[Skill]:
    """Load all skill files from a directory.

    Args:
        directory: Path to directory containing skill markdown files.

    Returns:
        List of loaded Skill objects.
    """
    dir_path = Path(directory)
    if not dir_path.exists():
        return []

    skills = []
    for md_file in dir_path.rglob("*.md"):
        try:
            skill = _parse_skill_file(md_file)
            skills.append(skill)
        except Exception as exc:
            # Log but don't fail on individual file errors
            print(f"Warning: Failed to load skill from {md_file}: {exc}")

    return skills


def load_and_register_skills(directory: Path | str) -> int:
    """Load skills from directory and register them in the global registry.

    Args:
        directory: Path to directory containing skill markdown files.

    Returns:
        Number of skills loaded.
    """
    from cassey.skills.registry import get_skills_registry

    skills = load_skills_from_directory(directory)
    registry = get_skills_registry()

    for skill in skills:
        registry.register(skill)

    return len(skills)
