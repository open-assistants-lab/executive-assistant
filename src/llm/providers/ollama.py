from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.llm.base import BaseLLMProvider
from src.llm.errors import LLMConfigurationError

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel

    from src.config.settings import Settings


class OllamaProvider(BaseLLMProvider):
    """Ollama LLM provider for local/cloud models."""

    @property
    def provider_name(self) -> str:
        return "ollama"

    def is_available(self) -> bool:
        return bool(self.base_url)

    @classmethod
    def from_settings(cls, settings: Settings) -> OllamaProvider:
        return cls(
            base_url=settings.llm.ollama_base_url,
            api_key=settings.llm.ollama_api_key,
        )

    def create_chat_model(self, model: str, **kwargs: Any) -> BaseChatModel:
        """Create chat model for Ollama (local or cloud).

        For cloud mode (with API key), uses https://ollama.com with Authorization header.
        For local mode, uses ChatOllama with local Ollama.
        """
        from langchain_ollama import ChatOllama

        config = self.get_config(**kwargs)
        base_url = config.pop("base_url", self.base_url or "http://localhost:11434")
        api_key = config.pop("api_key", self.api_key)

        if api_key:
            config["client_kwargs"] = {"headers": {"Authorization": f"Bearer {api_key}"}}

        config["model"] = model
        config["base_url"] = base_url

        # Add callbacks (e.g., Langfuse)
        callbacks = self._get_callbacks()
        if callbacks:
            config["callbacks"] = callbacks

        return ChatOllama(**config)
