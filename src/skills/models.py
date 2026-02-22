"""Skill models and schema for Agent Skills compatibility."""

from pathlib import Path
from typing import NotRequired, TypedDict

import yaml


class SkillMetadata(TypedDict):
    """Skill metadata from YAML frontmatter."""

    name: str
    description: str
    license: NotRequired[str]
    compatibility: NotRequired[str]
    metadata: NotRequired[dict[str, str]]
    allowed_tools: NotRequired[str]


class Skill(TypedDict):
    """A skill that can be progressively disclosed to the agent.

    Based on Agent Skills spec: https://agentskills.io/specification
    """

    name: str
    description: str
    content: str
    path: str
    license: NotRequired[str]
    compatibility: NotRequired[str]
    metadata: NotRequired[dict[str, str]]
    allowed_tools: NotRequired[str]


def parse_skill_file(skill_path: Path) -> Skill | None:
    """Parse a SKILL.md file and extract metadata and content.

    Args:
        skill_path: Path to SKILL.md file

    Returns:
        Skill dict with metadata and content, or None if invalid
    """
    if not skill_path.exists():
        return None

    content = skill_path.read_text(encoding="utf-8")

    # Split by YAML frontmatter delimiter
    if not content.startswith("---"):
        return None

    parts = content.split("---", 2)
    if len(parts) < 3:
        return None

    frontmatter = parts[1].strip()
    body = parts[2].strip() if len(parts) > 2 else ""

    # Parse YAML frontmatter
    try:
        metadata = yaml.safe_load(frontmatter)
    except yaml.YAMLError:
        return None

    if not isinstance(metadata, dict):
        return None

    # Validate required fields
    name = metadata.get("name")
    description = metadata.get("description")

    if not name or not description:
        return None

    # Validate name format (lowercase, numbers, hyphens only)
    if not _is_valid_skill_name(name):
        return None

    skill: Skill = {
        "name": name,
        "description": description,
        "content": body,
        "path": str(skill_path.parent),
    }

    # Optional fields
    if license := metadata.get("license"):
        skill["license"] = license
    if compatibility := metadata.get("compatibility"):
        skill["compatibility"] = compatibility
    if metadata_dict := metadata.get("metadata"):
        skill["metadata"] = metadata_dict
    if allowed_tools := metadata.get("allowed_tools"):
        skill["allowed_tools"] = allowed_tools

    return skill


def _is_valid_skill_name(name: str) -> bool:
    """Validate skill name format.

    Must be 1-64 characters, lowercase letters and hyphens only,
    cannot start or end with hyphen, no consecutive hyphens.
    """
    if not name or len(name) > 64:
        return False
    if name[0] == "-" or name[-1] == "-":
        return False
    if "--" in name:
        return False
    return all(c.islower() or c.isdigit() or c == "-" for c in name)


def skill_to_system_prompt_entry(skill: Skill) -> str:
    """Convert skill to system prompt entry (name + description).

    Args:
        skill: Skill dict

    Returns:
        Formatted string for system prompt
    """
    return f"- **{skill['name']}**: {skill['description']}"
