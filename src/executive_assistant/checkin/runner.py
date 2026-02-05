"""Main check-in execution logic.

Orchestrates the check-in process: query journal/goals, analyze,
and send message if findings are important.
"""

from __future__ import annotations

import asyncio
from datetime import timezone
from typing import Any

from executive_assistant.checkin.analyzer import (
    analyze_journal_and_goals,
    get_start_time,
)
from executive_assistant.checkin.config import (
    CheckinConfig,
    get_checkin_config,
    update_last_checkin,
)
from executive_assistant.logging import logger
from executive_assistant.storage.goals_storage import GoalsStorage
from executive_assistant.storage.journal_storage import JournalStorage


async def run_checkin(
    thread_id: str,
    channel: str | None = None,
) -> str | None:
    """
    Run check-in for a user.

    Args:
        thread_id: Thread identifier
        channel: Channel to send message (if None, won't send)

    Returns:
        Message content if important findings, None otherwise
    """
    # 1. Get config
    config = get_checkin_config(thread_id)

    if not config.enabled:
        logger.debug(f"Check-in disabled for {thread_id}")
        return None

    if not config.is_active_hours():
        logger.debug(f"Check-in outside active hours for {thread_id}")
        return None

    # 2. Get journal entries
    journal_storage = JournalStorage()
    start_time = get_start_time(config.lookback)

    try:
        journal_entries = journal_storage.list_entries(
            thread_id=thread_id,
            start_time=start_time,
            entry_type="raw",  # Only get raw entries, not rollups
            limit=100,
        )
    except Exception as e:
        logger.error(f"Error fetching journal for {thread_id}: {e}")
        journal_entries = []

    # 3. Get goals
    goals_storage = GoalsStorage()

    try:
        goals = goals_storage.list_goals(
            thread_id=thread_id,
            status="planned",  # Only active goals
            limit=20,
        )
    except Exception as e:
        logger.error(f"Error fetching goals for {thread_id}: {e}")
        goals = []

    # 4. Analyze
    try:
        findings = await analyze_journal_and_goals(
            journal_entries=journal_entries,
            goals=goals,
            user_id=thread_id,
        )
    except Exception as e:
        logger.error(f"Error analyzing check-in for {thread_id}: {e}")
        return None

    # 5. Update last check-in time
    now = asyncio.get_event_loop().time()
    update_last_checkin(thread_id, str(now))

    # 6. Return findings if important
    if findings and findings != "CHECKIN_OK":
        logger.info(f"Check-in findings for {thread_id}: {findings[:100]}...")
        return findings
    else:
        logger.debug(f"Check-in OK for {thread_id} (nothing to report)")
        return None


async def send_checkin_message(thread_id: str, message: str, channel: str) -> None:
    """
    Send check-in message to user.

    Args:
        thread_id: Thread identifier
        message: Message content
        channel: Channel to send through
    """
    # This would need to integrate with the channel system
    # For now, just log the message
    logger.info(f"Check-in message for {thread_id} (channel={channel}):\n{message}")

    # TODO: Implement actual message sending
    # Would need to import channel senders
    # if channel == "telegram":
    #     from executive_assistant.channels.telegram import send_telegram_message
    #     await send_telegram_message(thread_id, message)
    # elif channel == "http":
    #     # Store for HTTP poll
    #     pass


async def run_checkin_and_send(
    thread_id: str,
    default_channel: str = "telegram",
) -> bool:
    """
    Run check-in and send message if findings exist.

    Args:
        thread_id: Thread identifier
        default_channel: Default channel to send through

    Returns:
        True if message was sent, False otherwise
    """
    try:
        findings = await run_checkin(thread_id, default_channel)

        if findings:
            await send_checkin_message(thread_id, findings, default_channel)
            return True

        return False

    except Exception as e:
        logger.error(f"Error in run_checkin_and_send for {thread_id}: {e}")
        return False


def should_run_checkin(config: CheckinConfig, last_run_time: float | None) -> bool:
    """
    Check if check-in should run based on schedule.

    Args:
        config: Check-in configuration
        last_run_time: Last time check-in ran (unix timestamp)

    Returns:
        True if check-in should run
    """
    import time

    if not config.enabled:
        return False

    if not config.is_active_hours():
        return False

    # Parse interval
    every = config.every.lower().strip()

    if every.endswith("m"):
        interval_minutes = int(every[:-1])
        interval_seconds = interval_minutes * 60
    elif every.endswith("h"):
        interval_hours = int(every[:-1])
        interval_seconds = interval_hours * 3600
    else:
        # Default to 30 minutes
        interval_seconds = 1800

    # Check if enough time has passed
    if last_run_time:
        elapsed = time.time() - last_run_time
        if elapsed < interval_seconds:
            return False

    return True
