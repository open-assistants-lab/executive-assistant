from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langchain_openai import ChatOpenAI

from src.llm.base import BaseLLMProvider
from src.llm.errors import LLMConfigurationError

if TYPE_CHECKING:
    from src.config.settings import Settings


class OpenRouterProvider(BaseLLMProvider):
    """OpenRouter LLM provider - access multiple models via unified API."""

    OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

    @property
    def provider_name(self) -> str:
        return "openrouter"

    def is_available(self) -> bool:
        return bool(self.api_key)

    @classmethod
    def from_settings(cls, settings: Settings) -> OpenRouterProvider:
        return cls(
            api_key=settings.llm.openrouter_api_key,
            base_url=cls.OPENROUTER_BASE_URL,
        )

    def create_chat_model(self, model: str, **kwargs: Any) -> ChatOpenAI:
        if not self.api_key:
            raise LLMConfigurationError(
                "OpenRouter API key is required. Set OPENROUTER_API_KEY environment variable.",
                provider=self.provider_name,
            )

        config = self.get_config(**kwargs)
        config["model"] = model
        config["base_url"] = self.base_url or self.OPENROUTER_BASE_URL

        if "api_key" in config:
            del config["api_key"]

        # Add callbacks (e.g., Langfuse)
        callbacks = self._get_callbacks()
        if callbacks:
            config["callbacks"] = callbacks

        return ChatOpenAI(api_key=self.api_key, **config)
