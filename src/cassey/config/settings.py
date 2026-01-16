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
    TELEGRAM_BOT_TOKEN: str | None = None
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
    KB_ROOT: Path = Field(default=Path("./data/kb"))

    # New consolidated storage (per-thread user data)
    USERS_ROOT: Path = Field(default=Path("./data/users"))
    SHARED_DB_PATH: Path = Field(default=Path("./data/shared/shared.db"))

    # Admin access control
    ADMIN_USER_IDS: set[str] = Field(default_factory=set)
    ADMIN_THREAD_IDS: set[str] = Field(default_factory=set)

    # Agent Runtime
    AGENT_RUNTIME: Literal["langchain", "custom"] = "langchain"
    AGENT_RUNTIME_FALLBACK: Literal["langchain", "custom"] | None = None

    # LangChain Middleware (agent runtime)
    MW_SUMMARIZATION_ENABLED: bool = True
    MW_SUMMARIZATION_MAX_TOKENS: int = 10_000
    MW_SUMMARIZATION_TARGET_TOKENS: int = 2_000
    MW_MODEL_CALL_LIMIT: int = 50
    MW_TOOL_CALL_LIMIT: int = 100
    MW_TOOL_RETRY_ENABLED: bool = True
    MW_MODEL_RETRY_ENABLED: bool = True
    MW_HITL_ENABLED: bool = False

    # Context Management
    MAX_CONTEXT_TOKENS: int = 100_000  # Max tokens before summarization
    ENABLE_SUMMARIZATION: bool = True  # Enable running summaries by default
    SUMMARY_THRESHOLD: int = 20  # Summarize after N messages
    MAX_ITERATIONS: int = 20  # Maximum ReAct loop iterations to prevent infinite loops

    # Memory (Embedded User Memories)
    MEM_AUTO_EXTRACT: bool = False  # Auto-extract memories from each message
    MEM_CONFIDENCE_MIN: float = 0.6  # Minimum confidence to save a memory
    MEM_MAX_PER_TURN: int = 3  # Max memories to extract per turn
    MEM_EXTRACT_MODEL: str = "gpt-4o-mini"  # Model for extraction
    MEM_EXTRACT_PROVIDER: Literal["anthropic", "openai", "zhipu"] = "openai"
    MEM_EXTRACT_TEMPERATURE: float = 0.0  # Temperature for extraction

    # Web Search
    SEARXNG_HOST: str | None = None

    # Logging
    LOG_LEVEL: str = "INFO"  # Log level for console output
    LOG_FILE: str | None = None  # Optional log file path

    # Firecrawl (web scraping API)
    FIRECRAWL_API_KEY: str | None = None  # Firecrawl API key
    FIRECRAWL_API_URL: str = "https://api.firecrawl.dev"  # Firecrawl API base URL

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
            ".log",
            ".pdf",
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

    @field_validator("KB_ROOT", mode="before")
    @classmethod
    def resolve_kb_root(cls, v: str | Path) -> Path:
        """Resolve knowledge base root to absolute path."""
        return Path(v).resolve()

    @field_validator("USERS_ROOT", mode="before")
    @classmethod
    def resolve_users_root(cls, v: str | Path) -> Path:
        """Resolve users root to absolute path."""
        return Path(v).resolve()

    @field_validator("SHARED_DB_PATH", mode="before")
    @classmethod
    def resolve_shared_db_path(cls, v: str | Path) -> Path:
        """Resolve shared DB path to absolute path."""
        return Path(v).resolve()

    @field_validator("ADMIN_USER_IDS", mode="before")
    @classmethod
    def parse_admin_user_ids(cls, v: str | list[str] | set[str] | None) -> set[str]:
        """Parse admin user IDs from comma-separated string or list."""
        if v is None:
            return set()
        if isinstance(v, set):
            return {str(item).strip() for item in v if str(item).strip()}
        if isinstance(v, list):
            return {str(item).strip() for item in v if str(item).strip()}
        if isinstance(v, str):
            return {item.strip() for item in v.split(",") if item.strip()}
        return {str(v).strip()}

    @field_validator("ADMIN_THREAD_IDS", mode="before")
    @classmethod
    def parse_admin_thread_ids(cls, v: str | list[str] | set[str] | None) -> set[str]:
        """Parse admin thread IDs from comma-separated string or list."""
        if v is None:
            return set()
        if isinstance(v, set):
            return {str(item).strip() for item in v if str(item).strip()}
        if isinstance(v, list):
            return {str(item).strip() for item in v if str(item).strip()}
        if isinstance(v, str):
            return {item.strip() for item in v.split(",") if item.strip()}
        return {str(v).strip()}

    @field_validator("AGENT_RUNTIME", "AGENT_RUNTIME_FALLBACK", mode="before")
    @classmethod
    def normalize_agent_runtime(cls, v: str | None) -> str | None:
        """Normalize agent runtime values to lowercase strings."""
        if v is None:
            return None
        if isinstance(v, str):
            normalized = v.strip().lower()
            return normalized or None
        return v

    def _sanitize_thread_id(self, thread_id: str) -> str:
        """Sanitize thread_id for use as directory name."""
        replacements = {":": "_", "/": "_", "@": "_", "\\": "_"}
        for old, new in replacements.items():
            thread_id = thread_id.replace(old, new)
        return thread_id

    def get_thread_root(self, thread_id: str) -> Path:
        """
        Get the root directory for a specific thread (new structure).

        Returns: data/users/{thread_id}/
        """
        safe_thread_id = self._sanitize_thread_id(thread_id)
        return (self.USERS_ROOT / safe_thread_id).resolve()

    def get_thread_files_path(self, thread_id: str) -> Path:
        """
        Get files directory for a thread (new structure).

        Returns: data/users/{thread_id}/files/
        With fallback to: data/files/{thread_id}/
        """
        safe_thread_id = self._sanitize_thread_id(thread_id)
        new_path = (self.USERS_ROOT / safe_thread_id / "files").resolve()

        # Backward compatibility: use old path if new path doesn't exist
        if not new_path.exists():
            old_path = (self.FILES_ROOT / safe_thread_id).resolve()
            if old_path.exists():
                return old_path

        return new_path

    def get_thread_db_path(self, thread_id: str) -> Path:
        """
        Get database file path for a thread (new structure).

        Returns: data/users/{thread_id}/db/db.db
        With fallback to: data/db/{thread_id}.db
        """
        safe_thread_id = self._sanitize_thread_id(thread_id)
        new_path = (self.USERS_ROOT / safe_thread_id / "db" / "db.db").resolve()

        # Backward compatibility: use old path if new path doesn't exist
        if not new_path.exists():
            old_path = (self.DB_ROOT / f"{safe_thread_id}.db").resolve()
            if old_path.exists():
                return old_path

        return new_path

    def get_thread_kb_path(self, thread_id: str) -> Path:
        """
        Get KB file path for a thread (new structure).

        Returns: data/users/{thread_id}/kb/kb.db
        With fallback to: data/kb/{thread_id}.db
        """
        safe_thread_id = self._sanitize_thread_id(thread_id)
        new_path = (self.USERS_ROOT / safe_thread_id / "kb" / "kb.db").resolve()

        # Backward compatibility: use old path if new path doesn't exist
        if not new_path.exists():
            old_path = (self.KB_ROOT / f"{safe_thread_id}.db").resolve()
            if old_path.exists():
                return old_path

        return new_path

    def get_thread_mem_path(self, thread_id: str) -> Path:
        """
        Get memory (mem.db) file path for a thread.

        Returns: data/users/{thread_id}/mem/mem.db
        With fallback to: data/mem/{thread_id}.db (if exists)
        """
        safe_thread_id = self._sanitize_thread_id(thread_id)
        new_path = (self.USERS_ROOT / safe_thread_id / "mem" / "mem.db").resolve()

        # Backward compatibility: use old path if new path doesn't exist
        if not new_path.exists():
            old_path = (Path("./data/mem") / f"{safe_thread_id}.db").resolve()
            if old_path.exists():
                return old_path

        return new_path

    def get_thread_plan_path(self, thread_id: str) -> Path:
        """
        Get plan directory path for a thread.

        Returns: data/users/{thread_id}/plan/
        """
        safe_thread_id = self._sanitize_thread_id(thread_id)
        return (self.USERS_ROOT / safe_thread_id / "plan").resolve()

    def is_new_storage_layout(self, thread_id: str) -> bool:
        """
        Check if a thread is using the new storage layout.

        Returns True if data/users/{thread_id}/ exists, False otherwise.
        """
        new_path = self.get_thread_root(thread_id)
        return new_path.exists()

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
