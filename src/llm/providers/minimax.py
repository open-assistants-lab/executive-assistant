from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langchain_openai import ChatOpenAI

from src.llm.base import BaseLLMProvider
from src.llm.errors import LLMConfigurationError

if TYPE_CHECKING:
    from src.config.settings import Settings


class MinimaxProvider(BaseLLMProvider):
    """Minimax LLM provider (Chinese LLM) - uses OpenAI-compatible API."""

    MINIMAX_BASE_URL = "https://api.minimax.chat/v1"

    @property
    def provider_name(self) -> str:
        return "minimax"

    def is_available(self) -> bool:
        return bool(self.api_key and self.group_id)

    @classmethod
    def from_settings(cls, settings: Settings) -> MinimaxProvider:
        return cls(
            api_key=settings.llm.minimax_api_key,
            group_id=settings.llm.minimax_group_id,
        )

    def __init__(
        self,
        api_key: str | None = None,
        group_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(api_key=api_key, **kwargs)
        self.group_id = group_id

    def create_chat_model(self, model: str, **kwargs: Any) -> ChatOpenAI:
        if not self.api_key:
            raise LLMConfigurationError(
                "Minimax API key is required. Set MINIMAX_API_KEY environment variable.",
                provider=self.provider_name,
            )
        if not self.group_id:
            raise LLMConfigurationError(
                "Minimax Group ID is required. Set MINIMAX_GROUP_ID environment variable.",
                provider=self.provider_name,
            )

        config = self.get_config(**kwargs)

        # Add callbacks (e.g., Langfuse)
        callbacks = self._get_callbacks()
        if callbacks:
            config["callbacks"] = callbacks

        # Minimax uses OpenAI-compatible API
        return ChatOpenAI(
            model=model,
            api_key=self.api_key,
            base_url=self.MINIMAX_BASE_URL,
            **config,
        )
