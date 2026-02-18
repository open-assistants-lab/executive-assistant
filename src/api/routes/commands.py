"""Administrative command endpoints for the Executive Assistant.

These endpoints provide HTTP API access to administrative commands
that mirror the Telegram bot slash commands.
"""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.commands import (
    get_current_model,
    get_effective_model,
    get_help_text,
    handle_clear_command,
    handle_model_command,
    set_current_model,
)
from src.utils import create_thread_id
from src.utils.checkpoint import delete_thread_checkpoint

router = APIRouter(prefix="/commands", tags=["commands"])


# ============================================================================
# Models
# ============================================================================

class HelpResponse(BaseModel):
    """Response model for /help command."""
    help_text: str = Field(..., description="Help text showing available commands")


class ModelInfoResponse(BaseModel):
    """Response model for /model GET command."""
    provider: str | None = Field(None, description="LLM provider (e.g., 'openai')")
    model: str | None = Field(None, description="Model name (e.g., 'gpt-4o')")
    full_model: str | None = Field(None, description="Full model string (provider/model)")
    source: str = Field(
        default="default",
        description="`override` when user-specific, otherwise `default`",
    )


class ModelSetRequest(BaseModel):
    """Request model for /model POST command."""
    model: str = Field(..., description="Model string (e.g., 'openai/gpt-4o')")
    user_id: str = Field(default="default", description="User ID")


class ModelSetResponse(BaseModel):
    """Response model for /model POST command."""
    message: str = Field(..., description="Confirmation message")


class ClearRequest(BaseModel):
    """Request model for /clear command."""
    user_id: str = Field(default="default", description="User ID")
    thread_id: str | None = Field(None, description="Thread ID to clear (optional)")


class ClearResponse(BaseModel):
    """Response model for /clear command."""
    message: str = Field(..., description="Confirmation message with new thread ID")
    new_thread_id: str = Field(..., description="New thread ID for the next conversation session")
    cleared_thread_id: str | None = Field(
        None,
        description="Previously active thread ID that was cleared",
    )
    checkpoint_deleted: bool = Field(
        False,
        description="Whether checkpoint deletion was attempted successfully",
    )


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/help", response_model=HelpResponse)
async def get_help() -> HelpResponse:
    """Get help text showing available commands.

    Returns all available commands and their usage.
    """
    return HelpResponse(help_text=get_help_text())


@router.get("/model", response_model=ModelInfoResponse)
async def get_model(
    user_id: str = "default",
) -> ModelInfoResponse:
    """Get the current model for a user.

    Args:
        user_id: User ID (default: "default")

    Returns:
        Current model information
    """
    current = get_current_model(user_id)

    if current:
        provider, model = current
        return ModelInfoResponse(
            provider=provider,
            model=model,
            full_model=f"{provider}/{model}",
            source="override",
        )
    else:
        provider, model = get_effective_model(user_id)
        return ModelInfoResponse(
            provider=provider,
            model=model,
            full_model=f"{provider}/{model}",
            source="default",
        )


@router.post("/model", response_model=ModelSetResponse)
async def set_model(request: ModelSetRequest) -> ModelSetResponse:
    """Change the model for a user.

    Args:
        request: Model change request

    Returns:
        Confirmation message
    """
    result = handle_model_command(
        model_string=request.model,
        user_id=request.user_id,
        get_current_model=get_current_model,
        set_model=lambda uid, p, m: set_current_model(uid, p, m)
    )

    return ModelSetResponse(message=result)


@router.post("/clear", response_model=ClearResponse)
async def clear_conversation(request: ClearRequest) -> ClearResponse:
    """Clear conversation history and start a new thread.

    Args:
        request: Clear request with user_id and optional thread_id

    Returns:
        Confirmation message with new thread ID
    """
    from src.config.settings import get_settings

    settings = get_settings()
    new_thread_id = create_thread_id(user_id=request.user_id, channel="api", reason="clear")
    old_thread_id = request.thread_id

    checkpoint_deleted = False
    if old_thread_id:
        checkpoint_deleted = await delete_thread_checkpoint(settings.database_url, old_thread_id)

    result = handle_clear_command(
        user_id=request.user_id,
        thread_id=new_thread_id,
    )

    return ClearResponse(
        message=result,
        new_thread_id=new_thread_id,
        cleared_thread_id=old_thread_id,
        checkpoint_deleted=checkpoint_deleted,
    )
