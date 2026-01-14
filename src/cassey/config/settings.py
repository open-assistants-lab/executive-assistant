"""Application settings with environment variable loading."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # LLM Configuration
    DEFAULT_LLM_PROVIDER: Literal["anthropic", "openai", "zhipu"] = "anthropic"
    ANTHROPIC_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None
    ZHIPUAI_API_KEY: str | None = None

    # Telegram Configuration
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_WEBHOOK_URL: str | None = None
    TELEGRAM_WEBHOOK_SECRET: str | None = None

    # Storage Configuration
    CHECKPOINT_STORAGE: Literal["postgres", "memory"] = "postgres"

    # PostgreSQL Configuration
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "cassey"
    POSTGRES_PASSWORD: str = "cassey_password"
    POSTGRES_DB: str = "cassey_db"

    # Security / File Sandbox
    FILES_ROOT: Path = Field(default=Path("./data/files"))
    MAX_FILE_SIZE_MB: int = 10

    # Database Storage
    DB_ROOT: Path = Field(default=Path("./data/db"))

    # Context Management
    MAX_CONTEXT_TOKENS: int = 100_000  # Max tokens before summarization
    ENABLE_SUMMARIZATION: bool = True  # Enable running summaries by default
    SUMMARY_THRESHOLD: int = 20  # Summarize after N messages

    # Web Search
    SEARXNG_HOST: str | None = None

    # Allowed file extensions for file operations
    ALLOWED_FILE_EXTENSIONS: set[str] = Field(
        default={
            ".txt",
            ".md",
            ".py",
            ".js",
            ".ts",
            ".json",
            ".yaml",
            ".yml",
            ".csv",
            ".xml",
            ".html",
            ".css",
            ".sh",
            ".bash",
        }
    )

    @field_validator("FILES_ROOT", mode="before")
    @classmethod
    def resolve_files_root(cls, v: str | Path) -> Path:
        """Resolve files root to absolute path."""
        return Path(v).resolve()

    @field_validator("DB_ROOT", mode="before")
    @classmethod
    def resolve_db_root(cls, v: str | Path) -> Path:
        """Resolve database root to absolute path."""
        return Path(v).resolve()

    def get_files_path(self, user_id: str) -> Path:
        """Get files path for a specific user."""
        user_path = self.FILES_ROOT / user_id
        user_path.mkdir(parents=True, exist_ok=True)
        return user_path

    @property
    def POSTGRES_URL(self) -> str:
        """Construct PostgreSQL connection URL from individual components."""
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Singleton instance
settings = get_settings()
