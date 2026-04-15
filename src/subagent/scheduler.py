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
from src.storage.paths import get_paths

logger = get_logger()


def _get_jobs_db_path() -> Path:
    return get_paths().jobs_db_path()


def _get_results_db_path() -> Path:
    return get_paths().jobs_results_db_path()


_jobstores: dict = {}
_scheduler: BackgroundScheduler | None = None


def _init_results_db():
    """Initialize results database."""
    results_path = _get_results_db_path()
    results_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(results_path)
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
    """Save job result to database. Preserves created_at on updates."""
    conn = sqlite3.connect(_get_results_db_path())
    existing = conn.execute(
        "SELECT created_at FROM job_results WHERE job_id = ?", (job_id,)
    ).fetchone()

    if existing:
        conn.execute(
            """
            UPDATE job_results
            SET user_id = ?, subagent_name = ?, task = ?, status = ?,
                result = ?, error = ?, completed_at = ?
            WHERE job_id = ?
        """,
            (
                user_id,
                subagent_name,
                task,
                status,
                json.dumps(result) if result else None,
                error,
                datetime.now().isoformat(),
                job_id,
            ),
        )
    else:
        conn.execute(
            """
            INSERT INTO job_results
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
    conn = sqlite3.connect(_get_results_db_path())
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
        jobs_path = _get_jobs_db_path()
        jobs_path.parent.mkdir(parents=True, exist_ok=True)
        _jobstores = {
            "default": SQLAlchemyJobStore(url=f"sqlite:///{jobs_path}"),
        }
        _init_results_db()
    return _jobstores


def get_scheduler() -> BackgroundScheduler:
    """Get or create the global scheduler."""
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler(
            jobstores=_get_jobstores(),
            misfire_grace_time=300,
        )

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
        _restore_scheduled_jobs(_scheduler)
        logger.info("subagent.scheduler.started", {}, user_id="system")
    return _scheduler


def _restore_scheduled_jobs(scheduler: BackgroundScheduler) -> None:
    """Restore scheduled jobs from results DB on startup."""
    conn = sqlite3.connect(_get_results_db_path())
    cursor = conn.execute(
        "SELECT job_id, user_id, subagent_name, task FROM job_results WHERE status = 'scheduled'"
    )
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return

    logger.info("subagent.restoring_jobs", {"count": len(rows)}, user_id="system")

    for job_id, user_id, subagent_name, task in rows:
        try:
            from datetime import timedelta

            run_at = datetime.now() + timedelta(seconds=30)
            scheduler.add_job(
                _run_subagent_job,
                trigger=DateTrigger(run_date=run_at),
                id=job_id,
                args=[user_id, subagent_name, task, job_id],
                replace_existing=True,
            )
            logger.info("subagent.job_restored", {"job_id": job_id}, user_id=user_id)
        except Exception as e:
            logger.error(
                "subagent.job_restore_failed",
                {"job_id": job_id, "error": str(e)},
                user_id=user_id,
            )


def _run_subagent_job(user_id: str, subagent_name: str, task: str, job_id: str) -> None:
    """Module-level function to run subagent job (picklable)."""
    from src.subagent.manager import get_subagent_manager

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
        raise


def schedule_once(
    user_id: str,
    subagent_name: str,
    task: str,
    run_at: datetime,
) -> str:
    """Schedule a one-time subagent execution."""
    job_id = f"subagent_{uuid.uuid4().hex[:8]}"

    scheduler = get_scheduler()

    scheduler.add_job(
        _run_subagent_job,
        trigger=DateTrigger(run_date=run_at),
        id=job_id,
        args=[user_id, subagent_name, task, job_id],
        replace_existing=True,
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
    """Schedule a subagent to run immediately (async)."""
    return schedule_once(user_id, subagent_name, task, datetime.now())


def schedule_recurring(
    user_id: str,
    subagent_name: str,
    task: str,
    cron: str,
) -> str:
    """Schedule a recurring subagent execution."""
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
    """Cancel a scheduled job."""
    scheduler = get_scheduler()
    job = scheduler.get_job(job_id)
    if job:
        job.remove()
        conn = sqlite3.connect(_get_results_db_path())
        conn.execute(
            "UPDATE job_results SET status = 'cancelled', completed_at = ? WHERE job_id = ?",
            (datetime.now().isoformat(), job_id),
        )
        conn.commit()
        conn.close()
        return True
    return False


def list_jobs(user_id: str | None = None) -> list[dict[str, Any]]:
    """List all scheduled jobs."""
    conn = sqlite3.connect(_get_results_db_path())
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
