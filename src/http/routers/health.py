from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    """Health check."""
    return {"status": "healthy"}


@router.get("/health/ready")
async def ready():
    """Readiness check."""
    return {"status": "ready"}
