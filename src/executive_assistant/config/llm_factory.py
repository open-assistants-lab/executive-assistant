"""LLM provider factory for creating chat models."""

import logging
import re
from functools import lru_cache
from typing import Literal

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

from executive_assistant.config.settings import settings

logger = logging.getLogger(__name__)


def get_llm_config() -> dict:
    """Get LLM configuration from YAML defaults.

    Returns:
        Flattened LLM configuration dictionary.
    """
    from executive_assistant.config.loader import get_yaml_defaults
    return get_yaml_defaults()

# Model aliases (no default models - users must configure)
MODEL_ALIASES = ["default", "fast"]

# Provider-specific model name patterns for validation
MODEL_PATTERNS = {
    "anthropic": r"^claude-",  # Must start with "claude-"
    "openai": r"^(gpt|o1)-",   # Must start with "gpt-" or "o1-"
    "zhipu": r"^glm-",         # Must start with "glm-"
    "ollama": r".+",            # Any pattern allowed for Ollama
    "gemini": r"^gemini(?:-[\d\.]+)?(?:-[a-z]+(?:-[a-z0-9]+)?)?$",
    "qwen": r"^(?:qwen|qwq)(?:-[a-zA-Z0-9\.\+]+)*$",
    "kimi": r"^kimi-k2(?:\.[a-z0-9]+)?(?:-[a-z0-9]+)?$",
    "minimax": r"^(?:MiniMax-)?M2(?:\.[a-z0-9]+)?(?:-[A-Za-z]+)?$",
}

# Ollama Cloud models that do NOT support JSON Schema for tool calling
# These models will fail when bind_tools() is called with JSON Schema format
OLLAMA_INCOMPATIBLE_MODELS = {
    "kimi-k2.5:cloud": "JSON Schema not supported - use native Kimi provider instead",
    "deepseek-v3.2:cloud": "XML tool calling only - not compatible with LangChain bind_tools()",
}

# Ollama Cloud models with verified JSON Schema tool calling support
OLLAMA_COMPATIBLE_MODELS = {
    "deepseek-v3.1:671b-cloud": "Recommended - full JSON Schema support",
    "glm-4.7:cloud": "Good - JSON Schema supported",
    "minimax-m2.1:cloud": "Good - JSON Schema supported",
    "gpt-oss:20b-cloud": "Good - JSON Schema supported",
    "qwen3-next:80b-cloud": "Good - JSON Schema supported",
}


def validate_llm_config() -> None:
    """Validate LLM configuration on startup.

    Checks:
    - Provider is valid
    - Default and fast models are configured
    - Model names match provider patterns
    - API keys are set for cloud providers

    Raises:
        ValueError: If configuration is invalid, with descriptive message.
    """
    errors = []

    provider = settings.DEFAULT_LLM_PROVIDER

    # Check provider-specific model overrides
    provider_upper = provider.upper()
    default_model = getattr(settings, f"{provider_upper}_DEFAULT_MODEL", None)
    fast_model = getattr(settings, f"{provider_upper}_FAST_MODEL", None)

    # Check global overrides as fallback
    if not default_model:
        default_model = settings.DEFAULT_LLM_MODEL
    if not fast_model:
        fast_model = settings.FAST_LLM_MODEL

    # Validate models are set
    if not default_model:
        errors.append(
            f"No default model configured for provider '{provider}'. "
            f"Set {provider_upper}_DEFAULT_MODEL or DEFAULT_LLM_MODEL."
        )
    if not fast_model:
        errors.append(
            f"No fast model configured for provider '{provider}'. "
            f"Set {provider_upper}_FAST_MODEL or FAST_LLM_MODEL."
        )

    # Validate model name patterns
    pattern = MODEL_PATTERNS.get(provider)
    if pattern:
        if default_model and not re.match(pattern, default_model):
            errors.append(
                f"Invalid default model '{default_model}' for {provider}. Please check model name."
            )
        if fast_model and not re.match(pattern, fast_model):
            errors.append(
                f"Invalid fast model '{fast_model}' for {provider}. Please check model name."
            )

    # Validate Ollama-specific config
    if provider == "ollama":
        if settings.OLLAMA_MODE == "cloud" and not settings.OLLAMA_CLOUD_API_KEY:
            errors.append(
                "OLLAMA_MODE=cloud requires OLLAMA_CLOUD_API_KEY to be set. "
                "Use OLLAMA_MODE=local for local Ollama (no API key required)."
            )

        # Warn about incompatible Ollama Cloud models (only check if in cloud mode)
        if settings.OLLAMA_MODE == "cloud":
            for model_variant_name, model_name in [("default", default_model), ("fast", fast_model)]:
                if model_name in OLLAMA_INCOMPATIBLE_MODELS:
                    logger.warning(
                        "Ollama Cloud model '%s' (%s variant) doesn't support JSON Schema tool calling: %s. "
                        "Use a different model or the native provider for full tool support.",
                        model_name, model_variant_name, OLLAMA_INCOMPATIBLE_MODELS[model_name]
                    )

    # Check API key for cloud providers
    if provider in ["anthropic", "openai", "zhipu"]:
        api_key_var = f"{provider_upper}_API_KEY"
        if provider == "zhipu":
            api_key_var = "ZHIPUAI_API_KEY"
        if not getattr(settings, api_key_var, None):
            errors.append(
                f"{api_key_var} not set for {provider} provider."
            )

    # Check API keys for new providers
    if provider == "gemini":
        if not settings.GOOGLE_API_KEY and not settings.GEMINI_API_KEY:
            errors.append("GOOGLE_API_KEY or GEMINI_API_KEY not set for gemini provider.")
    if provider == "qwen":
        if not settings.DASHSCOPE_API_KEY:
            errors.append("DASHSCOPE_API_KEY not set for qwen provider.")
    if provider == "kimi":
        if not settings.MOONSHOT_API_KEY:
            errors.append("MOONSHOT_API_KEY not set for kimi provider.")
    if provider == "minimax":
        if not settings.MINIMAX_API_KEY:
            errors.append("MINIMAX_API_KEY not set for minimax provider.")

    if errors:
        error_msg = "LLM configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        logger.error(error_msg)
        raise ValueError(error_msg)

    logger.info(f"LLM config validated: {provider} (default={default_model}, fast={fast_model})")


def _get_model_config(provider: str, model: str = "default") -> str:
    """Get model name from config or env override.

    Priority (highest to lowest):
    1. Provider-specific env var (e.g., ANTHROPIC_DEFAULT_MODEL)
    2. Global env var (DEFAULT_LLM_MODEL or FAST_LLM_MODEL)
    3. Error: No model configured

    Args:
        provider: LLM provider (anthropic, openai, zhipu, ollama, gemini, qwen, kimi, minimax)
        model: Model variant (default, fast) or specific model name

    Returns:
        Model name string

    Raises:
        ValueError: If no model is configured
    """
    provider_upper = provider.upper()

    # If not an alias, return as-is (specific model name)
    if model not in MODEL_ALIASES:
        return model

    # Check provider-specific env var first (highest priority)
    env_var = f"{provider_upper}_{model.upper()}_MODEL"
    env_value = getattr(settings, env_var, None)
    if env_value:
        return env_value

    # Check global env vars
    global_var = f"{model.upper()}_LLM_MODEL"
    global_value = getattr(settings, global_var, None)
    if global_value:
        return global_value

    # No model configured - raise error
    raise ValueError(
        f"No model configured for {provider} '{model}'. "
        f"Set {env_var} or {global_var} in your .env file."
    )


def _get_ollama_config(model: str = "default") -> tuple[str, str, str | None]:
    """Get Ollama base_url, model, and API key based on mode.

    Args:
        model: Model variant (default, fast) or specific model name

    Returns:
        (base_url, model, api_key or None)

    Raises:
        ValueError: If cloud mode selected but no API key configured
    """
    # Get the model name for this variant
    model_name = _get_model_config("ollama", model)

    if settings.OLLAMA_MODE == "local":
        base_url = settings.OLLAMA_LOCAL_URL
        api_key = None  # Local doesn't need API key
    else:  # cloud
        api_key = settings.OLLAMA_CLOUD_API_KEY
        if not api_key:
            raise ValueError(
                "OLLAMA_CLOUD_API_KEY not set for Ollama Cloud mode. "
                "Set OLLAMA_CLOUD_API_KEY or use OLLAMA_MODE=local for local Ollama."
            )
        base_url = settings.OLLAMA_CLOUD_URL

    return base_url, model_name, api_key


def check_ollama_tool_compatibility(model_name: str) -> tuple[bool, str | None]:
    """Check if an Ollama Cloud model supports JSON Schema tool calling.

    Args:
        model_name: The Ollama model name to check

    Returns:
        (is_compatible, error_message or None)
    """
    # Check if model is in incompatible list
    if model_name in OLLAMA_INCOMPATIBLE_MODELS:
        return False, OLLAMA_INCOMPATIBLE_MODELS[model_name]

    # Check if model ends with :cloud (unverified model)
    if model_name.endswith(":cloud") and model_name not in OLLAMA_COMPATIBLE_MODELS:
        logger.warning(
            "Ollama Cloud model '%s' not in compatibility list. "
            "Tool calling may fail if model doesn't support JSON Schema. "
            "Test with a simple tool call first.",
            model_name
        )

    return True, None


class LLMFactory:
    """Factory for creating LLM instances."""

    @staticmethod
    def _create_anthropic(model: str = "default", **kwargs) -> ChatAnthropic:
        """Create Anthropic Claude model."""
        if not settings.ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY not set")
        model_name = _get_model_config("anthropic", model)
        return ChatAnthropic(
            model=model_name,
            api_key=settings.ANTHROPIC_API_KEY,
            temperature=kwargs.get("temperature", 0.7),
            max_tokens=kwargs.get("max_tokens", 8192),
            **kwargs,
        )

    @staticmethod
    def _create_openai(model: str = "default", **kwargs) -> ChatOpenAI:
        """Create OpenAI model."""
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY not set")
        model_name = _get_model_config("openai", model)
        # gpt-5.x requires max_completion_tokens instead of max_tokens
        if "gpt-5" in model_name:
            kwargs.setdefault("max_completion_tokens", kwargs.get("max_tokens", 4096))
        else:
            kwargs.setdefault("max_tokens", kwargs.get("max_tokens", 4096))
        return ChatOpenAI(
            model=model_name,
            api_key=settings.OPENAI_API_KEY,
            temperature=kwargs.get("temperature", 0.7),
            **kwargs,
        )

    @staticmethod
    def _create_zhipu(model: str = "default", **kwargs) -> BaseChatModel:
        """Create Zhipu AI model using native SDK with LangChain wrapper."""
        if not settings.ZHIPUAI_API_KEY:
            raise ValueError("ZHIPUAI_API_KEY not set")

        # Use langchain_openai's compatible base with Zhipu endpoint
        from langchain_openai import ChatOpenAI

        model_name = _get_model_config("zhipu", model)

        # Create ChatOpenAI with Zhipu's endpoint
        return ChatOpenAI(
            model=model_name,
            api_key=settings.ZHIPUAI_API_KEY,
            base_url="https://open.bigmodel.cn/api/paas/v4/",
            temperature=kwargs.get("temperature", 0.7),
            max_tokens=kwargs.get("max_tokens", 4096),
            **kwargs,
        )

    @staticmethod
    def _create_ollama(model: str = "default", **kwargs) -> BaseChatModel:
        """Create Ollama model (cloud or local).

        For cloud mode, requires OLLAMA_CLOUD_API_KEY to be set.
        For local mode, no API key needed.

        Note: Some Ollama Cloud models don't support JSON Schema for tool calling.
        Incompatible models will be logged with a warning.
        """
        base_url, model_name, api_key = _get_ollama_config(model)

        # Check tool compatibility for cloud models
        if api_key:  # Cloud mode
            is_compatible, error_msg = check_ollama_tool_compatibility(model_name)
            if not is_compatible:
                logger.warning(
                    "Ollama Cloud model '%s' doesn't support JSON Schema tool calling: %s. "
                    "Tool calling features may not work correctly.",
                    model_name, error_msg
                )

        # Build ChatOllama kwargs
        ollama_kwargs = {
            "model": model_name,
            "base_url": base_url,
            "temperature": kwargs.get("temperature", 0.7),
            "num_ctx": kwargs.get("max_tokens", 4096),
        }

        # Only add API key for cloud mode
        if api_key:
            client_kwargs = kwargs.pop("client_kwargs", {})
            client_kwargs.setdefault("headers", {})
            client_kwargs["headers"]["Authorization"] = f"Bearer {api_key}"
            ollama_kwargs["client_kwargs"] = client_kwargs

        ollama_kwargs.update(kwargs)
        llm = ChatOllama(**ollama_kwargs)
        return llm

    @staticmethod
    def _create_gemini(model: str = "default", **kwargs) -> BaseChatModel:
        """Create Google Gemini model."""
        from langchain_google_genai import ChatGoogleGenerativeAI

        if not settings.GOOGLE_API_KEY and not settings.GEMINI_API_KEY:
            raise ValueError("GOOGLE_API_KEY or GEMINI_API_KEY not set")

        model_name = _get_model_config("gemini", model)
        api_key = settings.GOOGLE_API_KEY or settings.GEMINI_API_KEY

        # Vertex AI backend detection
        config = get_llm_config().get("gemini", {})
        vertexai = config.get("vertexai", False)

        params = {
            "model": model_name,
            "api_key": api_key,
            "temperature": kwargs.get("temperature", 1.0),  # Gemini 3.0+ defaults to 1.0
            "max_tokens": kwargs.get("max_tokens", None),
            "timeout": kwargs.get("timeout", None),
            "max_retries": kwargs.get("max_retries", 2),
        }

        if vertexai or settings.GOOGLE_CLOUD_PROJECT:
            params.update({
                "vertexai": True,
                "project": settings.GOOGLE_CLOUD_PROJECT or config.get("project"),
                "location": config.get("location", settings.GOOGLE_CLOUD_LOCATION or "us-central1"),
            })

        return ChatGoogleGenerativeAI(**params)

    @staticmethod
    def _create_qwen(model: str = "default", **kwargs) -> BaseChatModel:
        """Create Qwen (Alibaba) model."""
        from langchain_qwq import ChatQwen

        if not settings.DASHSCOPE_API_KEY:
            raise ValueError("DASHSCOPE_API_KEY not set")

        model_name = _get_model_config("qwen", model)

        return ChatQwen(
            model=model_name,
            api_key=settings.DASHSCOPE_API_KEY,
            max_tokens=kwargs.get("max_tokens", 3_000),
            temperature=kwargs.get("temperature", 0.7),
            timeout=kwargs.get("timeout", None),
            max_retries=kwargs.get("max_retries", 2),
        )

    @staticmethod
    def _create_kimi(model: str = "default", **kwargs) -> BaseChatModel:
        """Create Kimi K2 (Moonshot AI) model using OpenAI-compatible API."""
        if not settings.MOONSHOT_API_KEY:
            raise ValueError("MOONSHOT_API_KEY not set")

        model_name = _get_model_config("kimi", model)

        return ChatOpenAI(
            model=model_name,
            api_key=settings.MOONSHOT_API_KEY,
            base_url=settings.MOONSHOT_API_BASE,
            temperature=kwargs.get("temperature", 0.7),
            max_tokens=kwargs.get("max_tokens", 8192),
            timeout=kwargs.get("timeout", None),
            max_retries=kwargs.get("max_retries", 2),
        )

    @staticmethod
    def _create_minimax(model: str = "default", **kwargs) -> BaseChatModel:
        """Create MiniMax M2 model using OpenAI or Anthropic-compatible API."""
        config = get_llm_config().get("minimax", {})
        api_type = config.get("api_type", settings.MINIMAX_API_TYPE or "openai")

        if not settings.MINIMAX_API_KEY:
            raise ValueError("MINIMAX_API_KEY not set")

        model_name = _get_model_config("minimax", model)
        api_base = config.get(
            "api_base",
            settings.MINIMAX_API_BASE or (
                "https://api.minimax.io/v1" if api_type == "openai"
                else "https://api.minimax.io/anthropic"
            )
        )

        if api_type == "anthropic":
            return ChatAnthropic(
                model=model_name,
                api_key=settings.MINIMAX_API_KEY,
                base_url=api_base,
                temperature=kwargs.get("temperature", 0.7),
                max_tokens=kwargs.get("max_tokens", 204800),  # Ultra-long context!
                timeout=kwargs.get("timeout", None),
                max_retries=kwargs.get("max_retries", 2),
            )
        else:  # OpenAI-compatible (default)
            return ChatOpenAI(
                model=model_name,
                api_key=settings.MINIMAX_API_KEY,
                base_url=api_base,
                temperature=kwargs.get("temperature", 0.7),
                max_tokens=kwargs.get("max_tokens", 204800),
                timeout=kwargs.get("timeout", None),
                max_retries=kwargs.get("max_retries", 2),
            )

    @classmethod
    def create(
        cls,
        provider: Literal[
            "anthropic", "openai", "zhipu", "ollama", "gemini", "qwen", "kimi", "minimax"
        ] | None = None,
        model: str = "default",
        **kwargs,
    ) -> BaseChatModel:
        """
        Create a chat model instance.

        Args:
            provider: LLM provider (anthropic, openai, zhipu, ollama, gemini, qwen, kimi, minimax).
                      Defaults to DEFAULT_LLM_PROVIDER.
            model: Model variant (default, fast) or specific model name. Defaults to "default".
            **kwargs: Additional model parameters.

        Returns:
            Configured chat model instance.
        """
        if provider is None:
            provider = settings.DEFAULT_LLM_PROVIDER

        if provider == "anthropic":
            return cls._create_anthropic(model, **kwargs)
        elif provider == "openai":
            return cls._create_openai(model, **kwargs)
        elif provider == "zhipu":
            return cls._create_zhipu(model, **kwargs)
        elif provider == "ollama":
            return cls._create_ollama(model, **kwargs)
        elif provider == "gemini":
            return cls._create_gemini(model, **kwargs)
        elif provider == "qwen":
            return cls._create_qwen(model, **kwargs)
        elif provider == "kimi":
            return cls._create_kimi(model, **kwargs)
        elif provider == "minimax":
            return cls._create_minimax(model, **kwargs)
        else:
            raise ValueError(f"Unknown provider: {provider}")


@lru_cache
def get_model(provider: str | None = None) -> BaseChatModel:
    """Get cached model instance."""
    return LLMFactory.create(provider)


def create_model(provider: str | None = None, **kwargs) -> BaseChatModel:
    """
    Create a new model instance (uncached).

    Args:
        provider: LLM provider. Defaults to settings.DEFAULT_LLM_PROVIDER.
        **kwargs: Additional model parameters.

    Returns:
        New chat model instance.
    """
    return LLMFactory.create(provider, **kwargs)


def get_model_for_extraction() -> BaseChatModel:
    """Get model for memory/extraction operations.

    Uses MEM_EXTRACT_PROVIDER if set, otherwise falls back to DEFAULT_LLM_PROVIDER.
    Uses MEM_EXTRACT_MODEL (can be "default", "fast", or specific model name).
    """
    provider = settings.MEM_EXTRACT_PROVIDER or settings.DEFAULT_LLM_PROVIDER
    model = settings.MEM_EXTRACT_MODEL
    return LLMFactory.create(provider, model=model, temperature=settings.MEM_EXTRACT_TEMPERATURE)


def get_model_for_ocr() -> BaseChatModel:
    """Get model for OCR structured output.

    Uses OCR_STRUCTURED_PROVIDER if set, otherwise falls back to DEFAULT_LLM_PROVIDER.
    Uses OCR_STRUCTURED_MODEL (can be "default", "fast", or specific model name).
    """
    provider = settings.OCR_STRUCTURED_PROVIDER or settings.DEFAULT_LLM_PROVIDER
    model = settings.OCR_STRUCTURED_MODEL
    return LLMFactory.create(provider, model=model)
