"""Checkpoint validation and recovery utilities.

Detects and recovers from corrupted conversation states where:
- AIMessage has tool_calls but no following ToolMessage responses
- Messages are in an invalid order for the LLM API
"""

from typing import Any
from langchain_core.messages import AIMessage, ToolMessage, BaseMessage


def detect_corrupted_messages(messages: list[BaseMessage]) -> list[str] | None:
    """
    Detect corrupted message state.

    Returns list of descriptions of issues found, or None if state is valid.
    """
    issues = []

    if not messages:
        return None

    # Check for AIMessage with tool_calls not followed by ToolMessage responses
    for i, msg in enumerate(messages):
        if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls") and msg.tool_calls:
            # Get the tool_call IDs from this message
            tool_call_ids = {tc.get("id") for tc in msg.tool_calls if tc.get("id")}

            # Check if all tool_calls have corresponding ToolMessage responses
            if tool_call_ids:
                # Look at subsequent messages for ToolMessage responses
                next_messages = messages[i+1:] if i+1 < len(messages) else []

                # Collect tool_call_ids from ToolMessages
                responded_ids = set()
                for next_msg in next_messages:
                    if isinstance(next_msg, ToolMessage) and hasattr(next_msg, "tool_call_id"):
                        responded_ids.add(next_msg.tool_call_id)

                # Find tool_call_ids that weren't responded to
                unresponded = tool_call_ids - responded_ids
                if unresponded:
                    issues.append(
                        f"Message {i}: AIMessage has {len(unresponded)} tool_calls "
                        f"without corresponding ToolMessage responses (IDs: {list(unresponded)[:2]}...)"
                    )

    return issues if issues else None


def sanitize_corrupted_messages(messages: list[BaseMessage]) -> tuple[list[BaseMessage], list[str]]:
    """
    Attempt to sanitize corrupted message state.

    Strategy:
    1. Remove AIMessages with tool_calls that have no responses
    2. Remove orphaned ToolMessages (no preceding AIMessage)
    3. Ensure message sequence is valid

    Returns:
        Tuple of (sanitized_messages, list_of_actions_taken)
    """
    sanitized = list(messages)
    actions = []

    # Step 1: Find and mark AIMessages with unresponded tool_calls
    to_remove = set()

    # Build a map of tool_call_id -> index of AIMessage that made it
    tool_call_to_ai_idx = {}
    for i, msg in enumerate(sanitized):
        if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                if tc.get("id"):
                    tool_call_to_ai_idx[tc["id"]] = i

    # Find ToolMessages and verify their parent AIMessage exists
    # Also find orphaned ToolMessages
    orphaned_tool_messages = set()
    for i, msg in enumerate(sanitized):
        if isinstance(msg, ToolMessage) and hasattr(msg, "tool_call_id"):
            tc_id = msg.tool_call_id
            if tc_id not in tool_call_to_ai_idx:
                orphaned_tool_messages.add(i)
                actions.append(f"Removed orphaned ToolMessage at index {i} (no parent AIMessage)")

    # Find AIMessages with tool_calls that were never responded to
    tool_calls_responded = set()
    for i, msg in enumerate(sanitized):
        if isinstance(msg, ToolMessage) and hasattr(msg, "tool_call_id"):
            tc_id = msg.tool_call_id
            if tc_id in tool_call_to_ai_idx:
                tool_calls_responded.add(tool_call_to_ai_idx[tc_id])

    for i, msg in enumerate(sanitized):
        if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls") and msg.tool_calls:
            # Check if any of this AIMessage's tool_calls were responded to
            has_response = i in tool_calls_responded
            if not has_response:
                to_remove.add(i)
                actions.append(
                    f"Removed AIMessage at index {i} with {len(msg.tool_calls)} "
                    f"unresponded tool_calls"
                )

    # Add orphaned ToolMessages to removal set
    to_remove.update(orphaned_tool_messages)

    # Remove messages in reverse order to preserve indices
    for idx in sorted(to_remove, reverse=True):
        del sanitized[idx]

    if not actions:
        actions.append("No issues found - state is valid")

    return sanitized, actions


async def validate_and_recover_checkpoint(
    state: dict[str, Any],
    thread_id: str | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """
    Validate checkpoint state and attempt recovery if corrupted.

    Args:
        state: Current agent state with messages
        thread_id: Optional thread_id for logging

    Returns:
        Tuple of (potentially_fixed_state, list_of_actions_taken)
    """
    messages = state.get("messages", [])

    issues = detect_corrupted_messages(messages)

    if not issues:
        # No issues found
        return state, ["Checkpoint state is valid"]

    # Issues found - attempt to sanitize
    sanitized, actions = sanitize_corrupted_messages(messages)

    # If we made changes, update the state
    if len(sanitized) != len(messages):
        actions.insert(0, f"Found {len(issues)} issue(s) in checkpoint state")
        new_state = dict(state)
        new_state["messages"] = sanitized
        return new_state, actions

    # Couldn't auto-fix - recommend reset
    return state, issues + ["Could not auto-recover - recommend /reset command"]


def should_propose_before_action(action_name: str, args: dict[str, Any]) -> bool:
    """
    Determine if an action should be proposed to user before executing.

    Large or destructive operations should require confirmation:
    - kb_store with many documents
    - Operations that write/delete multiple files
    - Any operation with 'force', 'delete', 'drop' in name

    Args:
        action_name: Name of the tool being called
        args: Arguments passed to the tool

    Returns:
        True if user confirmation should be sought first
    """
    # Destructive operations
    destructive_keywords = ["delete", "drop", "remove", "force"]
    if any(kw in action_name.lower() for kw in destructive_keywords):
        return True

    # kb_store with many documents
    if action_name == "kb_store":
        try:
            import json
            documents = json.loads(args.get("documents", "[]"))
            if len(documents) > 5:  # More than 5 documents = significant operation
                return True
        except (json.JSONDecodeError, TypeError):
            pass

    # db_create_table with many rows
    if action_name == "db_create_table":
        try:
            import json
            data = json.loads(args.get("data", "[]"))
            if len(data) > 10:  # More than 10 rows
                return True
        except (json.JSONDecodeError, TypeError):
            pass

    return False


def format_proposal(action_name: str, args: dict[str, Any]) -> str:
    """
    Format a proposal message for user confirmation.

    Args:
        action_name: Name of the tool being called
        args: Arguments passed to the tool

    Returns:
        Formatted proposal message
    """
    lines = [
        "📋 *Proposed Action*",
        "",
    ]

    # Describe the action
    if action_name == "kb_store":
        import json
        try:
            documents = json.loads(args.get("documents", "[]"))
            table_name = args.get("table_name", "?")
            lines.append(f"• Store {len(documents)} documents in KB table '{table_name}'")
        except:
            lines.append(f"• Store documents in KB table '{args.get('table_name', '?')}'")

    elif action_name == "db_create_table":
        import json
        try:
            data = json.loads(args.get("data", "[]"))
            table_name = args.get("table_name", "?")
            lines.append(f"• Create table '{table_name}' with {len(data)} rows")
        except:
            lines.append(f"• Create table '{args.get('table_name', '?')}'")

    else:
        # Generic action description
        lines.append(f"• {action_name}")

    lines.extend([
        "",
        "Reply 'yes' to confirm, 'no' to cancel, or 'modify' to change something.",
    ])

    return "\n".join(lines)
