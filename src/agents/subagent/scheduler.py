"""Subagent scheduler using APScheduler."""

import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_MISSED
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from src.app_logging import get_logger

logger = get_logger()

JOBS_DB_PATH = Path("data/jobs.db")
RESULTS_DB_PATH = Path("data/jobs_results.db")

_jobstores: dict = {}
_scheduler: BackgroundScheduler | None = None


def _init_results_db():
    """Initialize results database."""
    RESULTS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(RESULTS_DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS job_results (
            job_id TEXT PRIMARY KEY,
            user_id TEXT,
            subagent_name TEXT,
            task TEXT,
            status TEXT,
            result TEXT,
            error TEXT,
            completed_at TEXT,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()


def _save_job_result(
    job_id: str,
    user_id: str,
    subagent_name: str,
    task: str,
    status: str,
    result: dict | None = None,
    error: str | None = None,
):
    """Save job result to database."""
    conn = sqlite3.connect(RESULTS_DB_PATH)
    conn.execute(
        """
        INSERT OR REPLACE INTO job_results 
        (job_id, user_id, subagent_name, task, status, result, error, completed_at, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            job_id,
            user_id,
            subagent_name,
            task,
            status,
            json.dumps(result) if result else None,
            error,
            datetime.now().isoformat(),
            datetime.now().isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def get_job_status(job_id: str) -> dict[str, Any] | None:
    """Get status of a job from database."""
    conn = sqlite3.connect(RESULTS_DB_PATH)
    cursor = conn.execute(
        "SELECT job_id, user_id, subagent_name, task, status, result, error, completed_at FROM job_results WHERE job_id = ?",
        (job_id,),
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "job_id": row[0],
        "user_id": row[1],
        "subagent_name": row[2],
        "task": row[3],
        "status": row[4],
        "result": json.loads(row[5]) if row[5] else None,
        "error": row[6],
        "completed_at": row[7],
    }


def _get_jobstores() -> dict:
    """Get jobstores dict with SQLite persistence."""
    global _jobstores
    if not _jobstores:
        JOBS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _jobstores = {
            "default": SQLAlchemyJobStore(url=f"sqlite:///{JOBS_DB_PATH}"),
        }
        _init_results_db()
    return _jobstores


def get_scheduler() -> BackgroundScheduler:
    """Get or create the global scheduler."""
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler(jobstores=_get_jobstores())

        def job_missed(event):
            logger.warning(
                "subagent.job_missed",
                {"job_id": event.job_id, "scheduled_run_time": str(event.scheduled_run_time)},
                user_id="system",
            )

        def job_executed(event):
            if event.exception:
                logger.error(
                    "subagent.job_failed",
                    {"job_id": event.job_id, "exception": str(event.exception)},
                    user_id="system",
                )

        _scheduler.add_listener(job_missed, EVENT_JOB_MISSED)
        _scheduler.add_listener(job_executed, EVENT_JOB_EXECUTED)

        _scheduler.start()
        logger.info("subagent.scheduler.started", {}, user_id="system")
    return _scheduler


def _run_subagent_job(user_id: str, subagent_name: str, task: str, job_id: str) -> None:
    """Module-level function to run subagent job (picklable)."""
    from src.agents.subagent.manager import get_subagent_manager

    logger.info(
        "subagent.job_executing",
        {"job_id": job_id, "subagent_name": subagent_name},
        user_id=user_id,
    )

    try:
        manager = get_subagent_manager(user_id)
        result = manager.invoke(subagent_name, task)
        _save_job_result(
            job_id=job_id,
            user_id=user_id,
            subagent_name=subagent_name,
            task=task,
            status="completed" if result.get("success") else "failed",
            result=result,
        )
        logger.info(
            "subagent.scheduled_run_completed",
            {"job_id": job_id, "success": result.get("success")},
            user_id=user_id,
        )
    except Exception as e:
        _save_job_result(
            job_id=job_id,
            user_id=user_id,
            subagent_name=subagent_name,
            task=task,
            status="failed",
            error=str(e),
        )
        logger.error(
            "subagent.scheduled_run_failed",
            {"job_id": job_id, "error": str(e)},
            user_id=user_id,
        )
        raise  # Re-raise so APScheduler marks job as failed


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

    scheduler.add_job(
        _run_subagent_job,
        trigger=DateTrigger(run_date=run_at),
        id=job_id,
        args=[user_id, subagent_name, task, job_id],
    )

    _save_job_result(
        job_id=job_id,
        user_id=user_id,
        subagent_name=subagent_name,
        task=task,
        status="scheduled",
    )

    logger.info(
        "subagent.scheduled",
        {"job_id": job_id, "subagent_name": subagent_name, "run_at": run_at.isoformat()},
        user_id=user_id,
    )

    return job_id


def schedule_now(
    user_id: str,
    subagent_name: str,
    task: str,
) -> str:
    """Schedule a subagent to run immediately (async).

    Args:
        user_id: User ID
        subagent_name: Subagent to invoke
        task: Task description

    Returns:
        Job ID
    """
    return schedule_once(user_id, subagent_name, task, datetime.now())


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

    try:
        trigger = CronTrigger.from_crontab(cron)
    except Exception as e:
        raise ValueError(f"Invalid cron expression: {e}")

    scheduler.add_job(
        _run_subagent_job,
        trigger=trigger,
        id=job_id,
        args=[user_id, subagent_name, task, job_id],
    )

    _save_job_result(
        job_id=job_id,
        user_id=user_id,
        subagent_name=subagent_name,
        task=task,
        status="scheduled",
    )

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
        _save_job_result(job_id=job_id, user_id="", subagent_name="", task="", status="cancelled")
        return True
    return False


def list_jobs(user_id: str | None = None) -> list[dict[str, Any]]:
    """List all scheduled jobs.

    Args:
        user_id: Optional filter by user

    Returns:
        List of job info dicts
    """
    conn = sqlite3.connect(RESULTS_DB_PATH)
    if user_id:
        cursor = conn.execute(
            "SELECT job_id, user_id, subagent_name, task, status FROM job_results WHERE user_id = ?",
            (user_id,),
        )
    else:
        cursor = conn.execute(
            "SELECT job_id, user_id, subagent_name, task, status FROM job_results"
        )
    jobs = []
    for row in cursor.fetchall():
        jobs.append(
            {
                "job_id": row[0],
                "user_id": row[1],
                "subagent_name": row[2],
                "task": row[3],
                "status": row[4],
            }
        )
    conn.close()
    return jobs
