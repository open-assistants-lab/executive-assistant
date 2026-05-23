"""Settings API — per-user overrides for API keys and default model."""

from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from src.app_logging import get_logger


class UpdateSettingsRequest(BaseModel):
    """Request body for PATCH /settings."""
    default_model: str | None = None


class SetApiKeyRequest(BaseModel):
    """Request body for POST /settings/api-keys."""
    provider: str
    api_key: str


logger = get_logger()
router = APIRouter(prefix="/settings", tags=["settings"])


def _settings_path(user_id: str) -> Path:
    from src.config.settings import get_settings

    root = get_settings().storage.data_dir or "data"
    return Path(f"{root}/users/{user_id}/settings.json")


def _read_settings(user_id: str) -> dict:
    path = _settings_path(user_id)
    if path.exists():
        return json.loads(path.read_text())
    return {"provider_keys": {}, "default_model": None}


def _write_settings(user_id: str, data: dict) -> None:
    path = _settings_path(user_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


@router.get("")
async def get_settings(user_id: str = Query("default_user")):
    """Read current settings (default model, which providers have keys)."""
    data = _read_settings(user_id)
    from src.sdk.registry import list_providers

    providers_meta = list_providers()
    provider_status = {}
    for p in providers_meta:
        pid = p.get("id", "")
        has_key = pid in data.get("provider_keys", {})
        has_env = _env_key_for_provider(pid) is not None
        provider_status[pid] = {
            "name": p.get("name", pid),
            "has_key": has_key or has_env,
            "key_configured_via_env": has_env,
        }
    return {
        "default_model": data.get("default_model"),
        "provider_status": provider_status,
    }


def _env_key_for_provider(provider_id: str) -> str | None:
    mapping = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "gemini": "GOOGLE_API_KEY",
        "ollama": "OLLAMA_API_KEY",
        "ollama-cloud": "OLLAMA_API_KEY",
        "groq": "GROQ_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "together": "TOGETHER_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
    }
    env_var = mapping.get(provider_id)
    if env_var:
        return os.environ.get(env_var)
    return None


@router.patch("")
async def update_settings(
    body: UpdateSettingsRequest,
    user_id: str = Query("default_user"),
):
    """Update settings (default_model, etc.)."""
    data = _read_settings(user_id)
    if body.default_model is not None:
        data["default_model"] = body.default_model
    _write_settings(user_id, data)
    return {"status": "updated"}


@router.get("/api-keys")
async def list_api_keys(user_id: str = Query("default_user")):
    """List which providers have stored API keys (without revealing keys)."""
    data = _read_settings(user_id)
    keys = data.get("provider_keys", {})
    return {pid: bool(val) for pid, val in keys.items()}


@router.post("/api-keys")
async def set_api_key(
    body: SetApiKeyRequest,
    user_id: str = Query("default_user"),
):
    """Store an API key for a provider."""
    data = _read_settings(user_id)
    data.setdefault("provider_keys", {})[body.provider] = body.api_key
    _write_settings(user_id, data)
    return {"status": "stored", "provider": body.provider}


@router.delete("/api-keys/{provider}")
async def delete_api_key(
    provider: str,
    user_id: str = Query("default_user"),
):
    """Remove a stored API key for a provider."""
    data = _read_settings(user_id)
    data.get("provider_keys", {}).pop(provider, None)
    _write_settings(user_id, data)
    return {"status": "removed", "provider": provider}
