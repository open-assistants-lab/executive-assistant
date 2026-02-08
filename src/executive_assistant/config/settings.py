"""Application settings with YAML defaults and .env overrides."""

import logging
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from executive_assistant.config.loader import get_yaml_defaults

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
        env_file=("docker/.env", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ============================================================================
    # LLM Configuration
    # ============================================================================

    DEFAULT_LLM_PROVIDER: Literal[
        "anthropic", "openai", "zhipu", "ollama", "deepseek", "gemini", "qwen", "kimi", "minimax"
    ] = _yaml_field("LLM_DEFAULT_PROVIDER", "anthropic")

    # Global Model Overrides (apply to all providers)
    DEFAULT_LLM_MODEL: str | None = _yaml_field("LLM_DEFAULT_MODEL", None)
    FAST_LLM_MODEL: str | None = _yaml_field("LLM_FAST_MODEL", None)

    # Provider-Specific Model Overrides (higher priority)
    ANTHROPIC_DEFAULT_MODEL: str | None = _yaml_field(
        "LLM_ANTHROPIC_DEFAULT_MODEL", None
    )
    ANTHROPIC_FAST_MODEL: str | None = _yaml_field("LLM_ANTHROPIC_FAST_MODEL", None)
    OPENAI_DEFAULT_MODEL: str | None = _yaml_field("LLM_OPENAI_DEFAULT_MODEL", None)
    OPENAI_FAST_MODEL: str | None = _yaml_field("LLM_OPENAI_FAST_MODEL", None)
    ZHIPU_DEFAULT_MODEL: str | None = _yaml_field("LLM_ZHIPU_DEFAULT_MODEL", None)
    ZHIPU_FAST_MODEL: str | None = _yaml_field("LLM_ZHIPU_FAST_MODEL", None)
    DEEPSEEK_DEFAULT_MODEL: str | None = _yaml_field(
        "LLM_DEEPSEEK_DEFAULT_MODEL", "deepseek-reasoner"
    )
    DEEPSEEK_FAST_MODEL: str | None = _yaml_field(
        "LLM_DEEPSEEK_FAST_MODEL", "deepseek-chat"
    )
    OLLAMA_DEFAULT_MODEL: str | None = _yaml_field("LLM_OLLAMA_DEFAULT_MODEL", None)
    OLLAMA_FAST_MODEL: str | None = _yaml_field("LLM_OLLAMA_FAST_MODEL", None)
    GEMINI_DEFAULT_MODEL: str | None = _yaml_field("LLM_GEMINI_DEFAULT_MODEL", None)
    GEMINI_FAST_MODEL: str | None = _yaml_field("LLM_GEMINI_FAST_MODEL", None)
    QWEN_DEFAULT_MODEL: str | None = _yaml_field("LLM_QWEN_DEFAULT_MODEL", None)
    QWEN_FAST_MODEL: str | None = _yaml_field("LLM_QWEN_FAST_MODEL", None)
    KIMI_DEFAULT_MODEL: str | None = _yaml_field("LLM_KIMI_DEFAULT_MODEL", None)
    KIMI_FAST_MODEL: str | None = _yaml_field("LLM_KIMI_FAST_MODEL", None)
    MINIMAX_DEFAULT_MODEL: str | None = _yaml_field("LLM_MINIMAX_DEFAULT_MODEL", None)
    MINIMAX_FAST_MODEL: str | None = _yaml_field("LLM_MINIMAX_FAST_MODEL", None)

    # API Keys (secrets - must be in .env)
    ANTHROPIC_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None
    ZHIPUAI_API_KEY: str | None = None
    DEEPSEEK_API_KEY: str | None = None  # For DeepSeek (official API or Ollama Cloud)

    # New LLM Provider API Keys
    GOOGLE_API_KEY: str | None = None  # For Gemini
    GEMINI_API_KEY: str | None = None  # Alternative to GOOGLE_API_KEY
    DASHSCOPE_API_KEY: str | None = None  # For Qwen (Alibaba)
    MOONSHOT_API_KEY: str | None = None  # For Kimi K2
    MINIMAX_API_KEY: str | None = None  # For MiniMax

    # ============================================================================
    # Ollama Configuration
    # ============================================================================

    OLLAMA_MODE: Literal["cloud", "local"] = _yaml_field("LLM_OLLAMA_MODE", "cloud")

    # Cloud Mode
    OLLAMA_CLOUD_API_KEY: str | None = None  # Secret
    OLLAMA_CLOUD_URL: str = _yaml_field("LLM_OLLAMA_CLOUD_URL", "https://ollama.com")

    # Local Mode
    OLLAMA_LOCAL_URL: str = _yaml_field(
        "LLM_OLLAMA_LOCAL_URL", "http://localhost:11434"
    )

    # Backward compatibility (deprecated, maps to CLOUD_API_KEY)
    OLLAMA_API_KEY: str | None = None

    @model_validator(mode="after")
    @classmethod
    def map_ollama_api_key_to_cloud(cls, settings_obj: "Settings") -> "Settings":
        """Map legacy OLLAMA_API_KEY to OLLAMA_CLOUD_API_KEY."""
        if not settings_obj.OLLAMA_CLOUD_API_KEY and settings_obj.OLLAMA_API_KEY:
            settings_obj.OLLAMA_CLOUD_API_KEY = settings_obj.OLLAMA_API_KEY
        return settings_obj

    # ============================================================================
    # DeepSeek Configuration
    # ============================================================================

    # DeepSeek API base URL (defaults to official API)
    # Set to Ollama Cloud URL (e.g., "https://ollama.com") to use Ollama as backend
    DEEPSEEK_API_BASE: str = _yaml_field("LLM_DEEPSEEK_API_BASE", "https://api.deepseek.com")

    # ============================================================================
    # Gemini Configuration
    # ============================================================================

    # Vertex AI backend (optional, defaults to Gemini API)
    GOOGLE_GENAI_USE_VERTEXAI: bool = False
    GOOGLE_CLOUD_PROJECT: str | None = None
    GOOGLE_CLOUD_LOCATION: str = "us-central1"

    # ============================================================================
    # Kimi Configuration
    # ============================================================================

    MOONSHOT_API_BASE: str = "https://api.moonshot.ai/v1"

    # ============================================================================
    # MiniMax Configuration
    # ============================================================================

    MINIMAX_API_TYPE: Literal["openai", "anthropic"] = "openai"
    MINIMAX_API_BASE: str = "https://api.minimax.io/v1"

    # ============================================================================
    # Google Workspace Integration
    # ============================================================================

    # OAuth2 Configuration (for Gmail, Calendar, Contacts)
    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: str | None = None
    GOOGLE_REDIRECT_URI: str | None = None

    # Token encryption (required for production, generate with: Fernet.generate_key())
    EMAIL_ENCRYPTION_KEY: str | None = None

    # Telegram Configuration
    TELEGRAM_BOT_TOKEN: str | None = None  # Secret
    TELEGRAM_WEBHOOK_URL: str | None = None
    TELEGRAM_WEBHOOK_SECRET: str | None = None  # Secret

    # Storage Configuration
    CHECKPOINT_STORAGE: Literal["postgres", "memory"] = _yaml_field(
        "STORAGE_CHECKPOINT", "postgres"
    )

    # PostgreSQL Configuration
    POSTGRES_HOST: str = _yaml_field("STORAGE_POSTGRES_HOST", "localhost")
    POSTGRES_PORT: int = _yaml_field("STORAGE_POSTGRES_PORT", 5432)
    POSTGRES_USER: str = _yaml_field("STORAGE_POSTGRES_USER", "executive_assistant")
    POSTGRES_PASSWORD: str = "executive_assistant_password"  # Secret - override in .env
    POSTGRES_DB: str = _yaml_field("STORAGE_POSTGRES_DB", "executive_assistant_db")

    # Security / File Sandbox
    MAX_FILE_SIZE_MB: int = _yaml_field("STORAGE_MAX_FILE_SIZE_MB", 10)
    ALLOWED_FILE_EXTENSIONS: set[str] = _yaml_field(
        "STORAGE_ALLOWED_FILE_EXTENSIONS",
        {
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
        },
    )

    # ============================================================================
    # Storage Paths
    # ============================================================================

    # 2-level storage hierarchy
    # Level 1: Org-wide (admin write, everyone read)
    SHARED_ROOT: Path = _yaml_field("STORAGE_PATHS_SHARED_ROOT", Path("./data/shared"))

    # Level 2: Thread/user storage (per-thread, no groups)
    USERS_ROOT: Path = _yaml_field("STORAGE_PATHS_USERS_ROOT", Path("./data/users"))

    # Admin storage (admins, allowlist, prompts, MCP config)
    ADMINS_ROOT: Path = _yaml_field("STORAGE_PATHS_ADMINS_ROOT", Path("./data/admins"))

    # Admin access control (stored as comma-separated strings for env compatibility)
    ADMIN_USER_IDS_RAW: str = _yaml_field("ADMIN_USER_IDS", "", alias="ADMIN_USER_IDS")
    ADMIN_THREAD_IDS_RAW: str = _yaml_field(
        "ADMIN_THREAD_IDS", "", alias="ADMIN_THREAD_IDS"
    )

    ADMIN_THREAD_IDS: list[str] = []

    @field_validator("ADMIN_THREAD_IDS", mode="before")
    @classmethod
    def _parse_admin_thread_ids(cls, v, info):
        raw = info.data.get("ADMIN_THREAD_IDS_RAW") if info and hasattr(info, "data") else None
        if v:
            return v
        if raw is None:
            return []
        if isinstance(raw, list):
            return raw
        if isinstance(raw, str):
            return [item.strip() for item in raw.split(",") if item.strip()]
        return []

    # LangChain Middleware (agent runtime)
    MW_SUMMARIZATION_ENABLED: bool = _yaml_field(
        "MIDDLEWARE_SUMMARIZATION_ENABLED", True
    )
    # NOTE: LangChain SummarizationMiddleware has dual trigger behavior:
    # 1. Counts message tokens via token_counter
    # 2. Checks AIMessage.usage_metadata.total_tokens (includes system + tools overhead)
    #
    # Trigger #2 fires early due to overhead:
    # - System prompt: ~1,200 tokens
    # - 72 tool definitions: ~4,500-5,000 tokens
    # - Total overhead: ~5,700 tokens
    #
    # With max_tokens=10,000: Effective message trigger = 10,000 - 5,700 = ~4,300 tokens
    # With target_tokens=2,000: Preserves ~15-20 recent messages after summarization (5:1 ratio)
    #
    # [SCOPE: Total LLM request size] Triggers when last request hit this token count
    MW_SUMMARIZATION_MAX_TOKENS: int = _yaml_field(
        "MIDDLEWARE_SUMMARIZATION_MAX_TOKENS", 10_000
    )
    # [SCOPE: Message buffer size AFTER summarization] Preserves most recent ~2,000 tokens
    MW_SUMMARIZATION_TARGET_TOKENS: int = _yaml_field(
        "MIDDLEWARE_SUMMARIZATION_TARGET_TOKENS", 2_000  # Increased to 5:1 ratio for better context retention
    )
    MW_DEBUG_SUMMARIZATION: bool = _yaml_field(
        "MIDDLEWARE_DEBUG_SUMMARIZATION", False
    )
    MW_DEBUG_CONTEXT_EDITING: bool = _yaml_field(
        "MIDDLEWARE_DEBUG_CONTEXT_EDITING", False
    )
    MW_MODEL_CALL_LIMIT: int = _yaml_field("MIDDLEWARE_MODEL_CALL_LIMIT", 50)
    MW_TOOL_CALL_LIMIT: int = _yaml_field("MIDDLEWARE_TOOL_CALL_LIMIT", 100)
    MW_TOOL_RETRY_ENABLED: bool = _yaml_field("MIDDLEWARE_TOOL_RETRY_ENABLED", True)
    MW_MODEL_RETRY_ENABLED: bool = _yaml_field("MIDDLEWARE_MODEL_RETRY_ENABLED", True)
    MW_TODO_LIST_ENABLED: bool = _yaml_field("MIDDLEWARE_TODO_LIST_ENABLED", True)
    MW_CONTEXT_EDITING_ENABLED: bool = _yaml_field(
        "MIDDLEWARE_CONTEXT_EDITING_ENABLED", True
    )
    MW_CONTEXT_EDITING_TRIGGER_TOKENS: int = _yaml_field(
        "MIDDLEWARE_CONTEXT_EDITING_TRIGGER_TOKENS", 100_000
    )
    MW_CONTEXT_EDITING_KEEP_TOOL_USES: int = _yaml_field(
        "MIDDLEWARE_CONTEXT_EDITING_KEEP_TOOL_USES", 10
    )
    MW_STATUS_UPDATE_ENABLED: bool = _yaml_field(
        "MIDDLEWARE_STATUS_UPDATES_ENABLED", True
    )
    MW_STATUS_SHOW_TOOL_ARGS: bool = _yaml_field(
        "MIDDLEWARE_STATUS_UPDATES_SHOW_TOOL_ARGS", False
    )
    MW_STATUS_UPDATE_INTERVAL: float = _yaml_field(
        "MIDDLEWARE_STATUS_UPDATES_UPDATE_INTERVAL", 0.5
    )

    # Todo List Display
    MW_TODO_LIST_MAX_DISPLAY: int = _yaml_field("MIDDLEWARE_TODO_LIST_MAX_DISPLAY", 10)
    MW_TODO_LIST_UPDATE_INTERVAL: float = _yaml_field(
        "MIDDLEWARE_TODO_LIST_UPDATE_INTERVAL", 0.5
    )
    MW_TODO_LIST_SHOW_PROGRESS_BAR: bool = _yaml_field(
        "MIDDLEWARE_TODO_LIST_SHOW_PROGRESS_BAR", False
    )

    # Vector Database (LanceDB)
    VDB_EMBEDDING_MODEL: str = _yaml_field(
        "VECTOR_DATABASE_EMBEDDING_MODEL", "all-MiniLM-L6-v2"
    )
    VDB_EMBEDDING_DIMENSION: int = _yaml_field(
        "VECTOR_DATABASE_EMBEDDING_DIMENSION", 384
    )
    VDB_CHUNK_SIZE: int = _yaml_field("VECTOR_DATABASE_CHUNK_SIZE", 3000)

    # Context Management
    MAX_CONTEXT_TOKENS: int = _yaml_field("CONTEXT_MAX_TOKENS", 100_000)
    ENABLE_SUMMARIZATION: bool = _yaml_field("CONTEXT_ENABLE_SUMMARIZATION", True)
    SUMMARY_THRESHOLD: int = _yaml_field("CONTEXT_SUMMARY_THRESHOLD", 20)

    # Agent Configuration
    AGENT_NAME: str = _yaml_field("AGENT_NAME", "Executive Assistant")

    # Memory (Embedded User Memories)
    MEM_AUTO_EXTRACT: bool = _yaml_field("MEMORY_AUTO_EXTRACT", True)
    MEM_CONFIDENCE_MIN: float = _yaml_field("MEMORY_CONFIDENCE_MIN", 0.6)
    MEM_MAX_PER_TURN: int = _yaml_field("MEMORY_MAX_PER_TURN", 3)
    MEM_EXTRACT_MODEL: str = _yaml_field("MEMORY_EXTRACT_MODEL", "fast")
    MEM_EXTRACT_PROVIDER: Literal[
        "anthropic", "openai", "zhipu", "ollama", "gemini", "qwen", "kimi", "minimax"
    ] | None = _yaml_field("MEMORY_EXTRACT_PROVIDER", None)
    MEM_EXTRACT_TEMPERATURE: float = _yaml_field("MEMORY_EXTRACT_TEMPERATURE", 0.0)

    @field_validator("MEM_EXTRACT_PROVIDER", mode="before")
    @classmethod
    def empty_string_to_none_extract(cls, v: str | None) -> str | None:
        """Convert empty strings to None for optional provider field."""
        return v or None

    # Journal (Time-Based Activity Tracking with Rollups)
    JOURNAL_RETENTION_HOURLY: int = _yaml_field("JOURNAL_RETENTION_HOURLY", 30)
    JOURNAL_RETENTION_WEEKLY: int = _yaml_field("JOURNAL_RETENTION_WEEKLY", 52)
    JOURNAL_RETENTION_MONTHLY: int = _yaml_field("JOURNAL_RETENTION_MONTHLY", 84)  # 7 years
    JOURNAL_RETENTION_YEARLY: int = _yaml_field("JOURNAL_RETENTION_YEARLY", 7)
    JOURNAL_AUTO_ROLLUP_ENABLED: bool = _yaml_field("JOURNAL_AUTO_ROLLUP_ENABLED", False)

    # Web Search (uses Firecrawl - external service, configure in .env)
    # Firecrawl API also used for scrape/crawl tools

    # Logging
    LOG_LEVEL: str = _yaml_field("LOGGING_LEVEL", "INFO")
    LOG_FILE: str | None = _yaml_field("LOGGING_FILE", None)

    # Firecrawl (web scraping API - external service, configure in .env)
    FIRECRAWL_API_KEY: str | None = None
    FIRECRAWL_API_URL: str = "https://api.firecrawl.dev"

    # OCR (local text extraction)
    OCR_ENGINE: Literal["paddleocr", "tesseract", "surya"] = _yaml_field(
        "OCR_ENGINE", "paddleocr"
    )
    OCR_LANG: str = _yaml_field("OCR_LANG", "en")
    OCR_USE_GPU: bool = _yaml_field("OCR_USE_GPU", False)
    OCR_MAX_FILE_MB: int = _yaml_field("OCR_MAX_FILE_MB", 10)
    OCR_MAX_PAGES: int = _yaml_field("OCR_MAX_PAGES", 3)
    OCR_PDF_DPI: int = _yaml_field("OCR_PDF_DPI", 200)
    OCR_PDF_MIN_TEXT_CHARS: int = _yaml_field("OCR_PDF_MIN_TEXT_CHARS", 5)
    OCR_TIMEOUT_SECONDS: int = _yaml_field("OCR_TIMEOUT_SECONDS", 30)
    OCR_STRUCTURED_MODEL: str = _yaml_field("OCR_STRUCTURED_MODEL", "fast")
    OCR_STRUCTURED_PROVIDER: (
        Literal[
            "anthropic",
            "openai",
            "zhipu",
            "ollama",
            "gemini",
            "qwen",
            "kimi",
            "minimax",
        ]
        | None
    ) = _yaml_field("OCR_STRUCTURED_PROVIDER", None)
    OCR_STRUCTURED_MAX_RETRIES: int = _yaml_field("OCR_STRUCTURED_MAX_RETRIES", 2)

    @field_validator("OCR_STRUCTURED_PROVIDER", mode="before")
    @classmethod
    def empty_string_to_none_ocr(cls, v: str | None) -> str | None:
        """Convert empty strings to None for optional provider field."""
        return v or None

    # ============================================================================
    # Temporal Workflow Configuration (external service - configure in .env)
    # ============================================================================

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

    # ============================================================================
    # ID Sanitization
    # ============================================================================

    def _sanitize_id(self, id_str: str) -> str:
        """Sanitize an ID for use as directory name."""
        replacements = {"\\": "_", "/": "_", "@": "_", ":": "_"}
        for old, new in replacements.items():
            id_str = id_str.replace(old, new)
        return id_str

    def _sanitize_thread_id(self, thread_id: str) -> str:
        """Sanitize thread_id for use as directory name."""
        return self._sanitize_id(thread_id)

    # ============================================================================
    # Thread-level paths (per-thread storage)
    # ============================================================================

    def get_thread_root(self, thread_id: str) -> Path:
        """
        Get the root directory for a specific thread.

        Returns: data/users/{thread_id}/
        """
        safe_thread_id = self._sanitize_id(thread_id)
        thread_path = (self.USERS_ROOT / safe_thread_id).resolve()
        thread_path.mkdir(parents=True, exist_ok=True)
        return thread_path

    def get_thread_files_path(self, thread_id: str) -> Path:
        """
        Get files directory for a thread.

        Returns: data/users/{thread_id}/files/
        """
        files_path = self.get_thread_root(thread_id) / "files"
        files_path.mkdir(parents=True, exist_ok=True)
        return files_path

    def get_thread_vdb_path(self, thread_id: str) -> Path:
        """
        Get vector database directory for a thread.

        Returns: data/users/{thread_id}/vdb/
        """
        vdb_path = self.get_thread_root(thread_id) / "vdb"
        vdb_path.mkdir(parents=True, exist_ok=True)
        return vdb_path

    def get_thread_tdb_path(self, thread_id: str, database: str = "default") -> Path:
        """
        Get transactional database file path for a thread.

        Returns: data/users/{thread_id}/tdb/{database}.sqlite
        """
        tdb_path = self.get_thread_root(thread_id) / "tdb"
        tdb_path.mkdir(parents=True, exist_ok=True)
        return tdb_path / f"{database}.sqlite"

    def get_thread_mem_path(self, thread_id: str) -> Path:
        """
        Get memory (mem.db) file path for a thread.

        Returns: data/users/{thread_id}/mem/mem.db
        """
        mem_path = self.get_thread_root(thread_id) / "mem"
        mem_path.mkdir(parents=True, exist_ok=True)
        return mem_path / "mem.db"

    def get_thread_reminders_path(self, thread_id: str) -> Path:
        """
        Get reminders directory for a thread.

        Returns: data/users/{thread_id}/reminders/
        """
        reminders_path = self.get_thread_root(thread_id) / "reminders"
        reminders_path.mkdir(parents=True, exist_ok=True)
        return reminders_path

    def get_thread_instincts_dir(self, thread_id: str) -> Path:
        """
        Get instincts directory for a thread.

        Returns: data/users/{thread_id}/instincts/
        """
        instincts_dir = self.get_thread_root(thread_id) / "instincts"
        instincts_dir.mkdir(parents=True, exist_ok=True)
        return instincts_dir

    def get_thread_mcp_dir(self, thread_id: str) -> Path:
        """
        Get MCP directory for a thread.

        Returns: data/users/{thread_id}/mcp/

        This directory contains user-specific MCP server configurations:
        - mcp.json: Local (stdio) MCP servers
        - mcp_remote.json: Remote (HTTP/SSE) MCP servers
        """
        mcp_dir = self.get_thread_root(thread_id) / "mcp"
        mcp_dir.mkdir(parents=True, exist_ok=True)
        return mcp_dir

    # ============================================================================
    # Context-Aware Routing (thread_id only)
    # ============================================================================

    def get_context_files_path(self) -> Path:
        """
        Get files directory for the current context.

        Uses thread_id from context.
        """
        from executive_assistant.storage.thread_storage import get_thread_id

        thread_id = get_thread_id()
        if thread_id:
            return self.get_thread_files_path(thread_id)

        raise ValueError("No thread_id context available for file operations")

    def get_context_db_path(self, database: str = "default") -> Path:
        """
        Get database file path for the current context.

        Uses thread_id from context.
        """
        from executive_assistant.storage.thread_storage import get_thread_id

        thread_id = get_thread_id()
        if thread_id:
            return self.get_thread_tdb_path(thread_id, database)

        raise ValueError("No thread_id context available for database operations")

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

    def get_shared_tdb_path(self, database: str = "shared") -> Path:
        """
        Get shared TDB file path for organization-wide database.

        Returns: data/shared/tdb/{database}.sqlite
        """
        tdb_path = self.SHARED_ROOT / "tdb"
        tdb_path.mkdir(parents=True, exist_ok=True)
        return tdb_path / f"{database}.sqlite"

    # Legacy file path method
    @property
    def POSTGRES_URL(self) -> str:
        """Construct PostgreSQL connection URL from individual components."""
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


def get_thread_mcp_dir() -> Path:
    """Convenience function to get MCP directory for a thread.

    Uses thread_id from context if available.

    Returns: data/users/{thread_id}/mcp/
    """
    from executive_assistant.storage.file_sandbox import get_thread_id

    thread_id = get_thread_id()
    if not thread_id:
        raise RuntimeError("No thread_id in context")

    return get_settings().get_thread_mcp_dir(thread_id)


# Singleton instance
settings = get_settings()
