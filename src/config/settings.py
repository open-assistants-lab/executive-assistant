"""Settings module for Executive Assistant."""

from pathlib import Path

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings


class _BaseSettings(BaseSettings):
    """Base settings with common config."""

    class Config:
        extra = "ignore"


class AgentConfig(_BaseSettings):
    """Agent configuration."""

    name: str = Field(default="Executive Assistant")
    model: str = Field(default="ollama:minimax-m2.5")

    class Config:
        env_prefix = "AGENT_"


class DatabaseConfig(_BaseSettings):
    """Database configuration."""

    host: str = Field(default="localhost")
    port: int = Field(default=5432)
    name: str = Field(default="executive_assistant")
    user: str = Field(default="postgres")
    password: str = Field(default="")
    pool_size: int = Field(default=10)

    @property
    def connection_string(self) -> str:
        """Generate asyncpg connection string."""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"

    @property
    def sync_connection_string(self) -> str:
        """Generate psycopg2 connection string."""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"

    class Config:
        env_prefix = "DB_"


class CheckpointerConfig(_BaseSettings):
    """Checkpointer configuration."""

    enabled: bool = True
    retention_days: int = 0  # 0 = no checkpoints, -1 = keep forever, N = keep N days

    class Config:
        env_prefix = "CHECKPOINT_"


class MessagesConfig(_BaseSettings):
    """Messages (long-term) configuration using SQLite + FTS5."""

    enabled: bool = True
    path: str = "data/users/{user_id}/.conversation/messages.db"
    vector_path: str = "data/users/{user_id}/.conversation/vectors"

    class Config:
        env_prefix = "MESSAGES_"


class StoreConfig(_BaseSettings):
    """Store configuration for long-term memory."""

    enabled: bool = True

    class Config:
        env_prefix = "STORE_"


class SummarizationConfig(_BaseSettings):
    """Summarization middleware configuration (short-term token reduction)."""

    enabled: bool = True
    trigger_tokens: int = 4000
    keep_messages: int = 20
    model: str = Field(default="ollama:minimax-m2.5")

    class Config:
        env_prefix = "SUMMARY_"


class MemoryConfig(_BaseSettings):
    """Memory configuration."""

    checkpointer: CheckpointerConfig = Field(default_factory=CheckpointerConfig)
    messages: MessagesConfig = Field(default_factory=MessagesConfig)
    store: StoreConfig = Field(default_factory=StoreConfig)
    summarization: SummarizationConfig = Field(default_factory=SummarizationConfig)


class LangfuseConfig(_BaseSettings):
    """Langfuse observability configuration."""

    enabled: bool = False
    public_key: str = ""
    secret_key: str = ""
    host: str = "https://cloud.langfuse.com"
    environment: str = ""  # production, development, staging

    class Config:
        env_prefix = "LANGFUSE_"


class LoggingConfig(_BaseSettings):
    """Logging configuration."""

    enabled: bool = True
    level: str = "info"  # debug, info, warning, error
    json_dir: str = "data/logs"

    class Config:
        env_prefix = "LOGGING_"


class ObservabilityConfig(_BaseSettings):
    """Observability configuration."""

    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    langfuse: LangfuseConfig = Field(default_factory=LangfuseConfig)


class ApiConfig(_BaseSettings):
    """API server configuration."""

    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = False
    workers: int = 1

    class Config:
        env_prefix = "API_"


class CliConfig(_BaseSettings):
    """CLI configuration."""

    history_file: str = "~/.ea_history"
    prompt: str = "> "

    class Config:
        env_prefix = "CLI_"


class ToolsConfig(_BaseSettings):
    """Tools configuration."""

    firecrawl_api_key: str = ""
    max_retries: int = 3
    timeout: int = 30

    class Config:
        env_prefix = "TOOLS_"


class SkillsConfig(_BaseSettings):
    """Skills configuration."""

    directory: str = "src/skills"

    def get_user_directory(self, user_id: str) -> str:
        """Get user-specific skills directory."""
        return f"data/users/{user_id}/skills"

    class Config:
        env_prefix = "SKILLS_"


class FilesystemConfig(_BaseSettings):
    """Filesystem tools configuration."""

    enabled: bool = True
    root_path: str = "data/users/{user_id}/files"
    max_file_size_mb: int = 10

    class Config:
        env_prefix = "FILESYSTEM_"
        extra = "ignore"


class ShellToolConfig(_BaseSettings):
    """Shell tool configuration."""

    enabled: bool = True
    allowed_commands: list[str] = Field(
        default_factory=lambda: ["python", "python3", "node", "echo", "date", "whoami", "pwd"]
    )
    hitl_commands: list[str] = Field(default_factory=lambda: ["rm", "rmdir"])
    timeout_seconds: int = 30
    max_output_kb: int = 100

    class Config:
        env_prefix = "SHELL_TOOL_"
        extra = "ignore"


class AppConfig(_BaseSettings):
    """Main application configuration."""

    agent: AgentConfig = Field(default_factory=AgentConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)
    api: ApiConfig = Field(default_factory=ApiConfig)
    cli: CliConfig = Field(default_factory=CliConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    skills: SkillsConfig = Field(default_factory=SkillsConfig)
    filesystem: FilesystemConfig = Field(default_factory=FilesystemConfig)
    shell_tool: ShellToolConfig = Field(default_factory=ShellToolConfig)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "AppConfig":
        """Load configuration from YAML file."""
        path = Path(path)
        if not path.exists():
            return cls()

        with open(path) as f:
            data = yaml.safe_load(f)

        if not data:
            return cls()

        return cls(**data)

    class Config:
        env_file = ".env"
        env_nested_delimiter = "__"
        extra = "ignore"


_config: AppConfig | None = None


def get_settings() -> AppConfig:
    """Get application settings singleton."""
    global _config
    if _config is None:
        _config = AppConfig.from_yaml("config.yaml")
    return _config


def reload_settings() -> AppConfig:
    """Reload settings (useful for testing)."""
    global _config
    _config = None
    return get_settings()
