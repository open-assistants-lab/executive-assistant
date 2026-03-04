"""Subagent scheduler using APScheduler."""

import uuid
from datetime import datetime
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from src.agents.subagent.manager import get_subagent_manager
from src.app_logging import get_logger

logger = get_logger()

_scheduler: BackgroundScheduler | None = None
_jobs: dict[str, dict[str, Any]] = {}


def get_scheduler() -> BackgroundScheduler:
    """Get or create the global scheduler."""
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler()
        _scheduler.start()
        logger.info("subagent.scheduler.started", {}, user_id="system")
    return _scheduler


def schedule_once(
    user_id: str,
    subagent_name: str,
    task: str,
    run_at: datetime,
) -> str:
    """Schedule a one-time subagent execution.

    Args:
        user_id: User ID
        subagent_name: Subagent to invoke
        task: Task description
        run_at: When to run

    Returns:
        Job ID
    """
    job_id = f"subagent_{uuid.uuid4().hex[:8]}"

    scheduler = get_scheduler()

    def _run():
        manager = get_subagent_manager(user_id)
        result = manager.invoke(subagent_name, task)
        _jobs[job_id] = {
            "status": "completed" if result.get("success") else "failed",
            "result": result,
            "completed_at": datetime.now().isoformat(),
        }
        logger.info(
            "subagent.scheduled_run_completed",
            {"job_id": job_id, "success": result.get("success")},
            user_id=user_id,
        )

    scheduler.add_job(_run, trigger=DateTrigger(run_date=run_at), id=job_id)

    _jobs[job_id] = {
        "user_id": user_id,
        "subagent_name": subagent_name,
        "task": task,
        "schedule_type": "once",
        "run_at": run_at.isoformat(),
        "status": "scheduled",
        "created_at": datetime.now().isoformat(),
    }

    logger.info(
        "subagent.scheduled",
        {"job_id": job_id, "subagent_name": subagent_name, "run_at": run_at.isoformat()},
        user_id=user_id,
    )

    return job_id


def schedule_recurring(
    user_id: str,
    subagent_name: str,
    task: str,
    cron: str,
) -> str:
    """Schedule a recurring subagent execution.

    Args:
        user_id: User ID
        subagent_name: Subagent to invoke
        task: Task description
        cron: Cron expression (e.g., "0 9 * * *" for daily 9am)

    Returns:
        Job ID
    """
    job_id = f"recurring_{uuid.uuid4().hex[:8]}"

    scheduler = get_scheduler()

    def _run():
        manager = get_subagent_manager(user_id)
        result = manager.invoke(subagent_name, task)
        logger.info(
            "subagent.recurring_run_completed",
            {"job_id": job_id, "success": result.get("success")},
            user_id=user_id,
        )

    try:
        trigger = CronTrigger.from_crontab(cron)
    except Exception as e:
        raise ValueError(f"Invalid cron expression: {e}")

    scheduler.add_job(_run, trigger=trigger, id=job_id)

    _jobs[job_id] = {
        "user_id": user_id,
        "subagent_name": subagent_name,
        "task": task,
        "schedule_type": "recurring",
        "cron": cron,
        "status": "scheduled",
        "created_at": datetime.now().isoformat(),
    }

    logger.info(
        "subagent.scheduled_recurring",
        {"job_id": job_id, "subagent_name": subagent_name, "cron": cron},
        user_id=user_id,
    )

    return job_id


def cancel_job(job_id: str) -> bool:
    """Cancel a scheduled job.

    Args:
        job_id: Job ID to cancel

    Returns:
        True if cancelled, False if not found
    """
    scheduler = get_scheduler()
    job = scheduler.get_job(job_id)
    if job:
        job.remove()
        if job_id in _jobs:
            _jobs[job_id]["status"] = "cancelled"
        logger.info("subagent.job_cancelled", {"job_id": job_id})
        return True
    return False


def list_jobs(user_id: str | None = None) -> list[dict[str, Any]]:
    """List all scheduled jobs.

    Args:
        user_id: Optional filter by user

    Returns:
        List of job info dicts
    """
    jobs = []
    for job_id, info in _jobs.items():
        if user_id is None or info.get("user_id") == user_id:
            jobs.append({"job_id": job_id, **info})
    return jobs


def get_job_status(job_id: str) -> dict[str, Any] | None:
    """Get status of a job.

    Args:
        job_id: Job ID

    Returns:
        Job info or None if not found
    """
    if job_id not in _jobs:
        return None
    return {"job_id": job_id, **_jobs[job_id]}
