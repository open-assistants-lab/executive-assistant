from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.config.settings import get_settings, parse_model_string
from src.llm.errors import LLMConfigurationError, LLMProviderNotFoundError

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel

    from src.llm.base import BaseLLMProvider

_PROVIDER_REGISTRY: dict[str, type[BaseLLMProvider]] = {}

MODEL_PREFIX_TO_PROVIDER: dict[str, str] = {
    "gpt-": "openai",
    "o1-": "openai",
    "o3-": "openai",
    "claude-": "anthropic",
    "gemini-": "google",
    "llama-": "groq",
    "mixtral-": "groq",
    "gemma-": "groq",
    "mistral-": "mistral",
    "codestral-": "mistral",
    "deepseek-": "deepseek",
    "grok-": "xai",
    "glm-": "zhipuai",
    "qwen-": "qwen",
}


def detect_provider_from_model(model: str) -> str | None:
    """
    Attempt to detect the provider from a model name.

    Args:
        model: Model name (e.g., 'gpt-4o', 'claude-3-5-sonnet')

    Returns:
        Provider name or None if cannot be detected
    """
    model_lower = model.lower()
    for prefix, provider in MODEL_PREFIX_TO_PROVIDER.items():
        if model_lower.startswith(prefix):
            return provider
    return None


def register_provider(name: str, provider_class: type[BaseLLMProvider]) -> None:
    """
    Register a new LLM provider.

    Args:
        name: Provider name (e.g., 'openai', 'anthropic')
        provider_class: Provider class that inherits from BaseLLMProvider
    """
    _PROVIDER_REGISTRY[name.lower()] = provider_class


def list_providers() -> list[str]:
    """
    List all registered LLM providers.

    Returns:
        List of provider names
    """
    return list(_PROVIDER_REGISTRY.keys())


class LLMFactory:
    """
    Factory for creating LLM instances.

    This class implements the singleton pattern to ensure
    consistent provider registration across the application.
    """

    _instance: LLMFactory | None = None

    def __new__(cls) -> LLMFactory:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._load_providers()

    def _load_providers(self) -> None:
        """Load all built-in providers."""
        from src.llm.providers import (
            AnthropicProvider,
            AzureProvider,
            CohereProvider,
            DeepSeekProvider,
            FireworksProvider,
            GoogleProvider,
            GroqProvider,
            HuggingFaceProvider,
            MinimaxProvider,
            MistralProvider,
            OllamaProvider,
            OpenAIProvider,
            OpenRouterProvider,
            QwenProvider,
            TogetherProvider,
            XAIProvider,
            ZhipuAIProvider,
        )

        # Only register providers that are available (not None)
        if OpenAIProvider:
            register_provider("openai", OpenAIProvider)
        if AnthropicProvider:
            register_provider("anthropic", AnthropicProvider)
        if GoogleProvider:
            register_provider("google", GoogleProvider)
        if AzureProvider:
            register_provider("azure", AzureProvider)
        if GroqProvider:
            register_provider("groq", GroqProvider)
        if OllamaProvider:
            register_provider("ollama", OllamaProvider)
        if MistralProvider:
            register_provider("mistral", MistralProvider)
        if CohereProvider:
            register_provider("cohere", CohereProvider)
        if TogetherProvider:
            register_provider("together", TogetherProvider)
        if FireworksProvider:
            register_provider("fireworks", FireworksProvider)
        if DeepSeekProvider:
            register_provider("deepseek", DeepSeekProvider)
        if XAIProvider:
            register_provider("xai", XAIProvider)
        if HuggingFaceProvider:
            register_provider("huggingface", HuggingFaceProvider)
        if OpenRouterProvider:
            register_provider("openrouter", OpenRouterProvider)
        if MinimaxProvider:
            register_provider("minimax", MinimaxProvider)
        if QwenProvider:
            register_provider("qwen", QwenProvider)
        if ZhipuAIProvider:
            register_provider("zhipuai", ZhipuAIProvider)

    def create(
        self,
        provider: str | None = None,
        model: str | None = None,
        **kwargs: Any,
    ) -> BaseChatModel:
        """
        Create an LLM instance.

        Args:
            provider: Provider name (e.g., 'openai', 'anthropic')
            model: Model name or 'provider/model' string
            **kwargs: Additional provider-specific configuration

        Returns:
            A LangChain BaseChatModel instance

        Raises:
            LLMProviderNotFoundError: If provider is not found
            LLMConfigurationError: If required configuration is missing
        """
        if model and "/" in model and provider is None:
            provider, model = parse_model_string(model)

        if not provider:
            if model:
                provider = detect_provider_from_model(model)
            if not provider:
                raise LLMProviderNotFoundError(
                    provider="unknown",
                    message="Could not determine provider. Please specify provider explicitly.",
                )

        provider_lower = provider.lower()

        if provider_lower not in _PROVIDER_REGISTRY:
            raise LLMProviderNotFoundError(provider=provider_lower)

        if not model:
            raise LLMConfigurationError("Model name is required", provider=provider_lower)

        provider_class = _PROVIDER_REGISTRY[provider_lower]
        settings = get_settings()

        provider_instance = provider_class.from_settings(settings)
        return provider_instance.create_chat_model(model, **kwargs)


_factory: LLMFactory | None = None


def _get_factory() -> LLMFactory:
    global _factory
    if _factory is None:
        _factory = LLMFactory()
    return _factory


def get_llm(
    provider: str | None = None,
    model: str | None = None,
    **kwargs: Any,
) -> BaseChatModel:
    """
    Get an LLM instance.

    Args:
        provider: Provider name (e.g., 'openai', 'anthropic')
        model: Model name or 'provider/model' string
        **kwargs: Additional provider-specific configuration

    Returns:
        A LangChain BaseChatModel instance
    """
    return _get_factory().create(provider=provider, model=model, **kwargs)


def get_summarization_llm(**kwargs: Any) -> BaseChatModel:
    """
    Get an LLM instance configured for summarization tasks.

    Uses the SUMMARIZATION_MODEL from settings.

    Args:
        **kwargs: Additional provider-specific configuration

    Returns:
        A LangChain BaseChatModel instance for summarization
    """
    settings = get_settings()
    provider, model = parse_model_string(settings.llm.summarization_model)
    return get_llm(provider=provider, model=model, **kwargs)


def get_default_llm(**kwargs: Any) -> BaseChatModel:
    """
    Get the default LLM instance.

    Uses the DEFAULT_MODEL from settings.

    Args:
        **kwargs: Additional provider-specific configuration

    Returns:
        A LangChain BaseChatModel instance
    """
    settings = get_settings()
    provider, model = parse_model_string(settings.llm.default_model)
    return get_llm(provider=provider, model=model, **kwargs)
