from fastapi import APIRouter, Query

router = APIRouter(prefix="/memories", tags=["memories"])


@router.get("/observations")
async def list_observations(
    user_id: str = "default_user",
    workspace_id: str = "personal",
    days: int = 7,
    limit: int = 50,
):
    """List recent observations."""
    from src.storage.memory import get_memory_store
    store = get_memory_store(user_id, workspace_id)
    results = store.get_recent_observations(days=days, limit=limit)
    return {"observations": results}


@router.get("/reflections")
async def list_reflections(
    user_id: str = "default_user",
    workspace_id: str = "personal",
    limit: int = 20,
):
    """List reflections (patterns and insights)."""
    from src.storage.memory import get_memory_store
    store = get_memory_store(user_id, workspace_id)
    results = store.get_reflections(limit=limit)
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
    from src.storage.memory import get_memory_store
    store = get_memory_store(user_id, workspace_id)
    results = store.search_reflections(query, method=method, limit=limit)
    for r in results:
        store.boost_reflection(r["id"])
    return {"query": query, "method": method, "results": results}


@router.post("/observations/search")
async def search_observations(
    query: str = Query(...),
    limit: int = 10,
    user_id: str = "default_user",
    workspace_id: str = "personal",
):
    """Search observations."""
    from src.storage.memory import get_memory_store
    store = get_memory_store(user_id, workspace_id)
    results = store.search_observations(query, limit=limit)
    return {"query": query, "results": results}


@router.delete("/clear")
async def clear_memories(
    user_id: str = "default_user",
    workspace_id: str = "personal",
):
    """Reset memory store cache."""
    from src.storage.memory import clear_memory_store_cache
    clear_memory_store_cache()
    return {"status": "cleared", "user_id": user_id, "workspace_id": workspace_id}
