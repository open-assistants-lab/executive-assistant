from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langchain_together import ChatTogether

from src.llm.base import BaseLLMProvider
from src.llm.errors import LLMConfigurationError

if TYPE_CHECKING:
    from src.config.settings import Settings


class TogetherProvider(BaseLLMProvider):
    """Together AI LLM provider."""

    @property
    def provider_name(self) -> str:
        return "together"

    def is_available(self) -> bool:
        return bool(self.api_key)

    @classmethod
    def from_settings(cls, settings: Settings) -> TogetherProvider:
        return cls(api_key=settings.llm.together_api_key)

    def create_chat_model(self, model: str, **kwargs: Any) -> ChatTogether:
        if not self.api_key:
            raise LLMConfigurationError(
                "Together API key is required. Set TOGETHER_API_KEY environment variable.",
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

        return ChatTogether(api_key=self.api_key, **config)
