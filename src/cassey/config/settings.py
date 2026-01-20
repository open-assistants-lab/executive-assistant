"""Application settings with YAML defaults and .env overrides."""

import logging
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from cassey.config.loader import get_yaml_defaults

logger = logging.getLogger(__name__)

# Get flattened defaults from YAML config
_yaml_defaults = get_yaml_defaults()


def _yaml_field(key: str, default, alias: str | None = None):
    """Create a Pydantic Field with YAML default.

    Args:
        key: Flattened YAML key (e.g., "LLM_DEFAULT_PROVIDER").
        default: Fallback default if not in YAML.
        alias: Optional field alias.

    Returns:
        Pydantic Field with appropriate default.
    """
    yaml_value = _yaml_defaults.get(key.upper(), default)
    return Field(default=yaml_value, alias=alias)


class Settings(BaseSettings):
    """Application settings loaded from YAML defaults + environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ============================================================================
    # LLM Configuration
    # ============================================================================

    DEFAULT_LLM_PROVIDER: Literal["anthropic", "openai", "zhipu", "ollama"] = _yaml_field(
        "LLM_DEFAULT_PROVIDER", "anthropic"
    )

    # Global Model Overrides (apply to all providers)
    DEFAULT_LLM_MODEL: str | None = _yaml_field("LLM_DEFAULT_MODEL", None)
    FAST_LLM_MODEL: str | None = _yaml_field("LLM_FAST_MODEL", None)

    # Provider-Specific Model Overrides (higher priority)
    ANTHROPIC_DEFAULT_MODEL: str | None = _yaml_field("LLM_ANTHROPIC_DEFAULT_MODEL", None)
    ANTHROPIC_FAST_MODEL: str | None = _yaml_field("LLM_ANTHROPIC_FAST_MODEL", None)
    OPENAI_DEFAULT_MODEL: str | None = _yaml_field("LLM_OPENAI_DEFAULT_MODEL", None)
    OPENAI_FAST_MODEL: str | None = _yaml_field("LLM_OPENAI_FAST_MODEL", None)
    ZHIPU_DEFAULT_MODEL: str | None = _yaml_field("LLM_ZHIPU_DEFAULT_MODEL", None)
    ZHIPU_FAST_MODEL: str | None = _yaml_field("LLM_ZHIPU_FAST_MODEL", None)
    OLLAMA_DEFAULT_MODEL: str | None = _yaml_field("LLM_OLLAMA_DEFAULT_MODEL", None)
    OLLAMA_FAST_MODEL: str | None = _yaml_field("LLM_OLLAMA_FAST_MODEL", None)

    # API Keys (secrets - must be in .env)
    ANTHROPIC_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None
    ZHIPUAI_API_KEY: str | None = None

    # ============================================================================
    # Ollama Configuration
    # ============================================================================

    OLLAMA_MODE: Literal["cloud", "local"] = _yaml_field("LLM_OLLAMA_MODE", "cloud")

    # Cloud Mode
    OLLAMA_CLOUD_API_KEY: str | None = None  # Secret
    OLLAMA_CLOUD_URL: str = _yaml_field("LLM_OLLAMA_CLOUD_URL", "https://ollama.com")

    # Local Mode
    OLLAMA_LOCAL_URL: str = _yaml_field("LLM_OLLAMA_LOCAL_URL", "http://localhost:11434")

    # Backward compatibility (deprecated, maps to CLOUD_API_KEY)
    OLLAMA_API_KEY: str | None = None

    @model_validator(mode="after")
    @classmethod
    def map_ollama_api_key_to_cloud(cls, settings_obj: "Settings") -> "Settings":
        """Map legacy OLLAMA_API_KEY to OLLAMA_CLOUD_API_KEY."""
        if not settings_obj.OLLAMA_CLOUD_API_KEY and settings_obj.OLLAMA_API_KEY:
            settings_obj.OLLAMA_CLOUD_API_KEY = settings_obj.OLLAMA_API_KEY
        return settings_obj

    # Telegram Configuration
    TELEGRAM_BOT_TOKEN: str | None = None  # Secret
    TELEGRAM_WEBHOOK_URL: str | None = None
    TELEGRAM_WEBHOOK_SECRET: str | None = None  # Secret

    # Storage Configuration
    CHECKPOINT_STORAGE: Literal["postgres", "memory"] = _yaml_field("STORAGE_CHECKPOINT", "postgres")

    # PostgreSQL Configuration
    POSTGRES_HOST: str = _yaml_field("STORAGE_POSTGRES_HOST", "localhost")
    POSTGRES_PORT: int = _yaml_field("STORAGE_POSTGRES_PORT", 5432)
    POSTGRES_USER: str = _yaml_field("STORAGE_POSTGRES_USER", "cassey")
    POSTGRES_PASSWORD: str = "cassey_password"  # Secret - override in .env
    POSTGRES_DB: str = _yaml_field("STORAGE_POSTGRES_DB", "cassey_db")

    # Security / File Sandbox
    MAX_FILE_SIZE_MB: int = _yaml_field("STORAGE_MAX_FILE_SIZE_MB", 10)

    # ============================================================================
    # Storage Paths
    # ============================================================================

    # 3-level storage hierarchy
    # Level 1: Org-wide (admin write, everyone read)
    SHARED_ROOT: Path = _yaml_field("STORAGE_PATHS_SHARED_ROOT", Path("./data/shared"))

    # Level 2: Groups (collaborative, members can access)
    # Note: Renamed from WORKSPACES_ROOT to GROUPS_ROOT for clarity
    GROUPS_ROOT: Path = _yaml_field("STORAGE_PATHS_GROUPS_ROOT", Path("./data/groups"))
    # Deprecated alias for backward compatibility
    WORKSPACES_ROOT: Path = _yaml_field("STORAGE_PATHS_GROUPS_ROOT", Path("./data/groups"))

    # Level 3: Users (personal, only that user)
    USERS_ROOT: Path = _yaml_field("STORAGE_PATHS_USERS_ROOT", Path("./data/users"))

    # Admin access control (stored as comma-separated strings for env compatibility)
    ADMIN_USER_IDS_RAW: str = _yaml_field("ADMIN_USER_IDS", "", alias="ADMIN_USER_IDS")
    ADMIN_THREAD_IDS_RAW: str = _yaml_field("ADMIN_THREAD_IDS", "", alias="ADMIN_THREAD_IDS")

    @property
    def ADMIN_USER_IDS(self) -> set[str]:
        """Admin user IDs parsed from comma-separated string."""
        return {item.strip() for item in self.ADMIN_USER_IDS_RAW.split(",") if item.strip()} if self.ADMIN_USER_IDS_RAW else set()

    @property
    def ADMIN_THREAD_IDS(self) -> set[str]:
        """Admin thread IDs parsed from comma-separated string."""
        return {item.strip() for item in self.ADMIN_THREAD_IDS_RAW.split(",") if item.strip()} if self.ADMIN_THREAD_IDS_RAW else set()

    # LangChain Middleware (agent runtime)
    MW_SUMMARIZATION_ENABLED: bool = _yaml_field("MIDDLEWARE_SUMMARIZATION_ENABLED", True)
    MW_SUMMARIZATION_MAX_TOKENS: int = _yaml_field("MIDDLEWARE_SUMMARIZATION_MAX_TOKENS", 10_000)
    MW_SUMMARIZATION_TARGET_TOKENS: int = _yaml_field("MIDDLEWARE_SUMMARIZATION_TARGET_TOKENS", 2_000)
    MW_MODEL_CALL_LIMIT: int = _yaml_field("MIDDLEWARE_MODEL_CALL_LIMIT", 50)
    MW_TOOL_CALL_LIMIT: int = _yaml_field("MIDDLEWARE_TOOL_CALL_LIMIT", 100)
    MW_TOOL_RETRY_ENABLED: bool = _yaml_field("MIDDLEWARE_TOOL_RETRY_ENABLED", True)
    MW_MODEL_RETRY_ENABLED: bool = _yaml_field("MIDDLEWARE_MODEL_RETRY_ENABLED", True)
    MW_HITL_ENABLED: bool = _yaml_field("MIDDLEWARE_HITL_ENABLED", False)
    MW_TODO_LIST_ENABLED: bool = _yaml_field("MIDDLEWARE_TODO_LIST_ENABLED", True)
    MW_CONTEXT_EDITING_ENABLED: bool = _yaml_field("MIDDLEWARE_CONTEXT_EDITING_ENABLED", False)
    MW_CONTEXT_EDITING_TRIGGER_TOKENS: int = _yaml_field("MIDDLEWARE_CONTEXT_EDITING_TRIGGER_TOKENS", 100_000)
    MW_CONTEXT_EDITING_KEEP_TOOL_USES: int = _yaml_field("MIDDLEWARE_CONTEXT_EDITING_KEEP_TOOL_USES", 10)
    MW_STATUS_UPDATE_ENABLED: bool = _yaml_field("MIDDLEWARE_STATUS_UPDATES_ENABLED", True)
    MW_STATUS_SHOW_TOOL_ARGS: bool = _yaml_field("MIDDLEWARE_STATUS_UPDATES_SHOW_TOOL_ARGS", False)
    MW_STATUS_UPDATE_INTERVAL: float = _yaml_field("MIDDLEWARE_STATUS_UPDATES_UPDATE_INTERVAL", 0.5)

    # Todo List Display
    MW_TODO_LIST_MAX_DISPLAY: int = _yaml_field("MIDDLEWARE_TODO_LIST_MAX_DISPLAY", 10)
    MW_TODO_LIST_UPDATE_INTERVAL: float = _yaml_field("MIDDLEWARE_TODO_LIST_UPDATE_INTERVAL", 0.5)
    MW_TODO_LIST_SHOW_PROGRESS_BAR: bool = _yaml_field("MIDDLEWARE_TODO_LIST_SHOW_PROGRESS_BAR", False)

    # Vector Store (LanceDB)
    VS_EMBEDDING_MODEL: str = _yaml_field("VECTOR_STORE_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    VS_EMBEDDING_DIMENSION: int = _yaml_field("VECTOR_STORE_EMBEDDING_DIMENSION", 384)
    VS_CHUNK_SIZE: int = _yaml_field("VECTOR_STORE_CHUNK_SIZE", 3000)

    # Context Management
    MAX_CONTEXT_TOKENS: int = _yaml_field("CONTEXT_MAX_TOKENS", 100_000)
    ENABLE_SUMMARIZATION: bool = _yaml_field("CONTEXT_ENABLE_SUMMARIZATION", True)
    SUMMARY_THRESHOLD: int = _yaml_field("CONTEXT_SUMMARY_THRESHOLD", 20)

    # Agent Configuration
    AGENT_NAME: str = _yaml_field("AGENT_NAME", "Cassey")
    MAX_ITERATIONS: int = _yaml_field("AGENT_MAX_ITERATIONS", 20)

    # Memory (Embedded User Memories)
    MEM_AUTO_EXTRACT: bool = _yaml_field("MEMORY_AUTO_EXTRACT", False)
    MEM_CONFIDENCE_MIN: float = _yaml_field("MEMORY_CONFIDENCE_MIN", 0.6)
    MEM_MAX_PER_TURN: int = _yaml_field("MEMORY_MAX_PER_TURN", 3)
    MEM_EXTRACT_MODEL: str = _yaml_field("MEMORY_EXTRACT_MODEL", "fast")
    MEM_EXTRACT_PROVIDER: Literal["anthropic", "openai", "zhipu", "ollama"] | None = _yaml_field("MEMORY_EXTRACT_PROVIDER", None)
    MEM_EXTRACT_TEMPERATURE: float = _yaml_field("MEMORY_EXTRACT_TEMPERATURE", 0.0)

    @field_validator("MEM_EXTRACT_PROVIDER", mode="before")
    @classmethod
    def empty_string_to_none_extract(cls, v: str | None) -> str | None:
        """Convert empty strings to None for optional provider field."""
        return v or None

    # Web Search (external service - configure in .env)
    SEARXNG_HOST: str | None = None

    # Logging
    LOG_LEVEL: str = _yaml_field("LOGGING_LEVEL", "INFO")
    LOG_FILE: str | None = _yaml_field("LOGGING_FILE", None)

    # Firecrawl (web scraping API - external service, configure in .env)
    FIRECRAWL_API_KEY: str | None = None
    FIRECRAWL_API_URL: str = "https://api.firecrawl.dev"

    # OCR (local text extraction)
    OCR_ENGINE: Literal["paddleocr", "tesseract", "surya"] = _yaml_field("OCR_ENGINE", "paddleocr")
    OCR_LANG: str = _yaml_field("OCR_LANG", "en")
    OCR_USE_GPU: bool = _yaml_field("OCR_USE_GPU", False)
    OCR_MAX_FILE_MB: int = _yaml_field("OCR_MAX_FILE_MB", 10)
    OCR_MAX_PAGES: int = _yaml_field("OCR_MAX_PAGES", 3)
    OCR_PDF_DPI: int = _yaml_field("OCR_PDF_DPI", 200)
    OCR_PDF_MIN_TEXT_CHARS: int = _yaml_field("OCR_PDF_MIN_TEXT_CHARS", 5)
    OCR_TIMEOUT_SECONDS: int = _yaml_field("OCR_TIMEOUT_SECONDS", 30)
    OCR_STRUCTURED_MODEL: str = _yaml_field("OCR_STRUCTURED_MODEL", "fast")
    OCR_STRUCTURED_PROVIDER: Literal["anthropic", "openai", "zhipu", "ollama"] | None = _yaml_field("OCR_STRUCTURED_PROVIDER", None)
    OCR_STRUCTURED_MAX_RETRIES: int = _yaml_field("OCR_STRUCTURED_MAX_RETRIES", 2)

    @field_validator("OCR_STRUCTURED_PROVIDER", mode="before")
    @classmethod
    def empty_string_to_none_ocr(cls, v: str | None) -> str | None:
        """Convert empty strings to None for optional provider field."""
        return v or None

    # ============================================================================
    # Temporal Workflow Configuration (external service - configure in .env)
    # ============================================================================

    TEMPORAL_HOST: str | None = None
    TEMPORAL_PORT: int = 7233
    TEMPORAL_NAMESPACE: str = "default"
    TEMPORAL_TASK_QUEUE: str = "cassey-workflows"
    TEMPORAL_CLIENT_TIMEOUT: int = 30
    TEMPORAL_CONNECTION_RETRY: int = 3
    TEMPORAL_WEB_UI_URL: str = "http://localhost:8080"

    @property
    def temporal_enabled(self) -> bool:
        """Check if Temporal is configured and enabled."""
        return bool(self.TEMPORAL_HOST)

    @property
    def temporal_target(self) -> str:
        """Get the Temporal server target (host:port)."""
        if not self.TEMPORAL_HOST:
            raise ValueError("TEMPORAL_HOST not configured")
        return f"{self.TEMPORAL_HOST}:{self.TEMPORAL_PORT}"

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
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
            ".tiff",
            ".tif",
            ".bmp",
            ".gif",
        }
    )

    @field_validator("ALLOWED_FILE_EXTENSIONS", mode="before")
    @classmethod
    def parse_allowed_extensions(cls, v: str | set[str] | list[str]) -> set[str]:
        """Parse allowed extensions from string (YAML/env) or set."""
        if isinstance(v, set):
            return v
        if isinstance(v, list):
            return set(v)
        if isinstance(v, str):
            return {ext.strip() for ext in v.split(",") if ext.strip()}
        return {
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
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
            ".tiff",
            ".tif",
            ".bmp",
            ".gif",
        }

    @field_validator("USERS_ROOT", mode="before")
    @classmethod
    def resolve_users_root(cls, v: str | Path) -> Path:
        """Resolve users root to absolute path."""
        return Path(v).resolve()

    @field_validator("SHARED_ROOT", mode="before")
    @classmethod
    def resolve_shared_root(cls, v: str | Path) -> Path:
        """Resolve shared root to absolute path."""
        return Path(v).resolve()

    @field_validator("GROUPS_ROOT", "WORKSPACES_ROOT", mode="before")
    @classmethod
    def resolve_groups_root(cls, v: str | Path) -> Path:
        """Resolve groups root to absolute path."""
        return Path(v).resolve()

    # ============================================================================
    # ID Sanitization
    # ============================================================================

    def _sanitize_id(self, id_str: str) -> str:
        """Sanitize an ID (user_id, group_id, etc.) for use as directory name."""
        replacements = {":": "_", "/": "_", "@": "_", "\\": "_"}
        for old, new in replacements.items():
            id_str = id_str.replace(old, new)
        return id_str

    # Legacy aliases
    def _sanitize_thread_id(self, thread_id: str) -> str:
        """Sanitize thread_id for use as directory name. (Legacy alias)"""
        return self._sanitize_id(thread_id)

    def _sanitize_workspace_id(self, workspace_id: str) -> str:
        """Sanitize workspace_id for use as directory name. (Legacy alias)"""
        return self._sanitize_id(workspace_id)

    def _sanitize_group_id(self, group_id: str) -> str:
        """Sanitize group_id for use as directory name."""
        return self._sanitize_id(group_id)

    # ============================================================================
    # User-level paths (Level 3: Personal data, user only)
    # ============================================================================

    def get_user_root(self, user_id: str) -> Path:
        """
        Get the root directory for a specific user.

        Returns: data/users/{user_id}/
        """
        safe_id = self._sanitize_id(user_id)
        user_path = (self.USERS_ROOT / safe_id).resolve()
        user_path.mkdir(parents=True, exist_ok=True)
        return user_path

    def get_user_files_path(self, user_id: str) -> Path:
        """
        Get files directory for a user.

        Returns: data/users/{user_id}/files/
        """
        return self.get_user_root(user_id) / "files"

    def get_user_db_path(self, user_id: str, database: str = "default") -> Path:
        """
        Get database file path for a user.

        Returns: data/users/{user_id}/db/{database}.sqlite
        """
        db_path = self.get_user_root(user_id) / "db"
        db_path.mkdir(parents=True, exist_ok=True)
        return db_path / f"{database}.sqlite"

    def get_user_mem_path(self, user_id: str) -> Path:
        """
        Get memory (mem.db) file path for a user.

        Returns: data/users/{user_id}/mem/mem.db
        """
        mem_path = self.get_user_root(user_id) / "mem"
        mem_path.mkdir(parents=True, exist_ok=True)
        return mem_path / "mem.db"

    def get_user_reminders_path(self, user_id: str) -> Path:
        """
        Get reminders directory for a user.

        Returns: data/users/{user_id}/reminders/
        """
        return self.get_user_root(user_id) / "reminders"

    # ============================================================================
    # Group-level paths (Level 2: Collaborative, group members)
    # ============================================================================

    def get_group_root(self, group_id: str) -> Path:
        """
        Get the root directory for a specific group.

        Returns: data/groups/{group_id}/
        """
        safe_id = self._sanitize_group_id(group_id)
        group_path = (self.GROUPS_ROOT / safe_id).resolve()
        group_path.mkdir(parents=True, exist_ok=True)
        return group_path

    def get_group_files_path(self, group_id: str) -> Path:
        """
        Get files directory for a group.

        Returns: data/groups/{group_id}/files/
        """
        return self.get_group_root(group_id) / "files"

    def get_group_vs_path(self, group_id: str) -> Path:
        """
        Get vector store directory for a group.

        Returns: data/groups/{group_id}/vs/
        """
        return self.get_group_root(group_id) / "vs"

    def get_group_db_path(self, group_id: str, database: str = "default") -> Path:
        """
        Get database file path for a group.

        Returns: data/groups/{group_id}/db/{database}.sqlite
        """
        db_path = self.get_group_root(group_id) / "db"
        db_path.mkdir(parents=True, exist_ok=True)
        return db_path / f"{database}.sqlite"

    def get_group_mem_path(self, group_id: str) -> Path:
        """
        Get memory (mem.db) file path for a group.

        Returns: data/groups/{group_id}/mem/mem.db
        """
        mem_path = self.get_group_root(group_id) / "mem"
        mem_path.mkdir(parents=True, exist_ok=True)
        return mem_path / "mem.db"

    def get_group_reminders_path(self, group_id: str) -> Path:
        """
        Get reminders directory for a group.

        Returns: data/groups/{group_id}/reminders/
        """
        return self.get_group_root(group_id) / "reminders"

    def get_group_workflows_path(self, group_id: str) -> Path:
        """
        Get workflows directory for a group.

        Returns: data/groups/{group_id}/workflows/
        """
        return self.get_group_root(group_id) / "workflows"

    # ============================================================================
    # Deprecated workspace aliases (for backward compatibility)
    # ============================================================================

    def get_workspace_root(self, workspace_id: str) -> Path:
        """
        Get the root directory for a specific workspace. (DEPRECATED - use get_group_root)

        Returns: data/groups/{workspace_id}/
        """
        return self.get_group_root(workspace_id)

    def get_workspace_files_path(self, workspace_id: str) -> Path:
        """Get files directory for a workspace. (DEPRECATED - use get_group_files_path)"""
        return self.get_group_files_path(workspace_id)

    def get_workspace_vs_path(self, workspace_id: str) -> Path:
        """Get vector store directory for a workspace. (DEPRECATED - use get_group_vs_path)"""
        return self.get_group_vs_path(workspace_id)

    def get_workspace_db_path(self, workspace_id: str) -> Path:
        """Get database file path for a workspace. (DEPRECATED - use get_group_db_path)"""
        return self.get_group_db_path(workspace_id)

    def get_workspace_mem_path(self, workspace_id: str) -> Path:
        """Get memory file path for a workspace. (DEPRECATED - use get_group_mem_path)"""
        return self.get_group_mem_path(workspace_id)

    def get_workspace_reminders_path(self, workspace_id: str) -> Path:
        """Get reminders directory for a workspace. (DEPRECATED - use get_group_reminders_path)"""
        return self.get_group_reminders_path(workspace_id)

    def get_workspace_workflows_path(self, workspace_id: str) -> Path:
        """Get workflows directory for a workspace. (DEPRECATED - use get_group_workflows_path)"""
        return self.get_group_workflows_path(workspace_id)

    # ============================================================================
    # Thread-based paths (legacy, transitional - kept for backward compatibility)
    # ============================================================================

    def get_thread_root(self, thread_id: str) -> Path:
        """
        Get the root directory for a specific thread (legacy).

        Note: Threads map to groups in the new model. This method exists for
        backward compatibility during transition.

        Returns: data/users/{thread_id}/
        """
        safe_thread_id = self._sanitize_id(thread_id)
        return (self.USERS_ROOT / safe_thread_id).resolve()

    def get_thread_files_path(self, thread_id: str) -> Path:
        """
        Get files directory for a thread (legacy).

        Returns: data/users/{thread_id}/files/
        """
        safe_thread_id = self._sanitize_id(thread_id)
        new_path = (self.USERS_ROOT / safe_thread_id / "files").resolve()
        new_path.mkdir(parents=True, exist_ok=True)
        return new_path

    def get_thread_db_path(self, thread_id: str) -> Path:
        """
        Get database file path for a thread (legacy).

        Returns: data/users/{thread_id}/db/db.sqlite
        """
        safe_thread_id = self._sanitize_id(thread_id)
        new_path = (self.USERS_ROOT / safe_thread_id / "db" / "db.sqlite").resolve()
        new_path.parent.mkdir(parents=True, exist_ok=True)
        return new_path

    def get_thread_mem_path(self, thread_id: str) -> Path:
        """
        Get memory (mem.db) file path for a thread (legacy).

        Returns: data/users/{thread_id}/mem/mem.db
        With fallback to: data/mem/{thread_id}.db (if exists)
        """
        safe_thread_id = self._sanitize_id(thread_id)
        new_path = (self.USERS_ROOT / safe_thread_id / "mem" / "mem.db").resolve()

        # Backward compatibility: use old path if new path doesn't exist
        if not new_path.exists():
            old_path = (Path("./data/mem") / f"{safe_thread_id}.db").resolve()
            if old_path.exists():
                return old_path

        new_path.parent.mkdir(parents=True, exist_ok=True)
        return new_path

    def is_new_storage_layout(self, thread_id: str) -> bool:
        """
        Check if a thread is using the new storage layout.

        Returns True if data/users/{thread_id}/ exists, False otherwise.
        """
        new_path = self.get_thread_root(thread_id)
        return new_path.exists()

    # ============================================================================
    # Context-Aware Routing (group_id first, then thread_id)
    # ============================================================================

    def get_context_files_path(self) -> Path:
        """
        Get files directory for the current context.

        Priority:
        1. group_id from context (new group-based routing) -> data/groups/{group_id}/files/
        2. thread_id from context (legacy thread-based routing) -> data/users/{thread_id}/files/

        Returns:
            Path to the files directory for current context.

        Raises:
            ValueError: If no group_id or thread_id context is available.
        """
        from cassey.storage.group_storage import get_workspace_id
        from cassey.storage.file_sandbox import get_thread_id

        # Check group_id first (new group-based routing)
        group_id = get_workspace_id()
        if group_id:
            return self.get_group_files_path(group_id)

        # Fall back to thread_id (legacy thread-based routing)
        thread_id = get_thread_id()
        if thread_id:
            return self.get_thread_files_path(thread_id)

        raise ValueError(
            "No group_id or thread_id context available for file operations"
        )

    def get_context_db_path(self, database: str = "default") -> Path:
        """
        Get database file path for the current context.

        Priority:
        1. group_id from context -> data/groups/{group_id}/db/{database}.sqlite
        2. thread_id from context -> data/users/{thread_id}/db/db.sqlite

        Returns:
            Path to the database file for current context.

        Raises:
            ValueError: If no group_id or thread_id context is available.
        """
        from cassey.storage.group_storage import get_workspace_id
        from cassey.storage.file_sandbox import get_thread_id

        # Check group_id first (new group-based routing)
        group_id = get_workspace_id()
        if group_id:
            return self.get_group_db_path(group_id, database)

        # Fall back to thread_id (legacy thread-based routing)
        thread_id = get_thread_id()
        if thread_id:
            return self.get_thread_db_path(thread_id)

        raise ValueError(
            "No group_id or thread_id context available for database operations"
        )

    # ============================================================================
    # Shared paths (Level 0: Organization-wide)
    # ============================================================================

    def get_shared_files_path(self) -> Path:
        """
        Get shared files directory for organization-wide file storage.

        Returns: data/shared/files/
        """
        shared_path = self.SHARED_ROOT / "files"
        shared_path.mkdir(parents=True, exist_ok=True)
        return shared_path

    def get_shared_db_path(self, database: str = "shared") -> Path:
        """
        Get shared database file path for organization-wide database.

        Returns: data/shared/db/{database}.sqlite
        """
        db_path = self.SHARED_ROOT / "db"
        db_path.mkdir(parents=True, exist_ok=True)
        return db_path / f"{database}.sqlite"

    # Legacy file path method
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
