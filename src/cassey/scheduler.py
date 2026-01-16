"""Scheduler for reminder notifications and scheduled job handling using APScheduler.

This module runs as a background task, polling the database for:
1. Pending reminders - sends notifications
2. Scheduled jobs - archived (orchestrator/worker agents are disabled)
"""

import asyncio
import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from cassey.config.settings import settings
from cassey.storage.file_sandbox import set_thread_id, clear_thread_id
from cassey.storage.reminder import ReminderStorage, get_reminder_storage
from cassey.storage.scheduled_jobs import get_scheduled_job_storage
from cassey.tools.orchestrator_tools import (
    ARCHIVED_MESSAGE,
    ORCHESTRATOR_ARCHIVED,
    execute_worker,
)
from cassey.utils.cron import parse_cron_next

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
    Jobs are executed synchronously within the timeout period.
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

        if ORCHESTRATOR_ARCHIVED:
            for job in pending:
                await storage.mark_failed(job.id, ARCHIVED_MESSAGE)
            logger.info("Archived scheduled jobs are disabled; marked due jobs as failed.")
            return

        for job in pending:
            # Mark as running
            await storage.mark_started(job.id, now)

            logger.info(f"Executing job {job.id}: {job.task[:50]}...")

            # Get worker if specified
            from cassey.storage.workers import get_worker_storage

            worker = None
            if job.worker_id:
                worker_storage = await get_worker_storage()
                worker = await worker_storage.get_by_id(job.worker_id)

            # Set thread_id context for worker execution
            set_thread_id(job.thread_id)

            try:
                # Execute the job
                if worker:
                    # Execute with worker
                    result, error = await execute_worker(
                        worker=worker,
                        task=job.task,
                        flow=job.flow,
                        thread_id=job.thread_id,
                        timeout=30,
                    )
                else:
                    # No worker - simple execution (use python tool)
                    result, error = await _execute_simple_job(job)

                # Record result
                if error:
                    await storage.mark_failed(job.id, error)
                    logger.error(f"Job {job.id} failed: {error}")
                else:
                    await storage.mark_completed(job.id, result)
                    logger.info(f"Job {job.id} completed successfully")

                    # Handle recurrence - create next instance
                    if job.is_recurring:
                        try:
                            next_due = parse_cron_next(job.cron, now)
                            next_job = await storage.create_next_instance(job, next_due)
                            logger.info(f"Created next instance {next_job.id} at {next_due}")
                        except Exception as e:
                            logger.error(f"Failed to create next instance: {e}")
            finally:
                # Clean up thread_id to avoid leaking thread-local fallback
                clear_thread_id()

    except Exception as e:
        logger.error(f"Error processing pending jobs: {e}")


async def _execute_simple_job(job) -> tuple[str | None, str | None]:
    """Execute a simple job without a dedicated worker.

    Uses the Python tool for basic execution.

    Args:
        job: ScheduledJob instance

    Returns:
        Tuple of (result, error)
    """
    from cassey.tools.python_tool import execute_python

    # Try to execute the flow as Python code
    # This is a simplified execution - workers are better for complex tasks

    # For simple notification jobs, create a message file
    job_name = job.name or f"job_{job.id}"

    # Build simple execution based on flow
    code_lines = []
    flow_lower = job.flow.lower()

    # Parse the flow for basic patterns
    if "notify" in flow_lower or "alert" in flow_lower or "send" in flow_lower:
        # Create a message file for notification
        message_content = f"Task: {job.task}\n"
        code_lines.append(f"with open('{job_name}_message.txt', 'w') as f:")
        code_lines.append(f"    f.write('''{message_content}''')")
        code_lines.append("result = 'Notification created'")

    # Add any user-specified Python code from the flow
    if "```python" in job.flow or "```" in job.flow:
        # Extract code block
        import re
        code_match = re.search(r"```(?:python)?\n(.*?)```", job.flow, re.DOTALL)
        if code_match:
            code_lines.append(code_match.group(1))

    if code_lines:
        code = "\n".join(code_lines)
        try:
            result = execute_python(code)
            return result, None
        except Exception as e:
            return None, str(e)

    return f"Job executed: {job.task}", None


async def start_scheduler():
    """Start the scheduler for reminders and scheduled jobs.

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

    # Add job to check for pending scheduled jobs every 60 seconds
    _scheduler.add_job(
        _process_pending_jobs,
        IntervalTrigger(seconds=60),
        id="check_pending_jobs",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info("Scheduler started (reminders; scheduled jobs archived)")


async def stop_scheduler():
    """Stop the scheduler.

    This should be called during application shutdown.
    """
    global _scheduler

    if _scheduler is None or not _scheduler.running:
        return

    _scheduler.shutdown()
    logger.info("Scheduler stopped")


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
