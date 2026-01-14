"""Scheduler for reminder notifications using APScheduler.

This module runs as a background task, polling the database for pending reminders
and sending notifications through the appropriate channels.
"""

import asyncio
import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from cassey.config.settings import settings
from cassey.storage.reminder import ReminderStorage, get_reminder_storage

logger = logging.getLogger(__name__)

# Global scheduler instance
_scheduler: AsyncIOScheduler | None = None
_notification_handlers = {}


def register_notification_handler(channel: str, handler):
    """Register a notification handler for a channel.

    Args:
        channel: Channel name (e.g., 'telegram', 'http', 'email')
        handler: Async function that takes (thread_ids, message) and sends notification
    """
    _notification_handlers[channel] = handler


async def _send_notification(thread_ids: list[str], message: str, channel: str) -> bool:
    """Send notification through the appropriate channel.

    Args:
        thread_ids: List of thread IDs to notify
        message: Message to send
        channel: Channel to use for sending

    Returns:
        True if successful, False otherwise
    """
    handler = _notification_handlers.get(channel)

    if handler:
        try:
            await handler(thread_ids, message)
            return True
        except Exception as e:
            logger.error(f"Failed to send notification via {channel}: {e}")
            return False
    else:
        logger.warning(f"No notification handler registered for channel: {channel}")
        return False


async def _process_pending_reminders():
    """Check for and process pending reminders.

    This is called periodically by the scheduler.
    """
    storage = await get_reminder_storage()

    # Get reminders due now or in the past
    now = datetime.now()
    # Look back 1 minute to catch any we might have missed
    lookback = now - timedelta(minutes=1)

    try:
        pending = await storage.get_pending_reminders(now)

        if not pending:
            return

        logger.info(f"Processing {len(pending)} pending reminder(s)")

        for reminder in pending:
            # Determine channel from thread_id (e.g., "telegram:123" -> "telegram")
            if not reminder.thread_ids:
                logger.warning(f"Reminder {reminder.id} has no thread_ids")
                await storage.mark_failed(reminder.id, "No thread IDs")
                continue

            # Use the first thread_id to determine channel
            thread_id = reminder.thread_ids[0]
            if ":" in thread_id:
                channel = thread_id.split(":")[0]
            else:
                channel = "unknown"

            # Send notification
            success = await _send_notification(
                reminder.thread_ids, reminder.message, channel
            )

            if success:
                await storage.mark_sent(reminder.id, now)
                logger.info(f"Reminder {reminder.id} sent successfully")

                # TODO: Handle recurring reminders - create next instance
                if reminder.is_recurring:
                    logger.info(f"TODO: Create next instance for recurring reminder {reminder.id}")
            else:
                await storage.mark_failed(
                    reminder.id, f"Failed to send via {channel}"
                )
                logger.error(f"Reminder {reminder.id} failed to send")

    except Exception as e:
        logger.error(f"Error processing pending reminders: {e}")


async def start_scheduler():
    """Start the reminder scheduler.

    This should be called during application startup.
    """
    global _scheduler

    if _scheduler is not None and _scheduler.running:
        logger.warning("Scheduler already running")
        return

    _scheduler = AsyncIOScheduler()

    # Add job to check for pending reminders every 60 seconds
    _scheduler.add_job(
        _process_pending_reminders,
        IntervalTrigger(seconds=60),
        id="check_pending_reminders",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info("Reminder scheduler started")


async def stop_scheduler():
    """Stop the reminder scheduler.

    This should be called during application shutdown.
    """
    global _scheduler

    if _scheduler is None or not _scheduler.running:
        return

    _scheduler.shutdown()
    logger.info("Reminder scheduler stopped")


def get_scheduler() -> AsyncIOScheduler | None:
    """Get the global scheduler instance."""
    return _scheduler


async def load_and_schedule_reminders():
    """Load pending reminders from database and ensure they're tracked.

    This is called on startup to pick up any reminders that were set
    while the server was down.
    """
    import asyncpg
    from cassey.config.settings import settings

    # Query pending reminder count
    conn = await asyncpg.connect(settings.POSTGRES_URL)
    try:
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM reminders WHERE status = 'pending'"
        )
    finally:
        await conn.close()

    logger.info(f"Loaded {count} pending reminders from database")
