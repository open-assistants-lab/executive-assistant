from typing import Any

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, Any]:
    """Health check."""
    return {"status": "healthy"}


@router.get("/health/ready")
async def ready() -> dict[str, Any]:
    """Readiness check."""
    return {"status": "ready"}


@router.get("/models")
async def list_models_endpoint() -> dict[str, Any]:
    """List available providers and models from models.dev cache."""
    from src.sdk.registry import list_models

    models = list_models()
    if not models:
        return {"providers": [], "total": 0}

    # Group by provider, deduplicating by model ID
    from src.sdk.registry import get_provider
    providers: dict[str, dict[str, Any]] = {}
    seen_models: set[str] = set()
    for m in models:
        full_id = f"{m.provider_id}:{m.id}"
        if full_id in seen_models:
            continue
        seen_models.add(full_id)
        pid = m.provider_id or "unknown"
        if pid not in providers:
            p_info = get_provider(pid)
            pname = (p_info.get("name") if p_info else pid)
            providers[pid] = {
                "id": pid,
                "name": pname,
                "models": [],
            }
        entry = {"id": m.id, "name": m.name}
        if entry not in providers[pid]["models"]:
            providers[pid]["models"].append(entry)

    return {"providers": list(providers.values()), "total": len(models)}
