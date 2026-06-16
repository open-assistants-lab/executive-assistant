"""User prompt API endpoints."""

from fastapi import APIRouter
from pydantic import BaseModel

from src.sdk.user_prompt import load_user_prompt, save_user_prompt

router = APIRouter(prefix="/user", tags=["user"])


class UserPromptResponse(BaseModel):
    prompt: str


class UserPromptRequest(BaseModel):
    prompt: str


@router.get("/prompt", response_model=UserPromptResponse)
async def get_user_prompt(user_id: str = "default_user") -> UserPromptResponse:
    """Get the user's custom prompt."""
    prompt = load_user_prompt(user_id)
    return UserPromptResponse(prompt=prompt)


@router.put("/prompt", response_model=UserPromptResponse)
async def set_user_prompt(req: UserPromptRequest, user_id: str = "default_user") -> UserPromptResponse:
    """Set the user's custom prompt."""
    save_user_prompt(user_id, req.prompt)
    return UserPromptResponse(prompt=req.prompt)
