"""Time tools for the Executive Assistant.

Provides time awareness with:
- Daylight saving time (DST) support via zoneinfo
- User timezone from profile memory
- Natural time context for system prompts
"""

from __future__ import annotations

from datetime import datetime, timezone as dt_timezone
from zoneinfo import ZoneInfo, available_timezones

from langchain_core.tools import tool


def get_dst_info(dt: datetime, tz: ZoneInfo) -> dict:
    """Get daylight saving time information for a datetime."""
    is_dst = bool(dt.dst())
    dst_name = dt.strftime("%Z")
    offset_hours = dt.utcoffset().total_seconds() / 3600 if dt.utcoffset() else 0

    return {
        "is_dst": is_dst,
        "abbreviation": dst_name,
        "utc_offset_hours": offset_hours,
        "utc_offset_str": dt.strftime("%z"),
    }


def get_time_context(user_timezone: str | None = None) -> str:
    """Get time context for system prompt injection.

    This should be called when building the system prompt to give
    the agent awareness of the current time.

    Args:
        user_timezone: User's preferred timezone (e.g., 'America/Los_Angeles').
                       Falls back to UTC if not provided or invalid.

    Returns:
        Formatted time context string for system prompt.
    """
    now_utc = datetime.now(dt_timezone.utc)

    user_tz = None
    if user_timezone:
        try:
            user_tz = ZoneInfo(user_timezone)
        except Exception:
            pass

    lines = [
        "## Current Time Context",
        "",
        f"**UTC**: {now_utc.strftime('%Y-%m-%d %H:%M:%S')} UTC",
        f"**Date**: {now_utc.strftime('%A, %B %d, %Y')}",
        f"**Week**: Week {now_utc.isocalendar()[1]} of {now_utc.year}",
        f"**Quarter**: Q{(now_utc.month - 1) // 3 + 1} {now_utc.year}",
    ]

    if user_tz:
        now_local = now_utc.astimezone(user_tz)
        dst_info = get_dst_info(now_local, user_tz)

        lines.append("")
        lines.append(f"**User Timezone**: {user_timezone}")
        lines.append(
            f"**Local Time**: {now_local.strftime('%Y-%m-%d %H:%M:%S')} {dst_info['abbreviation']}"
        )
        lines.append(
            f"**UTC Offset**: {'+' if dst_info['utc_offset_hours'] >= 0 else ''}{dst_info['utc_offset_hours']:.1f} hours"
        )

        if dst_info["is_dst"]:
            lines.append("**Daylight Saving**: Currently observing DST (clocks ahead 1 hour)")
        else:
            lines.append("**Daylight Saving**: Not currently observing DST")

    return "\n".join(lines)


@tool
def get_current_time(timezone: str | None = None) -> str:
    """Get current date and time with DST information.

    Use this tool when you need to know the current time, either in UTC
    or a specific timezone. Includes daylight saving time status.

    Args:
        timezone: Optional IANA timezone name (e.g., 'America/New_York',
                  'Europe/London', 'Asia/Tokyo', 'Australia/Sydney').
                  If not provided, returns UTC time only.

    Returns:
        Current date, time, timezone info, and DST status.

    Examples:
        get_current_time()  # UTC time
        get_current_time("America/New_York")  # Eastern Time with DST
        get_current_time("Europe/London")  # UK time with DST
        get_current_time("Australia/Sydney")  # Sydney time (DST in summer)
    """
    now_utc = datetime.now(dt_timezone.utc)

    result_lines = [
        f"UTC: {now_utc.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Date: {now_utc.strftime('%A, %B %d, %Y')}",
        f"Week: {now_utc.isocalendar()[1]} of {now_utc.year}",
        f"Quarter: Q{(now_utc.month - 1) // 3 + 1}",
        f"Day of Year: {now_utc.timetuple().tm_yday}",
    ]

    if not timezone:
        return "\n".join(result_lines)

    try:
        tz = ZoneInfo(timezone)
        now_local = now_utc.astimezone(tz)
        dst_info = get_dst_info(now_local, tz)

        result_lines.extend(
            [
                "",
                f"Timezone: {timezone}",
                f"Local Time: {now_local.strftime('%Y-%m-%d %H:%M:%S')} {dst_info['abbreviation']}",
                f"UTC Offset: {dst_info['utc_offset_str']} ({'+' if dst_info['utc_offset_hours'] >= 0 else ''}{dst_info['utc_offset_hours']:.1f} hours)",
                f"DST Active: {'Yes' if dst_info['is_dst'] else 'No'}",
            ]
        )

        if dst_info["is_dst"]:
            result_lines.append(
                "Note: Daylight Saving Time is currently in effect (clocks are 1 hour ahead)"
            )
        else:
            result_lines.append("Note: Standard Time is in effect")

    except Exception as e:
        result_lines.append(
            f"\nError: Invalid timezone '{timezone}'. Use IANA format like 'America/New_York'"
        )
        result_lines.append(
            f"Available examples: America/New_York, America/Los_Angeles, Europe/London, Asia/Tokyo, Australia/Sydney"
        )

    return "\n".join(result_lines)


@tool
def list_timezones(region: str | None = None) -> str:
    """List available timezone names.

    Use this to find valid timezone strings for get_current_time().

    Args:
        region: Optional region filter (e.g., 'America', 'Europe', 'Asia', 'Australia').
                If not provided, lists common timezones from all regions.

    Returns:
        List of valid IANA timezone names.
    """
    all_zones = sorted(available_timezones())

    common_zones = {
        "America": [
            "America/New_York",
            "America/Chicago",
            "America/Denver",
            "America/Los_Angeles",
            "America/Phoenix",
            "America/Anchorage",
            "America/Toronto",
            "America/Vancouver",
            "America/Mexico_City",
            "America/Sao_Paulo",
            "America/Buenos_Aires",
        ],
        "Europe": [
            "Europe/London",
            "Europe/Paris",
            "Europe/Berlin",
            "Europe/Rome",
            "Europe/Madrid",
            "Europe/Amsterdam",
            "Europe/Moscow",
            "Europe/Istanbul",
        ],
        "Asia": [
            "Asia/Tokyo",
            "Asia/Shanghai",
            "Asia/Hong_Kong",
            "Asia/Singapore",
            "Asia/Seoul",
            "Asia/Mumbai",
            "Asia/Dubai",
            "Asia/Bangkok",
        ],
        "Australia": [
            "Australia/Sydney",
            "Australia/Melbourne",
            "Australia/Brisbane",
            "Australia/Perth",
            "Australia/Adelaide",
        ],
        "Pacific": [
            "Pacific/Auckland",
            "Pacific/Fiji",
            "Pacific/Honolulu",
        ],
    }

    if region:
        filtered = [z for z in all_zones if z.startswith(f"{region}/")]
        if filtered:
            return f"Timezones in {region}:\n" + "\n".join(filtered[:50])
        return f"No timezones found for region '{region}'"

    lines = ["Common Timezones by Region:", ""]
    for reg, zones in common_zones.items():
        lines.append(f"**{reg}:**")
        lines.extend(f"  {z}" for z in zones)
        lines.append("")

    return "\n".join(lines)


@tool
def parse_relative_time(expression: str, reference_timezone: str | None = None) -> str:
    """Parse a relative time expression into an absolute date/time.

    Use this to understand natural language time references like
    'next week', 'in 3 days', 'end of month', etc.

    Args:
        expression: Natural language time expression (e.g., 'tomorrow',
                    'next monday', 'end of month', 'in 2 weeks').
        reference_timezone: Optional timezone for reference point.
                           Defaults to UTC.

    Returns:
        Absolute date/time with explanation.
    """
    from datetime import timedelta
    import re

    now = datetime.now(dt_timezone.utc)

    if reference_timezone:
        try:
            tz = ZoneInfo(reference_timezone)
            now = datetime.now(tz)
        except Exception:
            pass

    expression = expression.lower().strip()

    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if expression == "today":
        result = today
        explanation = "Today (start of day)"
    elif expression == "tomorrow":
        result = today + timedelta(days=1)
        explanation = "Tomorrow (start of day)"
    elif expression == "yesterday":
        result = today - timedelta(days=1)
        explanation = "Yesterday (start of day)"
    elif expression in ("this week", "end of week", "eow"):
        days_until_sunday = 6 - today.weekday()
        result = today + timedelta(days=days_until_sunday)
        explanation = "End of this week (Sunday)"
    elif expression in ("next week", "start of next week"):
        days_until_monday = (7 - today.weekday()) % 7 or 7
        result = today + timedelta(days=days_until_monday)
        explanation = "Start of next week (Monday)"
    elif expression in ("this month", "end of month", "eom"):
        if today.month == 12:
            result = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            result = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
        explanation = "End of this month"
    elif expression in ("next month", "start of next month"):
        if today.month == 12:
            result = today.replace(year=today.year + 1, month=1, day=1)
        else:
            result = today.replace(month=today.month + 1, day=1)
        explanation = "Start of next month"
    elif expression == "this quarter":
        quarter_start_month = ((today.month - 1) // 3) * 3 + 1
        quarter_end_month = quarter_start_month + 2
        if quarter_end_month == 12:
            result = today.replace(month=12, day=31)
        else:
            result = today.replace(month=quarter_end_month + 1, day=1) - timedelta(days=1)
        explanation = f"End of Q{(today.month - 1) // 3 + 1}"
    elif expression == "end of year" or expression == "eoy":
        result = today.replace(month=12, day=31)
        explanation = "End of this year"
    elif match := re.match(r"next (\w+)", expression):
        day_name = match.group(1)
        day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        if day_name in day_names:
            target_day = day_names.index(day_name)
            days_ahead = target_day - today.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            result = today + timedelta(days=days_ahead)
            explanation = f"Next {day_name.capitalize()}"
        else:
            return f"Could not parse '{expression}'. Unknown day name '{day_name}'."
    elif match := re.match(r"in (\d+) (day|days|week|weeks|month|months)", expression):
        amount = int(match.group(1))
        unit = match.group(2)
        if unit in ("day", "days"):
            result = today + timedelta(days=amount)
            explanation = f"In {amount} day(s)"
        elif unit in ("week", "weeks"):
            result = today + timedelta(weeks=amount)
            explanation = f"In {amount} week(s)"
        elif unit in ("month", "months"):
            month = today.month + amount
            year = today.year + (month - 1) // 12
            month = (month - 1) % 12 + 1
            day = min(today.day, 28)
            result = today.replace(year=year, month=month, day=day)
            explanation = f"In {amount} month(s)"
    else:
        return f"Could not parse '{expression}'. Try expressions like: today, tomorrow, next week, end of month, in 3 days, next monday."

    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    month_names = [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ]

    return f"""{explanation}
Date: {day_names[result.weekday()]}, {month_names[result.month - 1]} {result.day}, {result.year}
ISO: {result.strftime("%Y-%m-%d")}
Reference: {now.strftime("%Y-%m-%d %H:%M:%S %Z")}
"""
