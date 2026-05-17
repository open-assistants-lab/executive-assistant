"""Subagent management API for Flutter client — workspace-scoped."""
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/subagents", tags=["subagents"])


@router.get("")
async def list_subagents(
    user_id: str = Query("default_user"),
    workspace_id: str = Query("personal"),
):
    from src.sdk.coordinator import get_coordinator

    coordinator = get_coordinator(user_id, workspace_id)
    defs = await coordinator.list_defs()

    return {
        "subagents": [
            {
                "name": d.name,
                "description": d.description or "",
                "model": d.model,
                "tools": d.tools,
                "is_system": False,
            }
            for d in defs
        ]
    }


@router.post("")
async def create_subagent(
    name: str,
    user_id: str = Query("default_user"),
    workspace_id: str = Query("personal"),
    description: str = Query(""),
    model: str | None = Query(None),
    skills: str | None = Query(None),
    tools: str | None = Query(None),
    system_prompt: str | None = Query(None),
    mcp_config: str | None = Query(None),
    max_llm_calls: int = Query(50),
    cost_limit_usd: float = Query(1.0),
    timeout_seconds: int = Query(300),
):
    from src.sdk.coordinator import get_coordinator
    from src.sdk.subagent_models import AgentDef

    tool_list: list[str] | None = None
    if tools:
        tool_list = [t.strip() for t in tools.split(",") if t.strip()]

    skill_list: list[str] = []
    if skills:
        skill_list = [s.strip() for s in skills.split(",") if s.strip()]

    mcp_dict = None
    if mcp_config:
        import json as _json
        try:
            mcp_dict = _json.loads(mcp_config)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid MCP config JSON")

    agent_def = AgentDef(
        name=name,
        description=description,
        model=model,
        system_prompt=system_prompt,
        tools=tool_list,
        skills=skill_list,
        max_llm_calls=max_llm_calls,
        cost_limit_usd=cost_limit_usd,
        timeout_seconds=timeout_seconds,
        mcp_config=mcp_dict,
    )

    coordinator = get_coordinator(user_id, workspace_id)

    existing = coordinator.load_def(name)
    if existing is not None:
        raise HTTPException(status_code=400, detail=f"Subagent '{name}' already exists.")

    await coordinator.create(agent_def)
    return {"status": "created", "name": name, "workspace_id": workspace_id}


@router.delete("/{subagent_name}")
async def delete_subagent(
    subagent_name: str,
    user_id: str = Query("default_user"),
    workspace_id: str = Query("personal"),
):
    import shutil

    from src.sdk.coordinator import get_coordinator

    coordinator = get_coordinator(user_id, workspace_id)
    agent_def = coordinator.load_def(subagent_name)
    if agent_def is None:
        raise HTTPException(status_code=404, detail=f"Subagent '{subagent_name}' not found.")

    agent_path = coordinator.base_path / subagent_name
    if agent_path.exists():
        shutil.rmtree(agent_path)

    return {"status": "deleted", "name": subagent_name, "workspace_id": workspace_id}


@router.get("/jobs")
async def list_subagent_jobs(
    user_id: str = Query("default_user"),
    workspace_id: str = Query("personal"),
):
    from src.sdk.coordinator import get_coordinator

    coordinator = get_coordinator(user_id, workspace_id)
    tasks = await coordinator.check_progress()
    return {"jobs": [{"id": t["id"], "status": t["status"], "agent_name": t["agent_name"]} for t in tasks]}


@router.get("/jobs/{job_id}")
async def get_subagent_job(
    job_id: str,
    user_id: str = Query("default_user"),
    workspace_id: str = Query("personal"),
):
    from src.sdk.coordinator import get_coordinator

    coordinator = get_coordinator(user_id, workspace_id)
    result = await coordinator.get_result(job_id)
    if result is None:
        tasks = await coordinator.check_progress()
        for t in tasks:
            if t["id"] == job_id:
                return {"job": t}
        return {"error": "Job not found"}, 404
    return {"job": {"id": job_id, "output": result.output, "success": result.success}}


@router.post("/invoke")
async def invoke_subagent(
    name: str,
    task: str,
    user_id: str = Query("default_user"),
    workspace_id: str = Query("personal"),
):
    from src.sdk.tools_core.subagent import subagent_start

    result = await subagent_start.ainvoke({
        "user_id": user_id,
        "workspace_id": workspace_id,
        "agent_name": name,
        "task": task,
    })
    return {"result": str(result)}


@router.post("/{task_id}/cancel")
async def cancel_subagent_job(
    task_id: str,
    user_id: str = Query("default_user"),
    workspace_id: str = Query("personal"),
):
    from src.sdk.coordinator import get_coordinator

    coordinator = get_coordinator(user_id, workspace_id)
    await coordinator.cancel(task_id)
    return {"status": "cancelled", "task_id": task_id}
