"""Time tool for agent - get current time with timezone support."""

from datetime import datetime, timezone as tz_module
from typing import Optional

from langchain_core.tools import tool

from src.app_logging import get_logger

logger = get_logger()

# Common timezone mappings
TIMEZONE_MAP = {
    # Major cities
    "new york": "America/New_York",
    "nyc": "America/New_York",
    "los angeles": "America/Los_Angeles",
    "la": "America/Los_Angeles",
    "chicago": "America/Chicago",
    "london": "Europe/London",
    "paris": "Europe/Paris",
    "berlin": "Europe/Berlin",
    "tokyo": "Asia/Tokyo",
    "sydney": "Australia/Sydney",
    "shanghai": "Asia/Shanghai",
    "singapore": "Asia/Singapore",
    "hong kong": "Asia/Hong_Kong",
    "dubai": "Asia/Dubai",
    "mumbai": "Asia/Kolkata",
    "delhi": "Asia/Kolkata",
    "toronto": "America/Toronto",
    "vancouver": "America/Vancouver",
    "seattle": "America/Los_Angeles",
    "san francisco": "America/Los_Angeles",
    "sf": "America/Los_Angeles",
    # Regions
    "us": "America/New_York",
    "us east": "America/New_York",
    "us west": "America/Los_Angeles",
    "uk": "Europe/London",
    "europe": "Europe/Paris",
    "asia": "Asia/Shanghai",
    "australia": "Australia/Sydney",
    "pst": "America/Los_Angeles",
    "est": "America/New_York",
    "cet": "Europe/Paris",
    "jst": "Asia/Tokyo",
    "aest": "Australia/Sydney",
    # UTC
    "utc": "UTC",
    "gmt": "UTC",
}


@tool
def get_time(timezone: Optional[str] = None) -> str:
    """Get current time.

    If no timezone is provided, defaults to UTC.
    You can ask the user for their timezone if it's not specified.

    Args:
        timezone: Timezone name (e.g., 'America/New_York', 'Asia/Shanghai', 'London')
                 or common city names (e.g., 'New York', 'Shanghai', 'London')

    Returns:
        Formatted current time with timezone
    """
    # Determine timezone
    tz = "UTC"

    if timezone:
        # Normalize timezone input
        tz_lower = timezone.lower().strip()
        tz = TIMEZONE_MAP.get(tz_lower, timezone)

    try:
        if tz == "UTC":
            now = datetime.now(tz_module.utc)
            tz_name = "UTC"
        else:
            from zoneinfo import ZoneInfo

            now = datetime.now(ZoneInfo(tz))
            tz_name = tz

        # Format output
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M:%S")
        day_str = now.strftime("%A")

        return f"Current time: {date_str} {time_str} {tz_name} ({day_str})"

    except Exception as e:
        logger.warning("time.tool.error", {"timezone": tz, "error": str(e)}, channel="agent")
        # Fallback to UTC
        now = datetime.now(tz_module.utc)
        return f"Could not parse timezone '{timezone}', showing UTC: {now.strftime('%Y-%m-%d %H:%M:%S')} UTC"
