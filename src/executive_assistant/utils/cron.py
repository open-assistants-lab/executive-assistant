"""Cron parsing utilities shared across scheduling features."""

import logging
import re
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def parse_cron_next(cron: str, after: datetime) -> datetime:
    """Calculate next run time from a cron expression.

    Supports standard 5-field cron: minute hour day month weekday
    Also supports common shortcuts:
    - "@hourly" or "hourly" -> every hour
    - "@daily" or "daily" or "0 0 * * *" -> every day at midnight
    - "@weekly" or "weekly" or "0 0 * * 0" -> every week at midnight Sunday
    - "@monthly" or "monthly" or "0 0 1 * *" -> every month on 1st at midnight
    - "daily at 9am" -> daily at 9am
    - "daily at 9pm" -> daily at 9pm

    Args:
        cron: Cron expression or shortcut
        after: Calculate next time after this datetime

    Returns:
        Next run datetime

    Raises:
        ValueError: If cron expression is invalid
    """
    now = after

    # Handle shortcuts
    cron_lower = cron.lower().strip()
    if cron_lower in ("@hourly", "hourly"):
        return now + timedelta(hours=1)
    if cron_lower in ("@daily", "daily"):
        return (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    if cron_lower in ("@weekly", "weekly"):
        # Next Sunday at midnight
        days_ahead = 6 - now.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        next_week = now + timedelta(days=days_ahead)
        return next_week.replace(hour=0, minute=0, second=0, microsecond=0)
    if cron_lower in ("@monthly", "monthly"):
        # Next month on 1st at midnight
        if now.month == 12:
            next_month = now.replace(year=now.year + 1, month=1, day=1)
        else:
            next_month = now.replace(month=now.month + 1, day=1)
        return next_month.replace(hour=0, minute=0, second=0, microsecond=0)

    # Handle "daily at 9am" / "daily at 9pm" format
    match = re.match(r"daily\s+at\s+(\d{1,2})(:(\d{2}))?\s*(am|pm)?", cron_lower)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(3)) if match.group(3) else 0
        meridiem = match.group(4)
        if meridiem == "pm" and hour < 12:
            hour += 12
        elif meridiem == "am" and hour == 12:
            hour = 0

        result = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if result <= now:
            result = result + timedelta(days=1)
        return result

    # Remove @ prefix if present
    if cron_lower.startswith("@"):
        cron_lower = cron_lower[1:]

    # Parse standard 5-field cron
    # Format: minute hour day month weekday
    parts = cron_lower.strip().split()
    if len(parts) != 5:
        raise ValueError(
            f"Invalid cron expression '{cron}'. "
            "Expected 5 fields (minute hour day month weekday) or a shortcut."
        )

    minute_part, hour_part, day_part, month_part, weekday_part = parts

    # For simplicity, handle common patterns
    # This is a basic implementation - for full cron support, use croniter

    try:
        # Handle "0 9 * * *" (daily at 9am)
        if minute_part == "0" and hour_part.isdigit() and day_part == "*" and month_part == "*" and weekday_part == "*":
            hour = int(hour_part)
            if hour < 0 or hour > 23:
                raise ValueError("Hour must be 0-23")
            result = now.replace(hour=hour, minute=0, second=0, microsecond=0)
            if result <= now:
                result = result + timedelta(days=1)
            return result

        # Handle "0 */6 * * *" (every 6 hours)
        if minute_part == "0" and hour_part.startswith("*/") and day_part == "*" and month_part == "*" and weekday_part == "*":
            interval = int(hour_part[2:])
            if interval < 1 or interval > 23:
                raise ValueError("Hour interval must be 1-23")
            result = now.replace(minute=0, second=0, microsecond=0)
            # Find next interval
            current_hour = result.hour
            # Calculate hours to add to reach next interval
            hours_to_add = (interval - (current_hour % interval)) % interval
            if hours_to_add == 0 and result <= now:
                hours_to_add = interval
            result = result + timedelta(hours=hours_to_add)
            return result

        # Handle "*/30 * * * *" (every 30 minutes)
        if minute_part.startswith("*/") and hour_part == "*" and day_part == "*" and month_part == "*" and weekday_part == "*":
            interval = int(minute_part[2:])
            if interval < 1 or interval > 59:
                raise ValueError("Minute interval must be 1-59")
            result = now.replace(second=0, microsecond=0)
            # Round up to next interval
            minute = (result.minute // interval + 1) * interval
            if minute >= 60:
                result = result + timedelta(hours=1)
                minute = 0
            result = result.replace(minute=minute)
            if result <= now:
                result = result + timedelta(minutes=interval)
            return result

        # Handle "0 9 * * 1-5" (daily at 9am, weekdays only)
        if (
            minute_part == "0"
            and hour_part.isdigit()
            and day_part == "*"
            and month_part == "*"
            and "-" in weekday_part
        ):
            hour = int(hour_part)
            result = now.replace(hour=hour, minute=0, second=0, microsecond=0)
            # Find next weekday
            while True:
                result = result + timedelta(days=1)
                if result.weekday() < 5:  # Monday=0, Friday=4
                    return result

        # Default: add 1 day (fallback)
        logger.warning(f"Cron pattern '{cron}' not fully supported, treating as daily")
        return (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)

    except (ValueError, IndexError) as e:
        raise ValueError(f"Invalid cron expression '{cron}': {e}") from e
