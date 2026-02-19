"""LLM providers for Executive Assistant."""

import os
from typing import Any, Optional

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

from src.config import get_settings


def create_ollama_cloud_model(
    model: str = "minimax-m2.5",
    api_key: Optional[str] = None,
    base_url: str = "https://ollama.com",
    **kwargs: Any,
) -> BaseChatModel:
    """Create Ollama Cloud chat model.

    Args:
        model: Model name (e.g., "minimax-m2.5")
        api_key: Ollama API key
        base_url: Ollama Cloud API base URL (default: https://ollama.com)

    Returns:
        Initialized chat model
    """
    api_key = api_key or os.environ.get("OLLAMA_API_KEY")
    base_url = base_url or os.environ.get("OLLAMA_BASE_URL", "https://ollama.com")

    return init_chat_model(
        model=model, model_provider="ollama", api_key=api_key, base_url=base_url, **kwargs
    )


def create_openai_model(
    model: str = "gpt-4o", api_key: Optional[str] = None, **kwargs: Any
) -> BaseChatModel:
    """Create OpenAI chat model.

    Args:
        model: Model name
        api_key: OpenAI API key

    Returns:
        Initialized chat model
    """
    api_key = api_key or os.environ.get("OPENAI_API_KEY")

    return init_chat_model(model=model, model_provider="openai", api_key=api_key, **kwargs)


def create_anthropic_model(
    model: str = "claude-sonnet-4-20250514", api_key: Optional[str] = None, **kwargs: Any
) -> BaseChatModel:
    """Create Anthropic chat model.

    Args:
        model: Model name
        api_key: Anthropic API key

    Returns:
        Initialized chat model
    """
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")

    return init_chat_model(model=model, model_provider="anthropic", api_key=api_key, **kwargs)


def create_model_from_config(config_model: Optional[str] = None) -> BaseChatModel:
    """Create a model based on configuration.

    Args:
        config_model: Model string (e.g., "ollama:minimax-m2.5", "openai:gpt-4o")

    Returns:
        Initialized chat model
    """
    settings = get_settings()
    model_str = config_model or settings.agent.model

    # Parse model string (provider:model)
    if ":" in model_str:
        provider, model_name = model_str.split(":", 1)
    else:
        provider = "ollama"  # Default to ollama
        model_name = model_str

    # Create model based on provider
    if provider == "ollama":
        return create_ollama_cloud_model(model=model_name)
    elif provider == "openai":
        return create_openai_model(model=model_name)
    elif provider == "anthropic":
        return create_anthropic_model(model=model_name)
    else:
        raise ValueError(f"Unknown provider: {provider}")
