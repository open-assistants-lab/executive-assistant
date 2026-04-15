"""Provider factory — creates LLMProvider instances from config.

Uses the models.dev-powered registry to resolve provider types and base URLs
dynamically. Falls back to hardcoded defaults for well-known providers.
"""

from __future__ import annotations

import os
from typing import Any

from src.sdk.providers.anthropic import AnthropicProvider
from src.sdk.providers.base import LLMProvider
from src.sdk.providers.gemini import GeminiProvider
from src.sdk.providers.ollama import OllamaCloud, OllamaLocal
from src.sdk.providers.openai import OpenAIProvider

_PROVIDER_CLASSES: dict[str, type[LLMProvider]] = {
    "ollama": OllamaLocal,
    "ollama-cloud": OllamaCloud,
    "openai": OpenAIProvider,
    "openai-compatible": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "gemini": GeminiProvider,
}

_ENV_KEY_MAP: dict[str, str] = {
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


def _resolve_provider_type(provider_id: str) -> tuple[str, str]:
    lower = provider_id.lower().strip()

    if lower == "ollama":
        return "ollama", ""
    if lower == "ollama-cloud":
        return "ollama-cloud", ""
    if lower == "anthropic":
        return "anthropic", ""
    if lower == "gemini":
        return "gemini", ""
    if lower in ("openai",):
        return "openai", ""

    from src.sdk.registry import get_provider

    registry_provider = get_provider(provider_id)
    if registry_provider:
        return registry_provider["type"], registry_provider.get("base_url", "") or ""

    if lower in _PROVIDER_CLASSES:
        return lower, ""
    return "openai-compatible", ""


def create_provider(
    provider_type: str,
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    **kwargs: Any,
) -> LLMProvider:
    resolved_type, registry_url = _resolve_provider_type(provider_type)

    if resolved_type == "ollama":
        resolved_url = base_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        return OllamaLocal(base_url=resolved_url, model=model or "minimax-m2.5")

    if resolved_type == "ollama-cloud":
        resolved_url = base_url or os.environ.get("OLLAMA_BASE_URL", "https://ollama.com")
        resolved_key = api_key or os.environ.get("OLLAMA_API_KEY", "")
        return OllamaCloud(
            base_url=resolved_url, model=model or "minimax-m2.5", api_key=resolved_key
        )

    if resolved_type == "anthropic":
        resolved_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        resolved_url = base_url or "https://api.anthropic.com"
        return AnthropicProvider(
            api_key=resolved_key, model=model or "claude-sonnet-4-20250514", base_url=resolved_url
        )

    if resolved_type == "gemini":
        resolved_key = api_key or os.environ.get("GOOGLE_API_KEY", "")
        return GeminiProvider(api_key=resolved_key, model=model or "gemini-2.5-flash")

    if resolved_type in ("openai", "openai-compatible"):
        env_key = _ENV_KEY_MAP.get(provider_type, "")
        resolved_key = api_key or (os.environ.get(env_key, "") if env_key else "")
        default_url = registry_url or _default_base_url(provider_type)
        resolved_url = base_url or default_url
        return OpenAIProvider(
            api_key=resolved_key or "unused", base_url=resolved_url, model=model or "gpt-4o"
        )

    raise ValueError(f"Unknown provider type: {provider_type}")


def _default_base_url(provider_id: str) -> str:
    from src.sdk.registry import get_provider

    p = get_provider(provider_id)
    if p and p.get("base_url"):
        return p["base_url"]

    _fallback: dict[str, str] = {
        "groq": "https://api.groq.com/openai/v1",
        "deepseek": "https://api.deepseek.com/v1",
        "together": "https://api.together.xyz/v1",
        "openrouter": "https://openrouter.ai/api/v1",
        "lmstudio": "http://localhost:1234/v1",
        "llamacpp": "http://localhost:8080/v1",
    }
    return _fallback.get(provider_id, "https://api.openai.com/v1")


def create_model_from_config(config_model: str | None = None) -> LLMProvider:
    from src.config import get_settings

    settings = get_settings()
    model_str = config_model or settings.agent.model
    provider_type, model_name = _parse_model_string(model_str)

    if provider_type == "ollama":
        base_url = os.environ.get("OLLAMA_BASE_URL", "")
        ollama_key = os.environ.get("OLLAMA_API_KEY", "")
        if base_url and ("ollama.com" in base_url or ollama_key):
            return create_provider(
                "ollama-cloud", model=model_name, api_key=ollama_key, base_url=base_url
            )

    return create_provider(provider_type, model=model_name)


def _parse_model_string(model_str: str) -> tuple[str, str]:
    if ":" in model_str:
        provider, model_name = model_str.split(":", 1)
        return provider.strip(), model_name.strip()
    return "ollama", model_str.strip()
