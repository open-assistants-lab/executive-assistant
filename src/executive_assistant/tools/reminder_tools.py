"""Reminder tools for the agent.

Tools for setting, listing, and canceling reminders.
Uses dateparser for flexible natural language date/time parsing.
"""

import re
from datetime import datetime

from langchain_core.tools import tool
import dateparser

from executive_assistant.config.settings import settings
from executive_assistant.storage.db_storage import get_thread_id
from executive_assistant.storage.reminder import ReminderStorage, get_reminder_storage
from executive_assistant.storage.meta_registry import record_reminder_count


async def _get_storage() -> ReminderStorage:
    """Get reminder storage instance."""
    return await get_reminder_storage()


async def _refresh_reminder_meta(thread_id: str) -> None:
    """Refresh reminder count in meta registry."""
    try:
        storage = await _get_storage()
        reminders = await storage.list_by_user(thread_id, None)
        record_reminder_count(thread_id, len(reminders))
    except Exception:
        return


def _parse_time_expression(time_str: str) -> datetime:
    """Parse time expressions using dateparser.

    Supports many natural language formats:
    - Relative: "in 30 minutes", "in 2 hours", "in 3 days", "next week"
    - Days: "today", "tomorrow", "yesterday"
    - Combined: "today at 1:30pm", "tomorrow at 9am", "today 15:30"
    - Time only: "1:30pm", "3pm", "15:30" (assumes today, or tomorrow if passed)
    - Full datetime: "2025-01-15 14:00", "15 Jan 2025 2pm"
    - Relative dates: "next monday", "last friday", "in 2 weeks"

    Args:
        time_str: Time expression to parse

    Returns:
        datetime object representing the parsed time

    Raises:
        ValueError: If the time expression cannot be parsed
    """
    time_str = time_str.strip()
    now = datetime.now()

    # Configuration for dateparser
    settings_config = {
        'PREFER_DATES_FROM': 'future',
        'RELATIVE_BASE': now,
        'STRICT_PARSING': False,
        'REQUIRE_PARTS': ['day'],  # At least day part required
    }

    # First try: use dateparser for most natural language expressions
    parsed = dateparser.parse(time_str, settings=settings_config)

    if parsed:
        # If parsed time is in the past and no explicit date was given, assume future
        # Check if the input seems like just a time (no date keywords)
        date_keywords = {'today', 'tomorrow', 'yesterday', 'next', 'last', 'in',
                        'week', 'month', 'year', 'monday', 'tuesday', 'wednesday',
                        'thursday', 'friday', 'saturday', 'sunday', 'jan', 'feb',
                        'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct',
                        'nov', 'dec', '-', '/'}

        has_date_keyword = any(word in time_str.lower() for word in date_keywords)

        # If it looks like just a time and is in the past, move to tomorrow
        if parsed < now and not has_date_keyword:
            # Check if original input looks like just a time
            time_match = re.match(r'^\d{1,2}(:\d{2})?\s*(am|pm)?$', time_str.lower())
            if time_match:
                # Add one day
                from datetime import timedelta
                parsed += timedelta(days=1)

        if parsed:
            return parsed

    # Fallback for military time format like "1130hr", "1430hr" (edge case)
    military_match = re.search(r'(\d{4})hr\b', time_str)
    if military_match:
        time_digits = military_match.group(1)
        hour = int(time_digits[:2])
        minute = int(time_digits[2:])
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            parsed_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if parsed_time < now:
                from datetime import timedelta
                parsed_time += timedelta(days=1)
            return parsed_time

    # Fallback for 4-digit military time without "hr" suffix
    if re.match(r'^\d{4}$', time_str):
        hour = int(time_str[:2])
        minute = int(time_str[2:])
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            parsed_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if parsed_time < now:
                from datetime import timedelta
                parsed_time += timedelta(days=1)
            return parsed_time

    raise ValueError(
        f"Could not parse time expression '{time_str}'. "
        "Try formats like: 'in 30 minutes', 'in 2 hours', 'today at 1:30pm', "
        "'tomorrow at 9am', 'next monday', '1:30pm', '15:30', '2025-01-15 14:00'"
    )


@tool
async def reminder_set(
    message: str,
    time: str,
    recurrence: str = "",
) -> str:
    """Set a reminder for the user.

    Args:
        message: The reminder message (what to remind about)
        time: When to remind. Flexible formats supported via dateparser:
            - Relative: "in 30 minutes", "in 2 hours", "in 3 days", "next week"
            - Day + time: "today at 1:30pm", "tomorrow at 9am", "today 15:30"
            - Time only: "1:30pm", "3pm", "15:30" (assumes today/tomorrow)
            - Relative dates: "next monday", "next friday at 2pm"
            - Numeric: "0130hr" (1:30 AM), "1430hr" (2:30 PM)
            - Full date: "2025-01-15 14:00", "15 Jan 2025 2pm"
        recurrence: Optional recurrence pattern (e.g., "daily", "weekly", "daily at 9am")

    Returns:
        Confirmation message with reminder ID
    """
    storage = await _get_storage()
    thread_id = get_thread_id()

    if thread_id is None:
        return "Error: Could not determine conversation context for reminder."

    try:
        due_time = _parse_time_expression(time)
    except ValueError as e:
        return str(e)

    # Use thread_id as user_id for non-merged users
    user_id = thread_id

    reminder = await storage.create(
        user_id=user_id,
        thread_ids=[thread_id],
        message=message,
        due_time=due_time,
        recurrence=recurrence or None,
    )

    await _refresh_reminder_meta(thread_id)
    recurrence_str = f" (recurring: {recurrence})" if recurrence else ""
    return f"Reminder set for {due_time.strftime('%Y-%m-%d %H:%M')}{recurrence_str}. ID: {reminder.id}"


@tool
async def reminder_list(
    status: str = "",
) -> str:
    """List all reminders for the current user.

    Args:
        status: Filter by status ('pending', 'sent', 'cancelled', 'failed'). Empty for all.

    Returns:
        Formatted list of reminders
    """
    storage = await _get_storage()
    thread_id = get_thread_id()

    if thread_id is None:
        return "Error: Could not determine conversation context."

    user_id = thread_id

    # Validate status if provided
    valid_statuses = {"pending", "sent", "cancelled", "failed"}
    if status and status not in valid_statuses:
        return f"Invalid status. Use one of: {', '.join(valid_statuses)}"

    reminders = await storage.list_by_user(user_id, status or None)

    if not reminders:
        return "No reminders found."

    record_reminder_count(thread_id, len(reminders))
    lines = [f"{'ID':<5} {'Status':<10} {'Due Time':<20} {'Message'}"]
    lines.append("-" * 80)

    for r in reminders:
        due_str = r.due_time.strftime("%Y-%m-%d %H:%M")
        recurrence_str = " (recurring)" if r.is_recurring else ""
        lines.append(f"{r.id:<5} {r.status:<10} {due_str:<20} {r.message}{recurrence_str}")

    return "\n".join(lines)


@tool
async def reminder_cancel(
    reminder_id: int,
) -> str:
    """Cancel a pending reminder.

    Args:
        reminder_id: The ID of the reminder to cancel

    Returns:
        Confirmation message
    """
    storage = await _get_storage()
    thread_id = get_thread_id()

    if thread_id is None:
        return "Error: Could not determine conversation context."

    # Verify the reminder belongs to this user
    reminder = await storage.get_by_id(reminder_id)

    if not reminder:
        return f"Reminder {reminder_id} not found."

    user_id = thread_id
    if reminder.user_id != user_id:
        return "You can only cancel your own reminders."

    if reminder.status != "pending":
        return f"Reminder {reminder_id} is not pending (status: {reminder.status})."

    await storage.cancel(reminder_id)
    await _refresh_reminder_meta(thread_id)
    return f"Reminder {reminder_id} cancelled."


@tool
async def reminder_edit(
    reminder_id: int,
    message: str = "",
    time: str = "",
) -> str:
    """Edit an existing reminder.

    Args:
        reminder_id: The ID of the reminder to edit
        message: New reminder message (leave empty to keep current)
        time: New due time (leave empty to keep current)

    Returns:
        Confirmation message
    """
    storage = await _get_storage()
    thread_id = get_thread_id()

    if thread_id is None:
        return "Error: Could not determine conversation context."

    # Verify ownership
    reminder = await storage.get_by_id(reminder_id)

    if not reminder:
        return f"Reminder {reminder_id} not found."

    user_id = thread_id
    if reminder.user_id != user_id:
        return "You can only edit your own reminders."

    if reminder.status != "pending":
        return f"Reminder {reminder_id} is not pending (status: {reminder.status})."

    # Parse new values
    new_message = message if message else None
    new_due_time = None

    if time:
        try:
            new_due_time = _parse_time_expression(time)
        except ValueError as e:
            return str(e)

    updated = await storage.update(reminder_id, new_message, new_due_time)

    if updated:
        await _refresh_reminder_meta(thread_id)
        changes = []
        if new_message:
            changes.append(f"message to '{new_message}'")
        if new_due_time:
            changes.append(f"time to {new_due_time.strftime('%Y-%m-%d %H:%M')}")

        change_str = " and ".join(changes) if changes else "nothing"
        return f"Reminder {reminder_id} updated: {change_str}."
    else:
        return "Failed to update reminder."


def get_reminder_tools() -> list:
    """Get all reminder tools."""
    return [reminder_set, reminder_list, reminder_cancel, reminder_edit]
