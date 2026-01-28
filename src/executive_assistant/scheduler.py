"""Scheduler for reminder notifications and scheduled flow handling using APScheduler.

This module runs as a background task, polling the database for:
1. Pending reminders - sends notifications
2. Scheduled flows - executes flow chains
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
from executive_assistant.storage.scheduled_flows import get_scheduled_flow_storage
from executive_assistant.utils.cron import parse_cron_next

logger = logging.getLogger(__name__)

# Global scheduler instance
_scheduler: AsyncIOScheduler | None = None
_notification_handlers = {}


def register_notification_handler(channel: str, handler):
    """Register a notification handler for a channel.

    Args:
        channel: Channel name (e.g., 'telegram', 'http', 'email')
        handler: Async function that takes (thread_id, message) and sends notification
    """
    _notification_handlers[channel] = handler



async def send_notification(thread_id: str, message: str, channel: str) -> bool:
    """Public wrapper for sending notifications via registered handlers."""
    return await _send_notification(thread_id, message, channel)


async def _send_notification(thread_id: str, message: str, channel: str) -> bool:
    """Send notification through the appropriate channel.

    Args:
        thread_id: Thread ID to notify
        message: Message to send
        channel: Channel to use for sending

    Returns:
        True if successful, False otherwise
    """
    handler = _notification_handlers.get(channel)

    if handler:
        try:
            await handler(thread_id, message)
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
    try:
        pending = await storage.get_pending_reminders(now)

        if not pending:
            return

        logger.info(f"Processing {len(pending)} pending reminder(s)")

        for reminder in pending:
            # Determine channel from thread_id (e.g., "telegram:123" -> "telegram")
            if not reminder.thread_id:
                logger.warning(f"Reminder {reminder.id} has no thread_id")
                await storage.mark_failed(reminder.id, "No thread ID")
                continue

            # Use the first thread_id to determine channel
            thread_id = reminder.thread_id
            if ":" in thread_id:
                channel = thread_id.split(":")[0]
            else:
                channel = "unknown"

            try:
                # Send notification
                success = await _send_notification(
                    thread_id, reminder.message, channel
                )
            except Exception as e:
                logger.error(
                    f"Reminder {reminder.id} send failed via {channel}: {e}",
                    exc_info=True,
                )
                await storage.mark_failed(reminder.id, f"Send error via {channel}: {e}")
                continue

            if success:
                await storage.mark_sent(reminder.id, now)
                logger.info(f"Reminder {reminder.id} sent successfully")

                if reminder.is_recurring:
                    try:
                        next_due = parse_cron_next(reminder.recurrence, now)
                        next_reminder = await storage.create(
                            thread_id=reminder.thread_id,
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


async def _process_pending_flows():
    """Check for and process pending scheduled flows.

    This is called periodically by the scheduler.
    Scheduled flows are executed in-process.
    """
    storage = await get_scheduled_flow_storage()

    # Get flows due now or in the past
    now = datetime.now()
    try:
        pending = await storage.get_due_flows(now)

        if not pending:
            return

        logger.info(f"Processing {len(pending)} pending scheduled flow(s)")

        from executive_assistant.flows.runner import execute_flow

        for flow in pending:
            try:
                await execute_flow(flow)
            except Exception as e:
                logger.error(f"Flow {flow.id} execution failed: {e}", exc_info=True)

        logger.info("Scheduled flows processed.")

    except Exception as e:
        logger.error(f"Error processing pending flows: {e}")


async def start_scheduler():
    """Start the scheduler for reminders and scheduled flows.

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
        _process_pending_flows,
        CronTrigger(second=0),
        id="check_pending_flows",
        replace_existing=True,
    )

    _scheduler.start()
    ctx = format_log_context("system", component="scheduler")
    logger.info(f"{ctx} started (reminders; scheduled flows enabled)")
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
