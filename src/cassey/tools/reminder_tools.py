"""Reminder tools for the agent.

Tools for setting, listing, and canceling reminders.
"""

from datetime import datetime

from langchain_core.tools import tool
from dateutil import parser as date_parser
from dateutil.relativedelta import relativedelta

from cassey.config.settings import settings
from cassey.storage.db_storage import get_thread_id
from cassey.storage.reminder import ReminderStorage, get_reminder_storage


async def _get_storage() -> ReminderStorage:
    """Get reminder storage instance."""
    return await get_reminder_storage()


def _parse_time_expression(time_str: str) -> datetime:
    """Parse time expressions like 'in 30 minutes', 'tomorrow at 9am', 'today at 1:30pm'.

    Supports many natural language formats:
    - Relative: "in 30 minutes", "in 2 hours", "in 3 days"
    - Days: "today", "tomorrow"
    - Combined: "today at 1:30pm", "tomorrow at 9am", "today at 15:30"
    - Time only: "1:30pm", "3pm", "15:30" (assumes today, or tomorrow if passed)
    - Full datetime: "2025-01-15 14:00", "15 Jan 2025 2pm"

    Args:
        time_str: Time expression to parse

    Returns:
        datetime object representing the parsed time

    Raises:
        ValueError: If the time expression cannot be parsed
    """
    time_str = time_str.strip().lower()
    now = datetime.now()

    # Handle "in X minutes/hours/days/weeks"
    if time_str.startswith("in "):
        remainder = time_str[3:]
        parts = remainder.split()
        if len(parts) >= 2:
            try:
                amount = int(parts[0])
                unit = parts[1]

                if unit.startswith("min"):
                    return now + relativedelta(minutes=amount)
                elif unit.startswith("hr") or unit.startswith("hour"):
                    return now + relativedelta(hours=amount)
                elif unit.startswith("day"):
                    return now + relativedelta(days=amount)
                elif unit.startswith("week"):
                    return now + relativedelta(weeks=amount)
                elif unit.startswith("sec"):
                    return now + relativedelta(seconds=amount)
                elif unit.startswith("month"):
                    return now + relativedelta(months=amount)
            except ValueError:
                pass

    # Handle "today at X" or "tomorrow at X"
    if time_str.startswith("today at ") or time_str.startswith("today "):
        time_only = time_str.replace("today at ", "").replace("today ", "").strip()
        try:
            return date_parser.parse(time_only, default=now)
        except Exception:
            pass

    if time_str.startswith("tomorrow at ") or time_str.startswith("tomorrow "):
        time_only = time_str.replace("tomorrow at ", "").replace("tomorrow ", "").strip()
        try:
            tomorrow = now + relativedelta(days=1)
            return date_parser.parse(time_only, default=tomorrow)
        except Exception:
            pass

    # Handle "tomorrow", "today" standalone
    if time_str == "tomorrow":
        return now + relativedelta(days=1)
    if time_str == "today":
        return now

    # Handle "at X" - assume today or tomorrow if time has passed
    if time_str.startswith("at "):
        time_only = time_str[3:]
        try:
            parsed_time = date_parser.parse(time_only, default=now)
            if parsed_time < now:
                parsed_time += relativedelta(days=1)
            return parsed_time
        except Exception:
            pass

    # Handle numeric time formats like "0130hr", "1:30pm", "15:30"
    # Try to extract just the time portion
    import re
    time_match = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm|hr)?', time_str)
    if time_match and not any(word in time_str for word in ['day', 'tomorrow', 'today', 'jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec', '-', '/']):
        hour = int(time_match.group(1))
        minute = int(time_match.group(2)) if time_match.group(2) else 0
        meridiem = time_match.group(3)

        # Handle "0130hr" style (hour 0-23)
        if meridiem == 'hr' or hour > 12:
            parsed_time = now.replace(hour=hour % 24, minute=minute, second=0, microsecond=0)
        elif meridiem == 'pm' and hour != 12:
            parsed_time = now.replace(hour=hour + 12, minute=minute, second=0, microsecond=0)
        elif meridiem == 'am' and hour == 12:
            parsed_time = now.replace(hour=0, minute=minute, second=0, microsecond=0)
        else:
            parsed_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

        # If time has passed, assume tomorrow
        if parsed_time < now:
            parsed_time += relativedelta(days=1)
        return parsed_time

    # Try parsing as full datetime with dateutil (very flexible)
    try:
        parsed = date_parser.parse(time_str, fuzzy=True, default=now)
        # If parsed time is in the past and seems like just a time, move to tomorrow
        if parsed < now and parsed.year == now.year and parsed.month == now.month and parsed.day == now.day:
            # Check if original string looks like just a time (no date info)
            if not any(word in time_str.lower() for word in ['today', 'tomorrow', 'yesterday']):
                parsed += relativedelta(days=1)
        return parsed
    except Exception:
        pass

    # Final fallback: try parsing with now as default
    try:
        return date_parser.parse(time_str, default=now, fuzzy=True)
    except Exception as e:
        raise ValueError(
            f"Could not parse time expression '{time_str}'. "
            "Try formats like: 'in 30 minutes', 'in 2 hours', 'today at 1:30pm', "
            "'tomorrow at 9am', '1:30pm', '15:30', '2025-01-15 14:00'"
        ) from e


@tool
async def set_reminder(
    message: str,
    time: str,
    recurrence: str = "",
) -> str:
    """Set a reminder for the user.

    Args:
        message: The reminder message (what to remind about)
        time: When to remind. Flexible formats supported:
            - Relative: "in 30 minutes", "in 2 hours", "in 3 days", "in 1 week"
            - Day + time: "today at 1:30pm", "tomorrow at 9am", "today 15:30"
            - Time only: "1:30pm", "3pm", "15:30" (assumes today/tomorrow)
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

    recurrence_str = f" (recurring: {recurrence})" if recurrence else ""
    return f"Reminder set for {due_time.strftime('%Y-%m-%d %H:%M')}{recurrence_str}. ID: {reminder.id}"


@tool
async def list_reminders(
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

    lines = [f"{'ID':<5} {'Status':<10} {'Due Time':<20} {'Message'}"]
    lines.append("-" * 80)

    for r in reminders:
        due_str = r.due_time.strftime("%Y-%m-%d %H:%M")
        recurrence_str = " (recurring)" if r.is_recurring else ""
        lines.append(f"{r.id:<5} {r.status:<10} {due_str:<20} {r.message}{recurrence_str}")

    return "\n".join(lines)


@tool
async def cancel_reminder(
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
    return f"Reminder {reminder_id} cancelled."


@tool
async def edit_reminder(
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
    return [set_reminder, list_reminders, cancel_reminder, edit_reminder]
