from fastapi import APIRouter

from src.http.models import (
    ConnectionRequest,
    InsightSearchRequest,
    MemorySearchRequest,
    SearchAllRequest,
)

router = APIRouter(prefix="/memories", tags=["memories"])


@router.get("")
async def list_memories(
    user_id: str = "default",
    domain: str | None = None,
    memory_type: str | None = None,
    min_confidence: float = 0.0,
    limit: int = 100,
    scope: str | None = None,
    project_id: str | None = None,
):
    """List user memories/preferences."""
    from src.storage.memory import get_memory_store

    store = get_memory_store(user_id)
    memories = store.list_memories(
        domain=domain,
        memory_type=memory_type,
        min_confidence=min_confidence,
        limit=limit,
        scope=scope,
        project_id=project_id,
    )

    return {
        "memories": [
            {
                "id": m.id,
                "trigger": m.trigger,
                "action": m.action,
                "confidence": m.confidence,
                "domain": m.domain,
                "memory_type": m.memory_type,
                "source": m.source,
                "is_superseded": m.is_superseded,
                "superseded_by": m.superseded_by,
                "scope": m.scope,
                "project_id": m.project_id,
                "access_count": m.access_count,
                "structured_data": m.structured_data,
                "connections": [
                    {
                        "target_id": c.target_id,
                        "relationship": c.relationship,
                        "strength": c.strength,
                    }
                    for c in m.connections
                ],
                "updated_at": m.updated_at.isoformat() if m.updated_at else None,
            }
            for m in memories
        ]
    }


@router.post("")
async def add_memory(
    trigger: str,
    action: str,
    domain: str = "general",
    memory_type: str = "fact",
    user_id: str = "default",
):
    """Add a new memory entry."""
    from src.storage.memory import get_memory_store

    store = get_memory_store(user_id)
    memory = store.add_memory(
        trigger=trigger,
        action=action,
        domain=domain,
        memory_type=memory_type,
    )
    return {"memory": memory}


@router.put("/{memory_id}")
async def update_memory(
    memory_id: str,
    trigger: str | None = None,
    action: str | None = None,
    confidence: float | None = None,
    user_id: str = "default",
):
    """Update a memory entry."""
    from src.storage.memory import get_memory_store

    store = get_memory_store(user_id)
    updated = store.update_memory(
        memory_id,
        new_trigger=trigger,
        new_action=action,
    )
    if updated is None:
        return {"error": "Memory not found"}, 404
    return {"result": "Memory updated"}


@router.delete("/{memory_id}")
async def remove_memory(memory_id: str, user_id: str = "default"):
    """Remove a memory."""
    from src.storage.memory import get_memory_store

    store = get_memory_store(user_id)
    removed = store.remove_memory(memory_id)

    return {"status": "removed" if removed else "not_found", "id": memory_id}


@router.post("/search")
async def search_memories(request: MemorySearchRequest):
    """Search memories using keyword, semantic, hybrid, or field search."""
    from src.storage.memory import get_memory_store

    store = get_memory_store(request.user_id)

    if request.method == "fts":
        results = store.search_fts(request.query, limit=request.limit)
    elif request.method == "semantic":
        results = store.search_semantic(request.query, limit=request.limit)
    elif request.method == "field":
        results = store.search_field_semantic(request.query, limit=request.limit)
    else:
        results = store.search_hybrid(request.query, limit=request.limit)

    return {
        "query": request.query,
        "method": request.method,
        "results": [
            {
                "id": m.id,
                "trigger": m.trigger,
                "action": m.action,
                "confidence": m.confidence,
                "domain": m.domain,
                "memory_type": m.memory_type,
                "scope": m.scope,
                "project_id": m.project_id,
            }
            for m in results
        ],
    }


@router.post("/consolidate")
async def consolidate_memories(user_id: str = "default"):
    """Trigger memory consolidation manually."""
    from src.storage.consolidation import trigger_consolidation

    result = trigger_consolidation(user_id)
    return result


@router.get("/insights")
async def list_insights(user_id: str = "default", limit: int = 20, domain: str | None = None):
    """List synthesized insights from memory consolidation."""
    from src.storage.memory import get_memory_store

    store = get_memory_store(user_id)
    insights = store.list_insights(limit=limit, domain=domain)

    return {
        "insights": [
            {
                "id": i.id,
                "summary": i.summary,
                "domain": i.domain,
                "confidence": i.confidence,
                "linked_memories": i.linked_memories,
                "is_superseded": i.is_superseded,
                "created_at": i.created_at.isoformat() if i.created_at else None,
            }
            for i in insights
        ]
    }


@router.delete("/insights/{insight_id}")
async def remove_insight(insight_id: str, user_id: str = "default"):
    """Remove an insight."""
    from src.storage.memory import get_memory_store

    store = get_memory_store(user_id)
    removed = store.remove_insight(insight_id)

    return {"status": "removed" if removed else "not_found", "id": insight_id}


@router.post("/insights/search")
async def search_insights(request: InsightSearchRequest):
    """Search insights using keyword or semantic search."""
    from src.storage.memory import get_memory_store

    store = get_memory_store(request.user_id)

    if request.method == "fts":
        results = store.search_insights(request.query, limit=request.limit)
    elif request.method == "semantic":
        results = store.search_insights_semantic(request.query, limit=request.limit)
    else:
        results = store.search_insights(request.query, limit=request.limit)
        if not results:
            results = store.search_insights_semantic(request.query, limit=request.limit)

    return {
        "query": request.query,
        "method": request.method,
        "results": [
            {
                "id": i.id,
                "summary": i.summary,
                "domain": i.domain,
                "confidence": i.confidence,
                "linked_memories": i.linked_memories,
            }
            for i in results
        ],
    }


@router.post("/connections")
async def add_connection(request: ConnectionRequest):
    """Create a connection between two memories."""
    from src.storage.memory import get_memory_store

    store = get_memory_store(request.user_id)
    store.add_connection(
        request.memory_id,
        request.target_id,
        relationship=request.relationship,
        strength=request.strength,
    )

    return {
        "status": "connected",
        "memory_id": request.memory_id,
        "target_id": request.target_id,
        "relationship": request.relationship,
        "strength": request.strength,
    }


@router.get("/stats")
async def memory_stats(user_id: str = "default"):
    """Get memory system statistics."""
    from src.storage.memory import get_memory_store

    store = get_memory_store(user_id)
    return store.get_stats()


@router.post("/search-all")
async def search_all(request: SearchAllRequest):
    """Unified search across memories, messages, and insights."""
    from src.storage.memory import get_memory_store

    store = get_memory_store(request.user_id)
    results = store.search_all(
        request.query,
        memories_limit=request.memories_limit,
        messages_limit=request.messages_limit,
        insights_limit=request.insights_limit,
        user_id=request.user_id,
    )

    return {
        "query": request.query,
        "memories": [
            {
                "id": m.id,
                "trigger": m.trigger,
                "action": m.action,
                "confidence": m.confidence,
                "domain": m.domain,
                "memory_type": m.memory_type,
            }
            for m in results["memories"]
        ],
        "insights": [
            {
                "id": i.id,
                "summary": i.summary,
                "domain": i.domain,
                "confidence": i.confidence,
            }
            for i in results["insights"]
        ],
        "messages": results["messages"],
    }
