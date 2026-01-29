"""User skill creation tool."""

from datetime import datetime
from pathlib import Path

from langchain_core.tools import tool

from executive_assistant.storage.file_sandbox import get_thread_id
from executive_assistant.storage.user_storage import UserPaths


@tool
def create_user_skill(
    name: str,
    description: str,
    content: str,
    tags: str = "",
) -> str:
    """Create a personal skill for the current user.

    User skills are private to your thread and can be loaded immediately
    without restart using the load_skill tool.

    Args:
        name: Skill name (will be normalized to snake_case)
        description: Brief description of what this skill does
        content: Skill content in markdown format
        tags: Comma-separated tags (optional)

    Returns:
        Confirmation message with canonical skill name.

    Examples:
        create_user_skill(
            name="todo workflow",
            description="My personal todo management workflow",
            content="## Overview\\nWhen I say 'track todos', use TDB...",
            tags="productivity,todos"
        )
    """
    # Get current thread_id
    thread_id = get_thread_id()
    if not thread_id:
        return "❌ No thread context available. Please try again."

    # ─────────────────────────────────────────────────────────────
    # Validate skill name
    # ─────────────────────────────────────────────────────────────
    if not name or len(name) > 100:
        return "❌ Skill name must be 1-100 characters."

    # Normalize name to snake_case
    normalized_name = name.lower().replace(" ", "_").replace("-", "_")
    if not normalized_name.replace("_", "").isalnum():
        return "❌ Skill name can only contain letters, numbers, spaces, and hyphens."

    # ─────────────────────────────────────────────────────────────
    # Validate content size (max 50KB)
    # ─────────────────────────────────────────────────────────────
    max_size = 50 * 1024  # 50KB
    if len(content) > max_size:
        return f"❌ Skill content too large ({len(content)} bytes, max {max_size})."

    # ─────────────────────────────────────────────────────────────
    # Parse tags
    # ─────────────────────────────────────────────────────────────
    tag_list = []
    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]

    # ─────────────────────────────────────────────────────────────
    # Build skill markdown
    # ─────────────────────────────────────────────────────────────
    timestamp = datetime.now().isoformat()
    skill_md = f"""# {name.title()}

Description: {description}

Tags: {", ".join(tag_list)} if tag_list else "user_skill"}

*Created: {timestamp}*

## Overview
{content}
"""

    # ─────────────────────────────────────────────────────────────
    # Write to user skills directory
    # ─────────────────────────────────────────────────────────────
    skill_path = UserPaths.get_skill_path(thread_id, normalized_name)

    try:
        # Ensure directory exists
        skill_path.parent.mkdir(parents=True, exist_ok=True)

        # Write skill file
        skill_path.write_text(skill_md, encoding="utf-8")

        return (
            f"✅ Skill created successfully!\n\n"
            f"**Name:** {normalized_name}\n"
            f"**Description:** {description}\n\n"
            f"Load it with: load_skill('{normalized_name}')"
        )
    except Exception as e:
        return f"❌ Failed to create skill: {e}"


def get_user_skill_tools():
    """Get user skill tools for registration."""
    return [create_user_skill]
