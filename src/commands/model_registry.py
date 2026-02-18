from __future__ import annotations

from threading import RLock

from src.config.settings import get_settings

_lock = RLock()
_user_models: dict[str, tuple[str, str]] = {}


def get_current_model(user_id: str) -> tuple[str, str] | None:
    """Get a user-scoped model override."""
    with _lock:
        return _user_models.get(user_id)


def set_current_model(user_id: str, provider: str, model: str) -> None:
    """Set a user-scoped model override."""
    with _lock:
        _user_models[user_id] = (provider, model)


def clear_current_model(user_id: str) -> None:
    """Clear a user-scoped model override."""
    with _lock:
        _user_models.pop(user_id, None)


def get_effective_model(user_id: str) -> tuple[str, str]:
    """Get effective `(provider, model)` for a user, including defaults."""
    override = get_current_model(user_id)
    if override:
        return override
    return get_settings().llm.get_default_provider_model()
