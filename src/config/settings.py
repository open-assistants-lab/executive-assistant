from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.config.middleware_settings import MiddlewareConfig


def parse_model_string(model_string: str) -> tuple[str, str]:
    """
    Parse a model string in the format 'provider/model-name'.

    Args:
        model_string: Model identifier string (e.g., 'openai/gpt-4o')

    Returns:
        Tuple of (provider, model_name)

    Raises:
        ValueError: If the model string is not in the correct format
    """
    if not model_string or "/" not in model_string:
        raise ValueError(f"Invalid model format: '{model_string}'. Expected 'provider/model-name'")
    parts = model_string.split("/", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError(f"Invalid model format: '{model_string}'. Expected 'provider/model-name'")
    return parts[0].lower(), parts[1]


class LLMSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    default_model: str = Field(
        default="openai/gpt-4o",
        description="Default chat model in format provider/model-name",
    )
    summarization_model: str = Field(
        default="openai/gpt-4o-mini",
        description="Model for summarization tasks in format provider/model-name",
    )

    openai_api_key: str | None = Field(default=None, description="OpenAI API key")
    anthropic_api_key: str | None = Field(default=None, description="Anthropic API key")
    google_api_key: str | None = Field(default=None, description="Google API key")
    azure_openai_api_key: str | None = Field(default=None, description="Azure OpenAI API key")
    azure_openai_endpoint: str | None = Field(default=None, description="Azure OpenAI endpoint")
    azure_openai_api_version: str = Field(
        default="2024-12-01-preview", description="Azure OpenAI API version"
    )
    groq_api_key: str | None = Field(default=None, description="Groq API key")
    xai_api_key: str | None = Field(default=None, description="xAI (Grok) API key")
    nvidia_api_key: str | None = Field(default=None, description="NVIDIA NIM API key")
    cohere_api_key: str | None = Field(default=None, description="Cohere API key")
    mistral_api_key: str | None = Field(default=None, description="Mistral API key")
    together_api_key: str | None = Field(default=None, description="Together AI API key")
    fireworks_api_key: str | None = Field(default=None, description="Fireworks API key")
    deepseek_api_key: str | None = Field(default=None, description="DeepSeek API key")
    huggingface_api_key: str | None = Field(default=None, description="HuggingFace API key")
    openrouter_api_key: str | None = Field(default=None, description="OpenRouter API key")

    ollama_base_url: str = Field(
        default="http://localhost:11434", description="Ollama base URL (local or cloud)"
    )
    ollama_api_key: str | None = Field(default=None, description="Ollama API key for cloud mode")

    aws_access_key_id: str | None = Field(default=None, description="AWS Access Key ID")
    aws_secret_access_key: str | None = Field(default=None, description="AWS Secret Access Key")
    aws_region: str = Field(default="us-east-1", description="AWS Region")

    databricks_host: str | None = Field(default=None, description="Databricks host")
    databricks_token: str | None = Field(default=None, description="Databricks token")

    watsonx_url: str | None = Field(default=None, description="IBM Watsonx URL")
    watsonx_apikey: str | None = Field(default=None, description="IBM Watsonx API key")

    llamacpp_model_path: str | None = Field(default=None, description="Llama.cpp model path")

    minimax_api_key: str | None = Field(default=None, description="Minimax API key")
    minimax_group_id: str | None = Field(default=None, description="Minimax Group ID")

    dashscope_api_key: str | None = Field(
        default=None, description="Dashscope (Qwen/Alibaba) API key"
    )

    zhipuai_api_key: str | None = Field(default=None, description="Zhipu AI API key")

    @field_validator("default_model", "summarization_model")
    @classmethod
    def validate_model_format(cls, v: str) -> str:
        parse_model_string(v)
        return v

    def get_default_provider_model(self) -> tuple[str, str]:
        return parse_model_string(self.default_model)

    def get_summarization_provider_model(self) -> tuple[str, str]:
        return parse_model_string(self.summarization_model)


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: str = Field(default="development", description="Application environment")
    debug: bool = Field(default=True, description="Debug mode")
    secret_key: str = Field(default="change-me-in-production", description="Application secret key")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_nested_delimiter="__",
    )

    app: AppSettings = Field(default_factory=AppSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    middleware: MiddlewareConfig = Field(
        default_factory=MiddlewareConfig,
        description="Middleware configuration (loaded from YAML, not env vars)",
    )

    database_url: str = Field(
        default="postgresql://agent:password@postgres:5432/agent",
        description="PostgreSQL connection URL for checkpoints",
    )
    data_path: Path = Field(
        default=Path("/data"),
        description="Base path for all persistent data (users, shared)",
    )

    @property
    def shared_path(self) -> Path:
        """Path to shared resources (skills, knowledge, templates)."""
        return self.data_path / "shared"

    @property
    def users_path(self) -> Path:
        """Path to user-specific data."""
        return self.data_path / "users"

    def get_user_path(self, user_id: str) -> Path:
        """Get path for a specific user's data."""
        return self.users_path / user_id

    langfuse_public_key: str | None = Field(default=None, description="Langfuse public key")
    langfuse_secret_key: str | None = Field(default=None, description="Langfuse secret key")
    langfuse_host: str = Field(default="https://cloud.langfuse.com", description="Langfuse host")

    google_client_id: str | None = Field(default=None, description="Google OAuth client ID")
    google_client_secret: str | None = Field(default=None, description="Google OAuth client secret")
    microsoft_client_id: str | None = Field(default=None, description="Microsoft OAuth client ID")
    microsoft_client_secret: str | None = Field(
        default=None, description="Microsoft OAuth client secret"
    )
    microsoft_tenant_id: str = Field(default="common", description="Microsoft tenant ID")

    api_host: str = Field(default="0.0.0.0", description="API server host")
    api_port: int = Field(default=8000, description="API server port")

    telegram_bot_token: str | None = Field(default=None, description="Telegram bot token")

    tavily_api_key: str | None = Field(default=None, description="Tavily API key for web search")

    firecrawl_api_key: str | None = Field(default=None, description="Firecrawl API key")
    firecrawl_base_url: str = Field(
        default="https://api.firecrawl.dev",
        description="Firecrawl base URL"
    )

    agent_name: str = Field(
        default="Executive Assistant",
        description="Name of the agent (customizable by user)",
    )

    @property
    def is_langfuse_configured(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key)

    @property
    def is_telegram_configured(self) -> bool:
        return bool(self.telegram_bot_token)

    @property
    def is_google_oauth_configured(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)

    @property
    def is_microsoft_oauth_configured(self) -> bool:
        return bool(self.microsoft_client_id and self.microsoft_client_secret)


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    global _settings
    _settings = None
