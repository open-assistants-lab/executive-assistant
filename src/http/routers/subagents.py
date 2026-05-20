"""Subagent management API for Flutter client - workspace-scoped."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, ValidationError

from src.sdk.subagent_models import AgentDef, TaskStatus

tools_router = APIRouter(tags=["tools"])

router = APIRouter(prefix="/subagents", tags=["subagents"])


@tools_router.get("/tools/names")
async def list_tool_names(
    user_id: str = Query("default_user"),
    workspace_id: str = Query("personal"),
):
    from src.sdk.native_tools import get_native_tool_names

    names = sorted(get_native_tool_names())
    return {"tools": names, "count": len(names)}


class SubagentCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    description: str = ""
    model: str | None = None
    provider_options: dict[str, Any] = Field(default_factory=dict)
    skills: list[str] = Field(default_factory=list)
    tools: list[str] | None = None
    system_prompt: str | None = None
    max_llm_calls: int = 50
    cost_limit_usd: float = 1.0
    timeout_seconds: int = 300
    output_schema: dict[str, Any] | None = None
    handoff_instructions: str | None = None
    artifact_policy: str | None = None


class SubagentUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    description: str | None = None
    model: str | None = None
    provider_options: dict[str, Any] | None = None
    skills: list[str] | None = None
    tools: list[str] | None = None
    system_prompt: str | None = None
    max_llm_calls: int | None = None
    cost_limit_usd: float | None = None
    timeout_seconds: int | None = None
    output_schema: dict[str, Any] | None = None
    handoff_instructions: str | None = None
    artifact_policy: str | None = None


class SubagentStartRequest(BaseModel):
    task: str = Field(..., min_length=1)
    parent_id: str | None = None


class SubagentInstructionRequest(BaseModel):
    instruction: str = Field(..., min_length=1)


def _parse_json_field(value: Any) -> Any:
    if not isinstance(value, str) or not value:
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _serialize_job(row: dict[str, Any]) -> dict[str, Any]:
    job = dict(row)
    job["progress"] = _parse_json_field(job.get("progress")) or {}
    job["result"] = _parse_json_field(job.get("result"))
    job["instructions"] = _parse_json_field(job.get("instructions")) or []
    return job


def _validate_context_ids(user_id: str, workspace_id: str) -> None:
    from src.storage.paths import get_paths

    try:
        get_paths(user_id, workspace_id=workspace_id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.get("")
async def list_subagents(
    user_id: str = Query("default_user"),
    workspace_id: str = Query("personal"),
):
    from src.sdk.coordinator import get_coordinator

    _validate_context_ids(user_id, workspace_id)
    coordinator = get_coordinator(user_id, workspace_id)
    scoped_defs = await coordinator.list_defs_with_scope()

    return {
        "agents": [
            {
                "name": d.name,
                "description": d.description or "",
                "model": d.model,
                "tools": d.tools,
                "skills": d.skills,
                "system_prompt": d.system_prompt,
                "max_llm_calls": d.max_llm_calls,
                "cost_limit_usd": d.cost_limit_usd,
                "timeout_seconds": d.timeout_seconds,
                "provider_options": d.provider_options,
                "output_schema": d.output_schema,
                "handoff_instructions": d.handoff_instructions,
                "artifact_policy": d.artifact_policy,
                "scope": scope,
            }
            for d, scope in scoped_defs
        ]
    }


@router.post("")
async def create_subagent(
    body: SubagentCreateRequest,
    user_id: str = Query("default_user"),
    workspace_id: str = Query("personal"),
):
    from src.sdk.coordinator import get_coordinator, validate_agent_def

    _validate_context_ids(user_id, workspace_id)
    coordinator = get_coordinator(user_id, workspace_id)
    if coordinator.load_def(body.name) is not None:
        raise HTTPException(status_code=400, detail=f"Subagent '{body.name}' already exists.")

    try:
        agent_def = AgentDef(**body.model_dump(), workspace_id=workspace_id)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors()) from e

    errors = validate_agent_def(agent_def, user_id=user_id, workspace_id=workspace_id)
    if errors:
        raise HTTPException(status_code=400, detail={"errors": errors})

    await coordinator.create(agent_def)
    return {"status": "created", "name": body.name, "workspace_id": workspace_id}


@router.get("/jobs")
async def list_subagent_jobs(
    user_id: str = Query("default_user"),
    workspace_id: str = Query("personal"),
    status: TaskStatus | None = Query(None),
):
    from src.sdk.work_queue import get_work_queue

    _validate_context_ids(user_id, workspace_id)
    db = await get_work_queue(user_id, workspace_id)
    jobs = await db.check_progress(status=status)
    return {"jobs": [_serialize_job(job) for job in jobs]}


@router.get("/jobs/{job_id}")
async def get_subagent_job(
    job_id: str,
    user_id: str = Query("default_user"),
    workspace_id: str = Query("personal"),
):
    from src.sdk.work_queue import get_work_queue

    _validate_context_ids(user_id, workspace_id)
    db = await get_work_queue(user_id, workspace_id)
    row = await db.get_task(job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job": _serialize_job(row)}


@router.post("/jobs/{job_id}/instructions")
async def instruct_subagent_job(
    job_id: str,
    body: SubagentInstructionRequest,
    user_id: str = Query("default_user"),
    workspace_id: str = Query("personal"),
):
    from src.sdk.coordinator import get_coordinator
    from src.sdk.work_queue import get_work_queue

    _validate_context_ids(user_id, workspace_id)
    db = await get_work_queue(user_id, workspace_id)
    if await db.get_task(job_id) is None:
        raise HTTPException(status_code=404, detail="Job not found")

    coordinator = get_coordinator(user_id, workspace_id)
    if not await coordinator.instruct(job_id, body.instruction):
        raise HTTPException(status_code=404, detail="Job not found")
    return {"status": "instruction_added", "job_id": job_id}


@router.post("/jobs/{job_id}/cancel")
async def cancel_subagent_job(
    job_id: str,
    user_id: str = Query("default_user"),
    workspace_id: str = Query("personal"),
):
    from src.sdk.coordinator import get_coordinator
    from src.sdk.work_queue import get_work_queue

    _validate_context_ids(user_id, workspace_id)
    db = await get_work_queue(user_id, workspace_id)
    if await db.get_task(job_id) is None:
        raise HTTPException(status_code=404, detail="Job not found")

    coordinator = get_coordinator(user_id, workspace_id)
    if not await coordinator.cancel(job_id):
        raise HTTPException(status_code=404, detail="Job not found")
    return {"status": "cancel_requested", "job_id": job_id}


@router.patch("/{name}")
async def update_subagent(
    name: str,
    body: SubagentUpdateRequest,
    user_id: str = Query("default_user"),
    workspace_id: str = Query("personal"),
):
    from src.sdk.coordinator import get_coordinator, validate_agent_def

    _validate_context_ids(user_id, workspace_id)
    coordinator = get_coordinator(user_id, workspace_id)
    update_data = body.model_dump(exclude_unset=True)
    update_data.pop("name", None)

    current = coordinator.load_def(name)
    if current is None:
        raise HTTPException(status_code=404, detail=f"Subagent '{name}' not found.")

    candidate_data = current.model_dump()
    candidate_data.update({k: v for k, v in update_data.items() if v is not None})
    try:
        candidate = AgentDef(**candidate_data)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors()) from e

    errors = validate_agent_def(candidate, user_id=user_id, workspace_id=workspace_id)
    if errors:
        raise HTTPException(status_code=400, detail={"errors": errors})

    updated = await coordinator.update(name, **update_data)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Subagent '{name}' not found.")
    return {"status": "updated", "subagent": updated.model_dump()}


@router.delete("/{name}")
async def delete_subagent(
    name: str,
    user_id: str = Query("default_user"),
    workspace_id: str = Query("personal"),
):
    from src.sdk.coordinator import get_coordinator

    _validate_context_ids(user_id, workspace_id)
    coordinator = get_coordinator(user_id, workspace_id)
    if not await coordinator.delete(name):
        raise HTTPException(status_code=404, detail=f"Subagent '{name}' not found.")
    return {"status": "deleted", "name": name, "workspace_id": workspace_id}


@router.post("/{name}/start")
async def start_subagent(
    name: str,
    body: SubagentStartRequest,
    user_id: str = Query("default_user"),
    workspace_id: str = Query("personal"),
):
    from src.sdk.coordinator import get_coordinator

    _validate_context_ids(user_id, workspace_id)
    coordinator = get_coordinator(user_id, workspace_id)
    try:
        task_id = await coordinator.start(name, body.task, parent_id=body.parent_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"job_id": task_id, "status": "pending", "subagent": name}
