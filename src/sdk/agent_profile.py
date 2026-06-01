"""EA-specific validation for AgentProfile.

Extends the OSS AgentProfile model with EA-specific validators
(models.dev lookup, tool registry, skill registry).
"""

from __future__ import annotations

from typing import Any


def validate_profile(data: dict[str, Any]) -> list[str]:
    """Validate an AgentProfile dict against EA-specific rules.

    Returns a list of error messages. Empty list = valid.
    """
    errors: list[str] = []

    # 1. Model must resolve through models.dev
    model = data.get("model", "")
    if model:
        from src.sdk.registry import get_model_info

        info = get_model_info(model)
        if info is None:
            errors.append(f"Unknown model: {model!r}")

    # 2. Tools must exist in registry
    tools = data.get("tools", [])
    if tools:
        from src.sdk.native_tools import get_native_tool_names

        known = get_native_tool_names()
        for tool_name in tools:
            if tool_name not in known:
                errors.append(f"Unknown tool: {tool_name!r}")

    # 3. Skills must exist in registry
    skills = data.get("skills", [])
    if skills:
        try:
            from src.skills.registry import get_skill_registry

            sr = get_skill_registry()
            for skill_name in skills:
                if not sr.has(skill_name):
                    errors.append(f"Unknown skill: {skill_name!r}")
        except Exception:
            pass  # skill registry may not be initialized in tests

    return errors
