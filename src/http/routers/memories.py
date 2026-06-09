from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Query

router = APIRouter(prefix="/memories", tags=["memories"])


def _get_core(user_id: str, workspace_id: str):
    from src.storage.messages import get_message_store
    return get_message_store(user_id, workspace_id).core


@router.get("/observations")
async def list_observations(
    user_id: str = "default_user",
    workspace_id: str = "personal",
    days: int = 7,
    limit: int = 50,
):
    """List recent observations."""
    core = _get_core(user_id, workspace_id)
    cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
    results = core.get_observations(ts_after=cutoff, limit=limit)
    return {"observations": results}


@router.get("/reflections")
async def list_reflections(
    user_id: str = "default_user",
    workspace_id: str = "personal",
    limit: int = 20,
):
    """List reflections (patterns and insights)."""
    core = _get_core(user_id, workspace_id)
    results = core.get_reflections(limit=limit)
    return {"reflections": results}


@router.post("/reflections/search")
async def search_reflections(
    query: str = Query(...),
    method: str = "hybrid",
    limit: int = 5,
    user_id: str = "default_user",
    workspace_id: str = "personal",
):
    """Search reflections."""
    core = _get_core(user_id, workspace_id)
    results = core.search_reflections(query, limit=limit)
    return {"query": query, "method": method, "results": results}


@router.post("/observations/search")
async def search_observations(
    query: str = Query(...),
    limit: int = 10,
    user_id: str = "default_user",
    workspace_id: str = "personal",
):
    """Search observations."""
    core = _get_core(user_id, workspace_id)
    results = core.search_observations(query, limit=limit)
    return {"query": query, "results": results}


@router.delete("/clear")
async def clear_memories(
    user_id: str = "default_user",
    workspace_id: str = "personal",
):
    """Delete all messages, observations, and reflections for the user."""
    core = _get_core(user_id, workspace_id)
    core.clear()
    core._db.raw_query("DELETE FROM observations")
    core._db.raw_query("DELETE FROM reflections")
    return {"status": "cleared", "user_id": user_id, "workspace_id": workspace_id}
