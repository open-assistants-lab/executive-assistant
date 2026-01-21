"""Scheduler for reminder notifications and scheduled job handling using APScheduler.

This module runs as a background task, polling the database for:
1. Pending reminders - sends notifications
2. Scheduled jobs - archived (orchestrator/worker agents are disabled)
"""

import asyncio
import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from executive_assistant.config.settings import settings
from executive_assistant.logging import format_log_context
from executive_assistant.storage.file_sandbox import set_thread_id, clear_thread_id
from executive_assistant.storage.reminder import ReminderStorage, get_reminder_storage
from executive_assistant.storage.scheduled_jobs import get_scheduled_job_storage
from executive_assistant.utils.cron import parse_cron_next

logger = logging.getLogger(__name__)

# Archived orchestrator constants
ORCHESTRATOR_ARCHIVED = True
ARCHIVED_MESSAGE = (
    "Orchestrator/worker agents are archived and disabled. "
    "Use the LangChain runtime and direct tools instead."
)

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

                if reminder.is_recurring:
                    try:
                        next_due = parse_cron_next(reminder.recurrence, now)
                        next_reminder = await storage.create(
                            user_id=reminder.user_id,
                            thread_ids=reminder.thread_ids,
                            message=reminder.message,
                            due_time=next_due,
                            recurrence=reminder.recurrence,
                        )
                        logger.info(
                            f"Created next reminder {next_reminder.id} for recurring reminder {reminder.id} at {next_due}"
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to create next instance for recurring reminder {reminder.id}: {e}"
                        )
            else:
                await storage.mark_failed(
                    reminder.id, f"Failed to send via {channel}"
                )
                logger.error(f"Reminder {reminder.id} failed to send")

    except Exception as e:
        logger.error(f"Error processing pending reminders: {e}")


async def _process_pending_jobs():
    """Check for and process pending scheduled jobs.

    This is called periodically by the scheduler.
    Scheduled jobs are archived and marked as failed.
    """
    storage = await get_scheduled_job_storage()

    # Get jobs due now or in the past
    now = datetime.now()
    # Look back 1 minute to catch any we might have missed
    lookback = now - timedelta(minutes=1)

    try:
        pending = await storage.get_due_jobs(now)

        if not pending:
            return

        logger.info(f"Processing {len(pending)} pending scheduled job(s)")

        # Mark all due jobs as failed with archived message
        for job in pending:
            await storage.mark_failed(job.id, ARCHIVED_MESSAGE)

        logger.info("Scheduled jobs are archived; marked due jobs as failed.")

    except Exception as e:
        logger.error(f"Error processing pending jobs: {e}")


async def start_scheduler():
    """Start the scheduler for reminders and scheduled jobs.

    This should be called during application startup.
    """
    global _scheduler

    if _scheduler is not None and _scheduler.running:
        logger.warning("Scheduler already running")
        return

    _scheduler = AsyncIOScheduler()

    # Run at second 0 of every minute to align scans
    _scheduler.add_job(
        _process_pending_reminders,
        CronTrigger(second=0),
        id="check_pending_reminders",
        replace_existing=True,
    )

    # Run at second 0 of every minute to align scans
    _scheduler.add_job(
        _process_pending_jobs,
        CronTrigger(second=0),
        id="check_pending_jobs",
        replace_existing=True,
    )

    _scheduler.start()
    ctx = format_log_context("system", component="scheduler")
    logger.info(f"{ctx} started (reminders; scheduled jobs archived)")
    logger.debug(f"{ctx} start_scheduler returning")


async def stop_scheduler():
    """Stop the scheduler.

    This should be called during application shutdown.
    """
    global _scheduler

    if _scheduler is None or not _scheduler.running:
        return

    _scheduler.shutdown()
    ctx = format_log_context("system", component="scheduler")
    logger.info(f"{ctx} stopped")


def get_scheduler() -> AsyncIOScheduler | None:
    """Get the global scheduler instance."""
    return _scheduler


async def load_and_schedule_reminders():
    """Load pending reminders from database and ensure they're tracked.

    This is called on startup to pick up any reminders that were set
    while the server was down.
    """
    import asyncpg
    from executive_assistant.config.settings import settings
    # Query pending reminder count
    conn = await asyncpg.connect(settings.POSTGRES_URL)
    try:
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM reminders WHERE status = 'pending'"
        )
    finally:
        await conn.close()

    ctx = format_log_context("system", component="scheduler")
    logger.info(f"{ctx} loaded pending_reminders={count}")
