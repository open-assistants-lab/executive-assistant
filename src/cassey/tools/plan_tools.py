"""Plan tools for thread-scoped task planning.

These tools provide a planning system for multi-step tasks with:
- init_plan: Create a new plan from templates
- read_plan: Read a plan file (task_plan, findings, progress)
- write_plan: Write content to a plan file
- update_plan: Update a specific section in a plan file
- clear_plan: Clear current plan files
- list_plans: List current and archived plans

Plan files are stored under data/users/{thread_id}/plan/ and are
strictly separated from user files (not visible via list_files, etc.).
"""

from langchain_core.tools import tool

from cassey.storage.plan_storage import get_plan_storage


@tool
def init_plan(task_title: str, force_new: bool = False) -> str:
    """
    Initialize a new planning workspace for a multi-step task.

    Creates three plan files from templates:
    - task_plan.md: Roadmap with phases, decisions, errors
    - findings.md: Research findings and technical decisions
    - progress.md: Session log, test results, error log

    Use this for complex tasks that require:
    - 3+ steps or phases
    - Research or exploration
    - Multi-turn work across sessions
    - Tracking decisions and errors

    For simple Q&A or single-file edits, skip planning.

    Args:
        task_title: Brief description of the task (e.g., "Create Python CLI todo app")
        force_new: If True, overwrite existing plan. If False, archives completed plans first.

    Returns:
        Confirmation message with created file paths.

    Examples:
        >>> init_plan("Build a REST API for task management")
        "Plan initialized. Files created: task_plan.md, findings.md, progress.md"
    """
    storage = get_plan_storage()
    result = storage.initialize_plan(task_title, force_new=force_new)

    if result["status"] == "existing":
        return f"Plan already exists. Use force_new=True to start fresh, or read existing plan:\n{result['task_plan']}"

    return f"""Plan initialized: {task_title}

Files created:
- task_plan.md (roadmap with phases)
- findings.md (research & decisions)
- progress.md (session log)

Next steps:
1. Update task_plan.md with your phases
2. Start with Phase 1: Requirements & Discovery
3. Log findings to findings.md as you discover them
4. Update progress.md as you complete phases"""


@tool
def read_plan(which: str = "task_plan") -> str:
    """
    Read a plan file.

    Args:
        which: Which plan file to read:
            - "task_plan": Main roadmap with phases, decisions, errors (default)
            - "findings": Research findings and technical decisions
            - "progress": Session log, test results, error log

    Returns:
        File contents.

    Examples:
        >>> read_plan()
        "# Task Plan: Build a REST API\\n\\n## Goal..."

        >>> read_plan("findings")
        "# Findings & Decisions\\n\\n## Requirements..."
    """
    storage = get_plan_storage()

    try:
        content = storage.read_plan(which)
        return content
    except FileNotFoundError as e:
        return f"Plan file not found. Use init_plan() first. ({e})"


@tool
def write_plan(which: str, content: str) -> str:
    """
    Write content to a plan file.

    Replaces the entire file content with the provided content.

    Args:
        which: Which plan file to write (task_plan, findings, progress).
        content: Full content to write to the file.

    Returns:
        Success message.

    Examples:
        >>> write_plan("task_plan", "# Task Plan: New Task\\n...")
        "Plan file updated: task_plan.md"
    """
    storage = get_plan_storage()
    return storage.write_plan(which, content)


@tool
def update_plan(which: str, section: str, content: str) -> str:
    """
    Update a specific section in a plan file.

    Finds the section heading and replaces its content while preserving
    other sections. Creates the section if not found.

    Args:
        which: Which plan file to update (task_plan, findings, progress).
        section: Section heading (without ## symbols).
            Examples: "Goal", "Phases", "Research Findings", "Error Log"
        content: New content for the section (markdown formatted).

    Returns:
        Success message.

    Examples:
        >>> update_plan("task_plan", "Goal", "Build a REST API with user authentication")
        "Section 'Goal' updated in task_plan.md"

        >>> update_plan("findings", "Research Findings", "- Python's FastAPI is recommended\\n- PostgreSQL for data")
        "Section 'Research Findings' updated in findings.md"
    """
    storage = get_plan_storage()
    return storage.update_plan_section(which, section, content)


@tool
def clear_plan(confirm: bool = False) -> str:
    """
    Clear the current plan files.

    Removes task_plan.md, findings.md, and progress.md.
    Archived plans are preserved.

    Args:
        confirm: Must be True to actually clear (safety check).

    Returns:
        Success message or confirmation prompt.

    Examples:
        >>> clear_plan(confirm=True)
        "Plan files cleared (archive preserved)"
    """
    storage = get_plan_storage()
    return storage.clear_plan(confirm=confirm)


@tool
def list_plans() -> str:
    """
    List current and archived plans.

    Returns:
        Formatted list showing current plan status and archived plans.

    Examples:
        >>> list_plans()
        "Current Plan:\\n  Status: active\\n  Completed: false\\n\\nArchived (2):\\n  - plan-20260115-1430.md..."
    """
    storage = get_plan_storage()
    result = storage.list_plans()

    output = ["Current Plan:"]
    if result["current"]["exists"]:
        status = "completed" if result["current"]["completed"] else "active"
        output.append(f"  Status: {status}")
    else:
        output.append("  No active plan")

    if result["archived"]:
        output.append(f"\nArchived ({len(result['archived'])}):")
        for archive in result["archived"][:10]:  # Show last 10
            output.append(f"  - {archive['filename']} ({archive['created']})")

    return "\n".join(output)


def get_plan_tools() -> list:
    """
    Get all plan tools for the agent.

    Returns:
        List of plan-related LangChain tools.
    """
    return [
        init_plan,
        read_plan,
        write_plan,
        update_plan,
        clear_plan,
        list_plans,
    ]
