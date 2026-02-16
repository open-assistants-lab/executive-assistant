from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.callbacks import BaseCallbackHandler


class BaseLLMProvider(ABC):
    """
    Abstract base class for LLM providers.

    All LLM provider implementations must inherit from this class
    and implement the required abstract methods.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: int | None = None,
        **kwargs: Any,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self.extra_config = kwargs

    @abstractmethod
    def create_chat_model(self, model: str, **kwargs: Any) -> BaseChatModel:
        """
        Create and return a LangChain chat model instance.

        Args:
            model: The model identifier (e.g., 'gpt-4o', 'claude-3-5-sonnet')
            **kwargs: Additional provider-specific configuration

        Returns:
            A LangChain BaseChatModel instance
        """
        pass

    def _get_callbacks(self) -> list[BaseCallbackHandler]:
        """
        Get callbacks to attach to the model.

        Returns:
            List of callback handlers (e.g., Langfuse CallbackHandler)
        """
        callbacks: list[BaseCallbackHandler] = []

        # Add Langfuse callback if configured
        try:
            from src.config.settings import get_settings

            settings = get_settings()
            if settings.is_langfuse_configured:
                from langfuse import Langfuse
                from langfuse.langchain import CallbackHandler

                # Initialize Langfuse client with credentials (singleton)
                # This creates the singleton client that CallbackHandler will use
                Langfuse(
                    public_key=settings.langfuse_public_key,
                    secret_key=settings.langfuse_secret_key,
                    host=settings.langfuse_host,
                )

                # CallbackHandler automatically uses the singleton client
                # No constructor args needed in v3
                callbacks.append(CallbackHandler())
        except ImportError:
            pass
        except Exception:
            pass

        return callbacks

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if the provider is properly configured and available.

        Returns:
            True if the provider can be used, False otherwise
        """
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """
        Return the name of this provider.

        Returns:
            Provider name (e.g., 'openai', 'anthropic')
        """
        pass

    def get_config(self, **overrides: Any) -> dict[str, Any]:
        """
        Get the configuration for this provider.

        Args:
            **overrides: Configuration values to override

        Returns:
            Configuration dictionary
        """
        config: dict[str, Any] = {}
        if self.api_key:
            config["api_key"] = self.api_key
        if self.base_url:
            config["base_url"] = self.base_url
        if self.timeout:
            config["timeout"] = self.timeout
        config.update(self.extra_config)
        config.update(overrides)
        return config
