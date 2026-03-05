import json
import os
import shutil
from pathlib import Path

import yaml
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
def subagent_batch(tasks: str, user_id: str) -> str:
    """Invoke multiple subagents in parallel.

    Args:
        tasks of tasks array: JSON string, e.g. '[{"name": "agent1", "task": "do X"}, {"name": "agent2", "task": "do Y"}]'
        user_id: The user ID (required)

    Returns:
        Results from all subagents
    """
    import json

    try:
        tasks_list = json.loads(tasks)
    except json.JSONDecodeError as e:
        return f"Error: Invalid JSON: {e}"

    if not isinstance(tasks_list, list):
        return "Error: tasks must be a JSON array"

    manager = get_subagent_manager(user_id)

    results = manager.invoke_batch(tasks_list)

    lines = ["## Parallel Subagent Results\n"]
    for i, result in enumerate(results):
        lines.append(f"### Task {i + 1}: {result.get('name', 'unknown')}")
        if result.get("success"):
            lines.append("**Status:** ✅ Success")
            lines.append(f"**Output:** {result.get('output', '')[:500]}")
        else:
            lines.append("**Status:** ❌ Failed")
            lines.append(f"**Error:** {result.get('error', 'Unknown error')}")
        lines.append("")

    return "\n".join(lines)


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

    if not os.path.exists(base_path):
        return f"Subagent '{name}' does not exist."

    config_path = Path(base_path) / "config.yaml"
    if not config_path.exists():
        return f"Subagent '{name}' has no config.yaml."

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


@tool
def subagent_schedule(
    subagent_name: str,
    task: str,
    schedule: str,
    user_id: str,
    run_at: str | None = None,
) -> str:
    """Schedule a subagent to run once or on a recurring basis.

    Args:
        subagent_name: Name of the subagent to schedule
        task: Task description
        schedule: "once" for one-time, or cron expression (e.g., "0 9 * * *" for daily 9am)
        user_id: The user ID (required)
        run_at: ISO datetime for "once" schedule (e.g., "2024-01-15T10:00:00")

    Returns:
        Scheduling confirmation with job ID
    """
    from datetime import datetime

    from src.agents.subagent.scheduler import schedule_once, schedule_recurring

    try:
        if schedule == "once":
            if not run_at:
                return "Error: run_at is required for 'once' schedule"
            run_time = datetime.fromisoformat(run_at)
            job_id = schedule_once(user_id, subagent_name, task, run_time)
            return f"✅ Scheduled one-time job {job_id}\nSubagent: {subagent_name}\nTask: {task}\nRun at: {run_at}"
        else:
            # Treat as cron expression
            job_id = schedule_recurring(user_id, subagent_name, task, schedule)
            return f"✅ Scheduled recurring job {job_id}\nSubagent: {subagent_name}\nTask: {task}\nCron: {schedule}"
    except ValueError as e:
        return f"Error: {e}"


@tool
def subagent_schedule_cancel(job_id: str, user_id: str) -> str:
    """Cancel a scheduled subagent job.

    Args:
        job_id: Job ID to cancel
        user_id: The user ID (required)

    Returns:
        Cancellation confirmation
    """
    from src.agents.subagent.scheduler import cancel_job

    if cancel_job(job_id):
        return f"✅ Job {job_id} cancelled"
    return f"Job {job_id} not found"


@tool
def subagent_schedule_list(user_id: str) -> str:
    """List all scheduled subagent jobs.

    Args:
        user_id: The user ID (required)

    Returns:
        List of scheduled jobs
    """
    from src.agents.subagent.scheduler import list_jobs

    jobs = list_jobs(user_id)

    if not jobs:
        return "No scheduled jobs."

    lines = ["## Scheduled Jobs\n"]
    for job in jobs:
        lines.append(f"### {job['job_id']}")
        lines.append(f"**Subagent:** {job.get('subagent_name', 'unknown')}")
        lines.append(f"**Task:** {job.get('task', '')[:50]}...")
        lines.append(f"**Status:** {job.get('status', 'unknown')}")
        if job.get("schedule_type") == "once":
            lines.append(f"**Run at:** {job.get('run_at', 'unknown')}")
        else:
            lines.append(f"**Cron:** {job.get('cron', 'unknown')}")
        lines.append("")

    return "\n".join(lines)


@tool
def subagent_delete(name: str, user_id: str) -> str:
    """Delete a subagent.

    Args:
        name: Subagent name to delete
        user_id: The user ID (required)

    Returns:
        Deletion confirmation
    """
    from src.agents.subagent.manager import get_subagent_manager

    manager = get_subagent_manager(user_id)
    base_path = manager.base_path / name

    if not base_path.exists():
        return f"Subagent '{name}' not found"

    try:
        shutil.rmtree(base_path)
        manager.invalidate_cache(name)
        return f"✅ Subagent '{name}' deleted"
    except Exception as e:
        return f"Error deleting subagent: {e}"


@tool
def telegram_send_message_tool(user_id: str, message: str) -> str:
    """Send a message to the user via Telegram.

    Args:
        user_id: The user ID (required)
        message: Message text to send

    Returns:
        Confirmation or error
    """
    from src.telegram.main import telegram_send_message as send_msg

    return send_msg(user_id, message)


@tool
def telegram_send_file_tool(user_id: str, file_path: str, caption: str = "") -> str:
    """Send a file to the user via Telegram.

    Args:
        user_id: The user ID (required)
        file_path: Path to file (relative to workspace)
        caption: Optional caption for the file

    Returns:
        Confirmation or error
    """
    from src.telegram.main import telegram_send_file as send_file

    return send_file(user_id, file_path, caption)
