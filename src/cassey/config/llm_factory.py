"""LLM provider factory for creating chat models."""

from functools import lru_cache
from typing import Literal

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from cassey.config.settings import settings


# Default model configurations
MODEL_CONFIGS = {
    "anthropic": {
        "default": "claude-sonnet-4-5-20250929",
        "fast": "claude-3-5-haiku-20241022",
    },
    "openai": {
        "default": "gpt-5.1",
        "fast": "gpt-4o-mini",
    },
    "zhipu": {
        "default": "glm-4-plus",
        "fast": "glm-4-flash",
    },
}


class LLMFactory:
    """Factory for creating LLM instances."""

    @staticmethod
    def _create_anthropic(model: str = "default", **kwargs) -> ChatAnthropic:
        """Create Anthropic Claude model."""
        if not settings.ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY not set")
        model_name = MODEL_CONFIGS["anthropic"].get(model, model)
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
        model_name = MODEL_CONFIGS["openai"].get(model, model)
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

        model_name = MODEL_CONFIGS["zhipu"].get(model, model)

        # Create ChatOpenAI with Zhipu's endpoint
        return ChatOpenAI(
            model=model_name,
            api_key=settings.ZHIPUAI_API_KEY,
            base_url="https://open.bigmodel.cn/api/paas/v4/",
            temperature=kwargs.get("temperature", 0.7),
            max_tokens=kwargs.get("max_tokens", 4096),
            **kwargs,
        )

    @classmethod
    def create(
        cls,
        provider: Literal["anthropic", "openai", "zhipu"] | None = None,
        model: str = "default",
        **kwargs,
    ) -> BaseChatModel:
        """
        Create a chat model instance.

        Args:
            provider: LLM provider (anthropic, openai, zhipu). Defaults to DEFAULT_LLM_PROVIDER.
            model: Model variant (default, fast). Defaults to "default".
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
