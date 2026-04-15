import json
import shutil

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/subagents", tags=["subagents"])


@router.get("")
async def list_subagents(user_id: str = "default"):
    """List all subagents."""
    from src.subagent.manager import get_subagent_manager

    manager = get_subagent_manager(user_id)
    subagents = manager.list_all()

    return {
        "subagents": [
            {
                "name": s["name"],
                "description": s.get("description", ""),
                "is_system": False,
            }
            for s in subagents
        ]
    }


@router.post("")
async def create_subagent(
    name: str,
    description: str = "",
    model: str | None = None,
    skills: list[str] | None = None,
    tools: list[str] | None = None,
    system_prompt: str | None = None,
    user_id: str = "default",
):
    """Create a new subagent."""
    from src.subagent.manager import get_subagent_manager

    manager = get_subagent_manager(user_id)
    subagent, result = manager.create(
        name=name,
        model=model,
        description=description,
        skills=skills,
        tools=tools,
        system_prompt=system_prompt,
    )

    if subagent is None:
        raise HTTPException(status_code=400, detail=result.get("errors", "Validation failed"))

    return {"status": "created", "name": name}


@router.delete("/{subagent_name}")
async def delete_subagent(subagent_name: str, user_id: str = "default"):
    """Delete a subagent."""
    from src.subagent.manager import get_subagent_manager

    manager = get_subagent_manager(user_id)
    subagent_path = manager.base_path / subagent_name
    if subagent_path.exists():
        shutil.rmtree(subagent_path)

    return {"status": "deleted", "name": subagent_name}


@router.get("/jobs")
async def list_subagent_jobs(user_id: str = "default"):
    """List all subagent jobs (scheduled, running, completed, failed)."""
    from src.subagent.scheduler import list_jobs

    jobs = list_jobs(user_id)
    return {"jobs": jobs}


@router.get("/jobs/{job_id}")
async def get_subagent_job(job_id: str):
    """Get status of a specific subagent job."""
    from src.subagent.scheduler import get_job_status

    status = get_job_status(job_id)
    if status is None:
        return {"error": "Job not found"}, 404
    return {"job": status}


@router.post("/invoke")
async def invoke_subagent(
    name: str,
    task: str,
    user_id: str = "default",
):
    """Invoke a subagent to execute a task (async)."""
    from src.subagent.tools import subagent_invoke

    result = subagent_invoke.invoke({"user_id": user_id, "name": name, "task": task})
    return {"result": str(result)}


@router.post("/batch")
async def batch_invoke_subagents(
    tasks: list[dict[str, str]],
    user_id: str = "default",
):
    """Batch invoke multiple subagents."""
    from src.subagent.tools import subagent_batch

    result = subagent_batch.invoke({"user_id": user_id, "tasks": json.dumps(tasks)})
    return {"result": str(result)}


@router.post("/schedule")
async def schedule_subagent(
    name: str,
    task: str,
    run_at: str | None = None,
    cron: str | None = None,
    user_id: str = "default",
):
    """Schedule a subagent task (one-time or recurring)."""
    from src.subagent.tools import subagent_schedule

    args = {"user_id": user_id, "name": name, "task": task}
    if run_at is not None:
        args["run_at"] = run_at
    if cron is not None:
        args["cron"] = cron
    result = subagent_schedule.invoke(args)
    return {"result": str(result)}


@router.delete("/jobs/{job_id}")
async def cancel_subagent_job(job_id: str, user_id: str = "default"):
    """Cancel a scheduled subagent job."""
    from src.subagent.tools import subagent_schedule_cancel

    result = subagent_schedule_cancel.invoke({"user_id": user_id, "job_id": job_id})
    return {"result": str(result)}
