from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langchain_mistralai import ChatMistralAI

from src.llm.base import BaseLLMProvider
from src.llm.errors import LLMConfigurationError

if TYPE_CHECKING:
    from src.config.settings import Settings


class MistralProvider(BaseLLMProvider):
    """Mistral AI LLM provider."""

    @property
    def provider_name(self) -> str:
        return "mistral"

    def is_available(self) -> bool:
        return bool(self.api_key)

    @classmethod
    def from_settings(cls, settings: Settings) -> MistralProvider:
        return cls(api_key=settings.llm.mistral_api_key)

    def create_chat_model(self, model: str, **kwargs: Any) -> ChatMistralAI:
        if not self.api_key:
            raise LLMConfigurationError(
                "Mistral API key is required. Set MISTRAL_API_KEY environment variable.",
                provider=self.provider_name,
            )

        config = self.get_config(**kwargs)
        config["model"] = model

        if "api_key" in config:
            del config["api_key"]

        # Add callbacks (e.g., Langfuse)
        callbacks = self._get_callbacks()
        if callbacks:
            config["callbacks"] = callbacks

        return ChatMistralAI(api_key=self.api_key, **config)
