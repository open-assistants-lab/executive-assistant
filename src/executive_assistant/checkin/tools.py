"""User-facing check-in commands.

Tools for users to enable/disable/configure check-in via chat.
"""

from __future__ import annotations

from langchain_core.tools import tool

from executive_assistant.checkin.config import (
    CheckinConfig,
    get_checkin_config,
    save_checkin_config,
)
from executive_assistant.storage.file_sandbox import get_thread_id


@tool
def checkin_enable(every: str = "30m", lookback: str = "24h") -> str:
    """Enable journal check-in to monitor your activity and goals.

    Periodically analyzes your journal and goals to surface patterns
    and items needing attention.

    Args:
        every: How often to run check-in (e.g., "30m", "1h", "2h", "4h")
        lookback: How much journal history to analyze (e.g., "24h", "7d", "1w")

    Returns:
        Confirmation message
    """
    thread_id = get_thread_id()

    # Get existing config or create new
    config = get_checkin_config(thread_id)

    # Update settings
    config.enabled = True
    config.every = every
    config.lookback = lookback

    # Save
    save_checkin_config(config)

    return f"""✅ Check-in enabled!

Configuration:
• Frequency: Every {every}
• Lookback: {lookback} of journal
• Active hours: {config.active_hours_start or '9:00'} - {config.active_hours_end or '18:00'}
• Active days: {config.active_days}

I'll periodically check your journal and goals, and message you
only when something important needs attention.

You can customize with:
• checkin_schedule() - Change frequency
• checkin_hours() - Set active hours
• checkin_show() - View configuration"""


@tool
def checkin_disable() -> str:
    """Disable journal check-in.

    Stops periodic monitoring of your journal and goals.

    Returns:
        Confirmation message
    """
    thread_id = get_thread_id()
    config = get_checkin_config(thread_id)

    config.enabled = False
    save_checkin_config(config)

    return """✅ Check-in disabled.

I'll no longer send proactive check-in messages.

Re-enable anytime with: checkin_enable()"""


@tool
def checkin_show() -> str:
    """Show current check-in configuration.

    Displays your current check-in settings including frequency,
    active hours, and status.

    Returns:
        Current configuration
    """
    thread_id = get_thread_id()
    config = get_checkin_config(thread_id)

    status = "✅ Enabled" if config.enabled else "❌ Disabled"

    return f"""Check-in Configuration:

Status: {status}
Frequency: Every {config.every}
Lookback: {config.lookback}
Active Hours: {config.active_hours_start or '9:00'} - {config.active_hours_end or '18:00'}
Active Days: {config.active_days}
Last Check-in: {config.last_checkin or 'Never'}

{'Check-in is actively monitoring your journal and goals.' if config.enabled else 'Check-in is disabled. Enable with checkin_enable()'}"""


@tool
def checkin_schedule(every: str) -> str:
    """Change check-in frequency.

    Args:
        every: How often to run (e.g., "30m", "1h", "2h", "4h")

    Returns:
        Confirmation message
    """
    thread_id = get_thread_id()
    config = get_checkin_config(thread_id)

    # Validate
    every = every.lower().strip()
    if not (every.endswith("m") or every.endswith("h")):
        return """❌ Invalid frequency format.

Use: "30m", "1h", "2h", etc.
Example: checkin_schedule("1h")"""

    config.every = every
    save_checkin_config(config)

    return f"""✅ Check-in frequency updated!

New schedule: Every {every}

Next check-in will run based on this schedule."""


@tool
def checkin_hours(
    start: str = "9:00",
    end: str = "18:00",
    days: str = "Mon,Tue,Wed,Thu,Fri",
) -> str:
    """Set active hours for check-in.

    Check-in will only run during these hours and days.

    Args:
        start: Start time (e.g., "9:00")
        end: End time (e.g., "18:00")
        days: Active days (comma-separated, e.g., "Mon,Tue,Wed,Thu,Fri")

    Returns:
        Confirmation message
    """
    thread_id = get_thread_id()
    config = get_checkin_config(thread_id)

    # Validate time format
    try:
        from datetime import time

        time.fromisoformat(start)
        time.fromisoformat(end)
    except ValueError:
        return """❌ Invalid time format.

Use HH:MM format (24-hour).
Example: checkin_hours("9:00", "18:00")"""

    # Validate days
    valid_days = {"Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"}
    day_list = [d.strip() for d in days.split(",")]
    if not all(d in valid_days for d in day_list):
        return f"""❌ Invalid day format.

Use: Mon, Tue, Wed, Thu, Fri, Sat, Sun
Example: checkin_hours("9:00", "18:00", "Mon,Tue,Wed,Thu,Fri")"""

    config.active_hours_start = start
    config.active_hours_end = end
    config.active_days = days
    save_checkin_config(config)

    return f"""✅ Active hours updated!

Schedule: {start} - {end}
Days: {days}

Check-in will only run during these hours."""


@tool
def checkin_test() -> str:
    """Test check-in by running it once now.

    Manually triggers check-in analysis and shows results
    without waiting for the scheduled time.

    Returns:
        Check-in results
    """
    import asyncio

    thread_id = get_thread_id()

    # Run check-in synchronously
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If already in async context, create task
            import nest_asyncio
            nest_asyncio.apply()
            result = asyncio.run(__run_test_checkin(thread_id))
        else:
            result = asyncio.run(__run_test_checkin(thread_id))
    except RuntimeError:
        # No event loop, create new one
        result = asyncio.run(__run_test_checkin(thread_id))

    return result


async def __run_test_checkin(thread_id: str) -> str:
    """Internal async function to test check-in."""
    from executive_assistant.checkin.runner import run_checkin

    try:
        findings = await run_checkin(thread_id)

        if findings:
            return f"""📋 Check-in Results:

{findings}"""
        else:
            return """✅ Check-in test complete.

Nothing important to report. (This is good!)"""

    except Exception as e:
        return f"""❌ Check-in test failed: {e}"""
