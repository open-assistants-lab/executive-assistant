import json

from langchain_core.tools import tool

from src.agents.subagent.manager import get_subagent_manager


@tool
def subagent_create(
    name: str,
    user_id: str,
    model: str | None = None,
    description: str = "",
    skills: list[str] | None = None,
    tools: list[str] | None = None,
    system_prompt: str | None = None,
    mcp_config: str | None = None,
) -> str:
    """Create a new subagent with specified configuration.

    Args:
        name: Subagent name (alphanumeric, hyphens, underscores)
        user_id: The user ID (required)
        model: Model to use (e.g., "anthropic:claude-sonnet-4-20250514")
        description: What this subagent does
        skills: List of skill names to assign
        tools: List of tool names to assign
        system_prompt: Custom system prompt
        mcp_config: MCP servers as JSON string

    Returns:
        Success message or validation errors
    """
    # Parse MCP config if provided
    mcp_dict = None
    if mcp_config:
        try:
            mcp_dict = json.loads(mcp_config)
        except json.JSONDecodeError as e:
            return f"Error: Invalid MCP config JSON: {e}"

    manager = get_subagent_manager(user_id)

    subagent, result = manager.create(
        name=name,
        model=model,
        description=description,
        skills=skills or [],
        tools=tools or [],
        system_prompt=system_prompt,
        mcp_config=mcp_dict,
    )

    if not result["valid"]:
        errors = "\n".join(f"- {e}" for e in result["errors"])
        warnings = "\n".join(f"- {w}" for w in result.get("warnings", []))
        return f"Validation failed:\n{errors}\n\nWarnings:\n{warnings}"

    warnings = ""
    if result.get("warnings"):
        warnings = "\nWarnings:\n" + "\n".join(f"- {w}" for w in result["warnings"])

    return f"Subagent '{name}' created successfully.{warnings}"


@tool
def subagent_invoke(name: str, task: str, user_id: str) -> str:
    """Invoke a subagent to execute a task.

    Args:
        name: Subagent name
        task: Task description
        user_id: The user ID (required)

    Returns:
        Subagent execution result
    """
    manager = get_subagent_manager(user_id)

    result = manager.invoke(name, task)

    if not result["success"]:
        return f"Error: {result['error']}"

    return result["output"]


@tool
def subagent_list(user_id: str) -> str:
    """List all subagents for the user.

    Args:
        user_id: The user ID (required)

    Returns:
        List of subagents
    """
    manager = get_subagent_manager(user_id)

    subagents = manager.list_all()

    if not subagents:
        return "No subagents found."

    lines = ["## Subagents\n"]
    for sa in subagents:
        lines.append(f"### {sa['name']}")
        if sa.get("description"):
            lines.append(f"{sa['description']}")
        if sa.get("model"):
            lines.append(f"**Model:** {sa['model']}")
        if sa.get("skills"):
            lines.append(f"**Skills:** {', '.join(sa['skills'])}")
        if sa.get("tools"):
            lines.append(f"**Tools:** {', '.join(sa['tools'])}")
        lines.append("")

    return "\n".join(lines)


@tool
def subagent_progress(task_name: str, user_id: str) -> str:
    """Get subagent progress from planning files.

    Args:
        task_name: Name of the planning task
        user_id: The user ID (required)

    Returns:
        Progress information
    """
    manager = get_subagent_manager(user_id)

    progress = manager.get_progress(task_name)

    if not progress["exists"]:
        return f"No planning files found for task: {task_name}"

    lines = [f"## Progress: {task_name}\n"]

    if progress.get("task_plan"):
        lines.append("### Task Plan")
        lines.append(progress["task_plan"])
        lines.append("")

    if progress.get("progress"):
        lines.append("### Progress")
        lines.append(progress["progress"])
        lines.append("")

    if progress.get("findings"):
        lines.append("### Findings")
        lines.append(progress["findings"])
        lines.append("")

    return "\n".join(lines)


@tool
def subagent_validate(name: str, user_id: str) -> str:
    """Validate a subagent configuration.

    Args:
        name: Subagent name
        user_id: The user ID (required)

    Returns:
        Validation result
    """
    # Import validation directly
    from src.agents.subagent.validation import validate_subagent_config

    base_path = f"data/users/{user_id}/subagents/{name}"
    import os

    if not os.path.exists(base_path):
        return f"Subagent '{name}' does not exist."

    from pathlib import Path

    config_path = Path(base_path) / "config.yaml"
    if not config_path.exists():
        return f"Subagent '{name}' has no config.yaml."

    import yaml

    config_dict = yaml.safe_load(config_path.read_text()) or {}

    result = validate_subagent_config(user_id, config_dict, Path(base_path))

    if result.valid:
        lines = [f"✅ Subagent '{name}' is valid"]
        if result.warnings:
            lines.append("\nWarnings:")
            for w in result.warnings:
                lines.append(f"  - {w}")
        return "\n".join(lines)

    lines = [f"❌ Subagent '{name}' has errors:"]
    for e in result.errors:
        lines.append(f"  - {e}")
    return "\n".join(lines)
