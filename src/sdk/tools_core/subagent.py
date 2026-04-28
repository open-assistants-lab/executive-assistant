"""Subagent tools — V1 SDK-native implementation with work_queue coordination.

8 tools:
    subagent_create   — create AgentDef, persist to disk
    subagent_update   — amend existing AgentDef (partial update)
    subagent_invoke   — insert task into work_queue + run immediately
    subagent_list     — list user's AgentDefs + their running tasks
    subagent_progress — check progress/status of tasks
    subagent_instruct — course-correct a running subagent
    subagent_cancel    — kill a running subagent
    subagent_delete   — remove AgentDef + cancel any running tasks
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from src.app_logging import get_logger
from src.sdk.subagent_models import AgentDef
from src.sdk.tools import ToolAnnotations, tool

logger = get_logger()


@tool
def subagent_create(
    name: str,
    user_id: str,
    description: str = "",
    model: str | None = None,
    tools: list[str] | None = None,
    system_prompt: str | None = None,
    skills: list[str] | None = None,
    max_llm_calls: int = 50,
    cost_limit_usd: float = 1.0,
    timeout_seconds: int = 300,
    mcp_config: str | None = None,
) -> str:
    """Create a new subagent with specified configuration.

    Args:
        name: Unique name for the subagent (alphanumeric, hyphens, underscores)
        user_id: The user ID (required)
        description: What this subagent does (shown to LLM for routing)
        model: Model to use (e.g., 'anthropic:claude-sonnet-4-20250514')
        tools: List of tool names to allow (None = all native tools)
        system_prompt: Custom system prompt
        skills: List of skill names to inject
        max_llm_calls: Per-task LLM call limit (default 50)
        cost_limit_usd: Per-task cost limit in USD (default 1.0)
        timeout_seconds: Per-task hard wall-clock timeout (default 300)
        mcp_config: MCP servers as JSON string

    Returns:
        Success message or validation errors
    """
    mcp_dict = None
    if mcp_config:
        try:
            mcp_dict = json.loads(mcp_config)
        except json.JSONDecodeError as e:
            return f"Error: Invalid MCP config JSON: {e}"

    if skills is None:
        skills = []

    agent_def = AgentDef(
        name=name,
        description=description,
        model=model,
        system_prompt=system_prompt,
        tools=tools,
        skills=skills,
        max_llm_calls=max_llm_calls,
        cost_limit_usd=cost_limit_usd,
        timeout_seconds=timeout_seconds,
        mcp_config=mcp_dict,
    )

    from src.sdk.coordinator import get_coordinator

    coordinator = get_coordinator(user_id)

    existing = coordinator.load_def(name)
    if existing is not None:
        return f"Error: Subagent '{name}' already exists. Use subagent_update to amend it."

    try:
        asyncio.get_running_loop()
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, coordinator.create(agent_def))
            future.result()
    except RuntimeError:
        asyncio.run(coordinator.create(agent_def))

    lines = [f"Subagent '{name}' created successfully."]
    if model:
        lines.append(f"Model: {model}")
    if tools:
        lines.append(f"Tools: {', '.join(tools)}")
    lines.append(f"Max LLM calls: {max_llm_calls}, Cost limit: ${cost_limit_usd}")

    return "\n".join(lines)


subagent_create.annotations = ToolAnnotations(title="Create Subagent", destructive=True)


@tool
def subagent_update(
    name: str,
    user_id: str,
    model: str | None = None,
    description: str | None = None,
    tools: list[str] | None = None,
    system_prompt: str | None = None,
    skills: list[str] | None = None,
    max_llm_calls: int | None = None,
    cost_limit_usd: float | None = None,
    timeout_seconds: int | None = None,
    mcp_config: str | None = None,
) -> str:
    """Amend an existing subagent. Only specified fields are updated.

    Args:
        name: Subagent name to update
        user_id: The user ID (required)
        model: New model override
        description: New description
        tools: New tool allowlist (replaces entirely)
        system_prompt: New system prompt
        skills: New skills list (replaces entirely)
        max_llm_calls: New LLM call limit
        cost_limit_usd: New cost limit
        timeout_seconds: New timeout
        mcp_config: New MCP config as JSON string

    Returns:
        Confirmation message
    """
    from src.sdk.coordinator import get_coordinator

    coordinator = get_coordinator(user_id)
    existing = coordinator.load_def(name)
    if existing is None:
        return f"Error: Subagent '{name}' not found."

    update_kwargs: dict[str, Any] = {}
    if model is not None:
        update_kwargs["model"] = model
    if description is not None:
        update_kwargs["description"] = description
    if tools is not None:
        update_kwargs["tools"] = tools
    if system_prompt is not None:
        update_kwargs["system_prompt"] = system_prompt
    if skills is not None:
        update_kwargs["skills"] = skills
    if max_llm_calls is not None:
        update_kwargs["max_llm_calls"] = max_llm_calls
    if cost_limit_usd is not None:
        update_kwargs["cost_limit_usd"] = cost_limit_usd
    if timeout_seconds is not None:
        update_kwargs["timeout_seconds"] = timeout_seconds
    if mcp_config is not None:
        try:
            update_kwargs["mcp_config"] = json.loads(mcp_config)
        except json.JSONDecodeError as e:
            return f"Error: Invalid MCP config JSON: {e}"

    if not update_kwargs:
        return f"No fields specified to update for subagent '{name}'."

    try:
        asyncio.get_running_loop()
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, coordinator.update(name, **update_kwargs))
            updated = future.result()
    except RuntimeError:
        updated = asyncio.run(coordinator.update(name, **update_kwargs))

    if updated is None:
        return f"Error: Failed to update subagent '{name}'."

    return f"Subagent '{name}' updated: {', '.join(update_kwargs.keys())}"


subagent_update.annotations = ToolAnnotations(title="Update Subagent", destructive=True)


@tool
def subagent_invoke(
    agent_name: str,
    task: str,
    user_id: str,
    parent_id: str | None = None,
) -> str:
    """Invoke a subagent to execute a task. Returns task ID immediately.

    The subagent runs in the background. Use subagent_progress to check status.
    Use subagent_instruct to send course-corrections.
    Use subagent_cancel to kill a stuck or misbehaving subagent.

    Args:
        agent_name: Name of the subagent to invoke
        task: Task description/prompt
        user_id: The user ID (required)
        parent_id: Correlation ID to group related tasks

    Returns:
        Task ID and status message
    """
    from src.sdk.coordinator import get_coordinator

    coordinator = get_coordinator(user_id)

    existing = coordinator.load_def(agent_name)
    if existing is None:
        return f"Error: Subagent '{agent_name}' not found. Create it first with subagent_create."

    import concurrent.futures

    def _run() -> str:
        return asyncio.run(coordinator.invoke(agent_name, task, parent_id=parent_id))

    try:
        asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            task_id_str = pool.submit(_run).result()
    except RuntimeError:
        task_id_str = asyncio.run(coordinator.invoke(agent_name, task, parent_id=parent_id))

    return f"""Task submitted for subagent '{agent_name}'.

**Task ID**: {task_id_str}
**Task**: {task[:100]}
**Status**: Running in background...

Use `subagent_progress` with task ID to check status and results."""


subagent_invoke.annotations = ToolAnnotations(title="Invoke Subagent", open_world=True)


@tool
def subagent_list(user_id: str) -> str:
    """List all subagents for the user and their active tasks.

    Args:
        user_id: The user ID (required)

    Returns:
        List of subagents with their configs and active tasks
    """
    from src.sdk.coordinator import get_coordinator

    coordinator = get_coordinator(user_id)

    try:
        asyncio.get_running_loop()
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as pool:
            defs_future = pool.submit(asyncio.run, coordinator.list_defs())
            progress_future = pool.submit(asyncio.run, coordinator.check_progress())
            defs = defs_future.result()
            tasks = progress_future.result()
    except RuntimeError:
        defs = asyncio.run(coordinator.list_defs())
        tasks = asyncio.run(coordinator.check_progress())

    if not defs and not tasks:
        return "No subagents found."

    lines = ["## Subagents\n"]
    for d in defs:
        lines.append(f"### {d.name}")
        if d.description:
            lines.append(f"  {d.description}")
        if d.model:
            lines.append(f"  **Model:** {d.model}")
        if d.tools:
            lines.append(f"  **Tools:** {', '.join(d.tools)}")
        lines.append(f"  **Max LLM calls:** {d.max_llm_calls}, **Cost limit:** ${d.cost_limit_usd}")
        lines.append("")

    if tasks:
        lines.append("## Active Tasks\n")
        for t in tasks:
            status = t.get("status", "unknown")
            name = t.get("agent_name", "unknown")
            task_id = t.get("id", "?")
            lines.append(f"- **{task_id}** ({name}): {status}")

    return "\n".join(lines)


subagent_list.annotations = ToolAnnotations(title="List Subagents", read_only=True, idempotent=True)


@tool
def subagent_progress(
    task_id: str | None = None,
    parent_id: str | None = None,
    user_id: str = "default_user",
) -> str:
    """Check progress/status of subagent tasks.

    Args:
        task_id: Specific task ID to check
        parent_id: Filter tasks by parent correlation ID
        user_id: The user ID (required)

    Returns:
        Task status and progress information
    """
    from src.sdk.coordinator import get_coordinator

    coordinator = get_coordinator(user_id)
    import concurrent.futures

    if task_id:

        async def _get_task() -> dict[str, Any] | None:
            db = await coordinator._get_db()
            return await db.get_task(task_id)

        try:
            asyncio.get_running_loop()
            with concurrent.futures.ThreadPoolExecutor() as pool:
                row = pool.submit(asyncio.run, _get_task()).result()
        except RuntimeError:
            row = asyncio.run(_get_task())

        if row is None:
            return f"No task found with ID: {task_id}"

        progress = json.loads(row.get("progress") or "{}")
        status = row.get("status", "unknown")
        agent_name = row.get("agent_name", "unknown")

        lines = [f"## Task: {task_id}", f"**Agent:** {agent_name}", f"**Status:** {status}"]

        if progress:
            steps = progress.get("steps_completed", 0)
            phase = progress.get("phase", "")
            msg = progress.get("message", "")
            stuck = progress.get("stuck", False)
            lines.append(f"**Steps completed:** {steps}")
            if phase:
                lines.append(f"**Phase:** {phase}")
            if msg:
                lines.append(f"**Last action:** {msg}")
            if stuck:
                lines.append("**STUCK** - doom loop detected")

        if status == "completed":
            result_data = json.loads(row.get("result") or "{}")
            output = result_data.get("output", "")
            truncated = result_data.get("truncated", False)
            lines.append(f"\n**Output:**\n{output[:500]}{'...' if len(output) > 500 else ''}")
            if truncated:
                lines.append("(output truncated)")

        elif status == "failed":
            lines.append(f"\n**Error:** {row.get('error', 'Unknown')}")

        elif status == "cancelled":
            lines.append("\nTask was cancelled by supervisor.")

        return "\n".join(lines)

    else:

        async def _get_progress() -> list[dict[str, Any]]:
            return await coordinator.check_progress(parent_id=parent_id)

        try:
            asyncio.get_running_loop()
            with concurrent.futures.ThreadPoolExecutor() as pool:
                tasks = pool.submit(asyncio.run, _get_progress()).result()
        except RuntimeError:
            tasks = asyncio.run(_get_progress())

        if not tasks:
            return "No active tasks."

        lines = ["## Tasks\n"]
        for t in tasks:
            t_status = t.get("status", "unknown")
            t_name = t.get("agent_name", "unknown")
            tid = t.get("id", "?")
            lines.append(f"- **{tid}** ({t_name}): {t_status}")

        return "\n".join(lines)


subagent_progress.annotations = ToolAnnotations(
    title="Subagent Progress", read_only=True, idempotent=True
)


@tool
def subagent_instruct(
    task_id: str,
    message: str,
    user_id: str,
) -> str:
    """Send a course-correction instruction to a running subagent.

    The instruction is injected as a system message on the subagent's next iteration.

    Args:
        task_id: The task ID to instruct
        message: The instruction message to inject
        user_id: The user ID (required)

    Returns:
        Confirmation message
    """
    from src.sdk.coordinator import get_coordinator

    coordinator = get_coordinator(user_id)

    async def _instruct() -> bool | None:
        db = await coordinator._get_db()
        row = await db.get_task(task_id)
        if row is None:
            return None
        if row.get("status") not in ("pending", "running"):
            return None
        ok = await db.add_instruction(task_id, message)
        return ok

    try:
        asyncio.get_running_loop()
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as pool:
            result = pool.submit(asyncio.run, _instruct()).result()
    except RuntimeError:
        result = asyncio.run(_instruct())

    if result is None:
        return f"Error: Task '{task_id}' not found or not running."
    if not result:
        return f"Error: Failed to send instruction to task '{task_id}'."

    return f"Instruction sent to task '{task_id}': {message[:100]}"


subagent_instruct.annotations = ToolAnnotations(title="Instruct Subagent")


@tool
def subagent_cancel(task_id: str, user_id: str) -> str:
    """Cancel a running or pending subagent task.

    Sets cancel_requested flag. The subagent's InstructionMiddleware will
    raise TaskCancelledError on its next iteration.

    Args:
        task_id: The task ID to cancel
        user_id: The user ID (required)

    Returns:
        Cancellation confirmation
    """
    from src.sdk.coordinator import get_coordinator

    coordinator = get_coordinator(user_id)

    async def _cancel() -> bool:
        return await coordinator.cancel(task_id)

    try:
        asyncio.get_running_loop()
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as pool:
            ok = pool.submit(asyncio.run, _cancel()).result()
    except RuntimeError:
        ok = asyncio.run(_cancel())

    if ok:
        return f"Task '{task_id}' cancellation requested. The subagent will terminate on its next iteration."
    return f"Error: Task '{task_id}' not found."


subagent_cancel.annotations = ToolAnnotations(title="Cancel Subagent", destructive=True)


@tool
def subagent_delete(name: str, user_id: str) -> str:
    """Delete a subagent definition and cancel any running tasks.

    Args:
        name: Subagent name to delete
        user_id: The user ID (required)

    Returns:
        Deletion confirmation
    """
    from src.sdk.coordinator import get_coordinator

    coordinator = get_coordinator(user_id)

    async def _delete() -> bool:
        return await coordinator.delete(name)

    try:
        asyncio.get_running_loop()
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as pool:
            ok = pool.submit(asyncio.run, _delete()).result()
    except RuntimeError:
        ok = asyncio.run(_delete())

    if ok:
        return f"Subagent '{name}' deleted. Any running tasks have been cancelled."
    return f"Error: Subagent '{name}' not found."


subagent_delete.annotations = ToolAnnotations(title="Delete Subagent", destructive=True)
