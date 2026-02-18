from __future__ import annotations

from src.commands.model_registry import (
    clear_current_model,
    get_current_model,
    get_effective_model,
    set_current_model,
)


def test_model_registry_set_get_clear_roundtrip() -> None:
    user_id = "registry-user-1"
    clear_current_model(user_id)

    set_current_model(user_id, "openai", "gpt-5-nano")
    assert get_current_model(user_id) == ("openai", "gpt-5-nano")

    clear_current_model(user_id)
    assert get_current_model(user_id) is None


def test_get_effective_model_falls_back_to_defaults() -> None:
    user_id = "registry-user-2"
    clear_current_model(user_id)

    provider, model = get_effective_model(user_id)
    assert provider
    assert model
