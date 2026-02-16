from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langchain_huggingface import ChatHuggingFace
from langchain_huggingface.llms.huggingface_endpoint import HuggingFaceEndpoint

from src.llm.base import BaseLLMProvider
from src.llm.errors import LLMConfigurationError

if TYPE_CHECKING:
    from src.config.settings import Settings


class HuggingFaceProvider(BaseLLMProvider):
    """HuggingFace LLM provider."""

    @property
    def provider_name(self) -> str:
        return "huggingface"

    def is_available(self) -> bool:
        return bool(self.api_key)

    @classmethod
    def from_settings(cls, settings: Settings) -> HuggingFaceProvider:
        return cls(api_key=settings.llm.huggingface_api_key)

    def create_chat_model(self, model: str, **kwargs: Any) -> ChatHuggingFace:
        if not self.api_key:
            raise LLMConfigurationError(
                "HuggingFace API key is required. Set HUGGINGFACE_API_KEY environment variable.",
                provider=self.provider_name,
            )

        config = self.get_config(**kwargs)

        if "api_key" in config:
            del config["api_key"]

        # Add callbacks (e.g., Langfuse)
        callbacks = self._get_callbacks()
        if callbacks:
            config["callbacks"] = callbacks

        llm = HuggingFaceEndpoint(
            repo_id=model,
            huggingfacehub_api_token=self.api_key,
            **config,
        )
        return ChatHuggingFace(llm=llm)
