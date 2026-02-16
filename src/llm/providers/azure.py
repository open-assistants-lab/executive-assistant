from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langchain_openai import AzureChatOpenAI

from src.llm.base import BaseLLMProvider
from src.llm.errors import LLMConfigurationError

if TYPE_CHECKING:
    from src.config.settings import Settings


class AzureProvider(BaseLLMProvider):
    """Azure OpenAI LLM provider."""

    @property
    def provider_name(self) -> str:
        return "azure"

    def is_available(self) -> bool:
        return bool(self.api_key and self.base_url)

    @classmethod
    def from_settings(cls, settings: Settings) -> AzureProvider:
        return cls(
            api_key=settings.llm.azure_openai_api_key,
            base_url=settings.llm.azure_openai_endpoint,
            api_version=settings.llm.azure_openai_api_version,
        )

    def create_chat_model(self, model: str, **kwargs: Any) -> AzureChatOpenAI:
        if not self.api_key:
            raise LLMConfigurationError(
                "Azure OpenAI API key is required. Set AZURE_OPENAI_API_KEY environment variable.",
                provider=self.provider_name,
            )
        if not self.base_url:
            raise LLMConfigurationError(
                "Azure OpenAI endpoint is required. Set AZURE_OPENAI_ENDPOINT environment variable.",
                provider=self.provider_name,
            )

        config = self.get_config(**kwargs)
        config["azure_deployment"] = model

        api_version = config.pop("api_version", "2024-12-01-preview")
        api_key = config.pop("api_key", self.api_key)
        base_url = config.pop("base_url", self.base_url)

        # Add callbacks (e.g., Langfuse)
        callbacks = self._get_callbacks()
        if callbacks:
            config["callbacks"] = callbacks

        return AzureChatOpenAI(
            api_key=api_key,
            azure_endpoint=base_url,
            api_version=api_version,
            **config,
        )
