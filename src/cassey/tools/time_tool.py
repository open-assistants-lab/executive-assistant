"""Time and date tools for the agent."""

from datetime import datetime
from zoneinfo import ZoneInfo
from langchain_core.tools import tool


@tool
def get_current_time(timezone: str = "UTC") -> str:
    """
    Get the current time for a specific timezone.

    Args:
        timezone: IANA timezone name (e.g., "America/New_York", "Asia/Shanghai", "UTC")

    Returns:
        Current date and time in the specified timezone.

    Examples:
        >>> get_current_time("UTC")
        "2025-01-14 10:30:45 UTC"
        >>> get_current_time("Asia/Shanghai")
        "2025-01-14 18:30:45 CST"
    """
    try:
        tz = ZoneInfo(timezone)
        now = datetime.now(tz)
        return f"{now.strftime('%Y-%m-%d %H:%M:%S')} {timezone}"
    except Exception as e:
        return f"Error: {e}. Available timezones: UTC, America/New_York, Europe/London, Asia/Shanghai, etc."


@tool
def get_current_date(timezone: str = "UTC") -> str:
    """
    Get the current date for a specific timezone.

    Args:
        timezone: IANA timezone name (e.g., "America/New_York", "Asia/Shanghai", "UTC")

    Returns:
        Current date in the specified timezone.

    Examples:
        >>> get_current_date("UTC")
        "Tuesday, January 14, 2025"
    """
    try:
        tz = ZoneInfo(timezone)
        now = datetime.now(tz)
        return now.strftime("%A, %B %d, %Y")
    except Exception as e:
        return f"Error: {e}"


@tool
def list_timezones() -> str:
    """
    List common timezones available for get_current_time.

    Returns:
        List of common IANA timezone names.
    """
    common_zones = [
        "UTC",
        "America/New_York",
        "America/Los_Angeles",
        "America/Chicago",
        "Europe/London",
        "Europe/Paris",
        "Asia/Shanghai",
        "Asia/Tokyo",
        "Asia/Singapore",
        "Asia/Dubai",
        "Australia/Sydney",
    ]
    return "Common timezones:\n" + "\n".join(f"- {tz}" for tz in common_zones)
