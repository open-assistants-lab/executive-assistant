import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from src.skills import SkillRegistry


class SubagentValidationResult(BaseModel):
    """Result of subagent validation."""

    valid: bool
    errors: list[str] = []
    warnings: list[str] = []


def get_available_tool_names() -> set[str]:
    """Get list of available tool names."""
    from src.agents.manager import get_default_tools

    tools = get_default_tools("default")
    return {tool.name for tool in tools}


def get_mcp_server_names() -> set[str]:
    """Get list of configured MCP server names."""
    # MCP servers are loaded from user's .mcp.json, not from system config
    # Return empty set - validation will just warn if server doesn't exist
    return set()


def validate_subagent_config(
    user_id: str,
    config: dict[str, Any],
    base_path: Path | None = None,
) -> SubagentValidationResult:
    """Validate subagent configuration.

    Args:
        user_id: The user ID
        config: The config dictionary (from config.yaml)
        base_path: Optional path to subagent directory

    Returns:
        ValidationResult with errors and warnings
    """
    errors = []
    warnings = []

    # Validate name
    name = config.get("name", "")
    if not name:
        errors.append("Missing required field: name")
    elif not _is_valid_name(name):
        errors.append(f"Invalid name '{name}': only alphanumeric, hyphens, and underscores allowed")

    # Validate model (if provided)
    model = config.get("model")
    if model and not _is_valid_model(model):
        warnings.append(f"Model '{model}' may not be available")

    # Validate skills
    skills = config.get("skills", [])
    if not isinstance(skills, list):
        errors.append("skills must be a list")
    else:
        registry = SkillRegistry(system_dir="src/skills", user_id=user_id)
        available_skills = {s["name"] for s in registry.get_all_skills()}

        for skill in skills:
            if skill not in available_skills:
                errors.append(f"Skill '{skill}' not found in system or user skills")

    # Validate tools
    tools = config.get("tools", [])
    if not isinstance(tools, list):
        errors.append("tools must be a list")
    else:
        available_tools = get_available_tool_names()

        for tool in tools:
            if tool not in available_tools:
                warnings.append(f"Tool '{tool}' may not be available")

    # Validate .mcp.json if base_path provided
    if base_path:
        mcp_path = base_path / ".mcp.json"
        if mcp_path.exists():
            try:
                mcp_config = json.loads(mcp_path.read_text())
                if not isinstance(mcp_config, dict):
                    errors.append(".mcp.json must be a JSON object")
                else:
                    # Check MCP servers exist in system config
                    system_mcp = get_mcp_server_names()
                    for server_name in mcp_config.keys():
                        if server_name not in system_mcp:
                            warnings.append(f"MCP server '{server_name}' not in system config")
            except json.JSONDecodeError as e:
                errors.append(f".mcp.json: invalid JSON - {e}")

        # Check system_prompt in config.yaml
        config_path = base_path / "config.yaml"
        if config_path.exists():
            config_dict = yaml.safe_load(config_path.read_text()) or {}
            if "system_prompt" not in config_dict:
                warnings.append("No system_prompt in config.yaml - will use default")

    return SubagentValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )


def _is_valid_name(name: str) -> bool:
    """Check if subagent name is valid."""
    import re

    return bool(re.match(r"^[a-zA-Z0-9_-]+$", name))


def _is_valid_model(model: str) -> bool:
    """Check if model identifier is valid format."""
    # Simple check - provider:model format
    return ":" in model or model.startswith(".")
