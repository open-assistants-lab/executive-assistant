"""Settings module for Executive Assistant."""

from pathlib import Path

import yaml
from pydantic import ConfigDict, Field
from pydantic_settings import BaseSettings


class _BaseSettings(BaseSettings):
    """Base settings with common config."""

    model_config = ConfigDict(extra="ignore")


class AgentConfig(_BaseSettings):
    """Agent configuration."""

    name: str = Field(default="Executive Assistant")
    model: str = Field(default="ollama:minimax-m2.5")
    system_prompt: str = Field(default="You are a helpful executive assistant.")

    model_config = ConfigDict(env_prefix="AGENT_")


class DatabaseConfig(_BaseSettings):
    """Database configuration."""

    host: str = Field(default="localhost")
    port: int = Field(default=5432)
    name: str = Field(default="executive_assistant")
    user: str = Field(default="postgres")
    password: str = Field(default="")
    pool_size: int = Field(default=10)

    model_config = ConfigDict(env_prefix="DB_")

    @property
    def connection_string(self) -> str:
        """Generate asyncpg connection string."""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"

    @property
    def sync_connection_string(self) -> str:
        """Generate psycopg2 connection string."""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


class CheckpointerConfig(_BaseSettings):
    """Checkpointer configuration.

    retention_days:
        0 = disabled (no checkpoints)
        -1 = keep forever
        N = keep for N days
    """

    enabled: bool = Field(default=False)
    path: str = Field(default="")
    retention_days: int = Field(default=7)

    model_config = ConfigDict(env_prefix="CHECKPOINT_")


class MessagesConfig(_BaseSettings):
    """Messages (long-term) configuration using SQLite + FTS5 + ChromaDB."""

    enabled: bool = True
    user_directory: str = "data/users/{user_id}/messages"

    model_config = ConfigDict(env_prefix="MESSAGES_")


class StoreConfig(_BaseSettings):
    """Store configuration for long-term memory."""

    enabled: bool = True

    model_config = ConfigDict(env_prefix="STORE_")


class SummarizationConfig(_BaseSettings):
    """Summarization middleware configuration (short-term token reduction)."""

    enabled: bool = True
    trigger_tokens: int = 4000
    keep_messages: int = 20
    model: str = Field(default="ollama:minimax-m2.5")

    model_config = ConfigDict(env_prefix="SUMMARY_")


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


class LoggingConfig(_BaseSettings):
    """Logging configuration."""

    enabled: bool = True
    level: str = "info"  # debug, info, warning, error
    json_dir: str = "data/logs"

    model_config = ConfigDict(env_prefix="LOGGING_")


class ObservabilityConfig(_BaseSettings):
    """Observability configuration."""

    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    langfuse: LangfuseConfig = Field(default_factory=LangfuseConfig)


class ApiConfig(_BaseSettings):
    """API configuration."""

    host: str = "0.0.0.0"
    port: int = 8000

    model_config = ConfigDict(env_prefix="API_")


class CliConfig(_BaseSettings):
    """CLI configuration."""

    model_config = ConfigDict(env_prefix="CLI_")


class ToolsConfig(_BaseSettings):
    """Tools configuration."""

    model_config = ConfigDict(env_prefix="TOOLS_")


class SkillsConfig(_BaseSettings):
    """Skills configuration."""

    user_directory: str = "data/users/{user_id}/skills"

    model_config = ConfigDict(env_prefix="SKILLS_")

    def get_user_directory(self, user_id: str) -> str:
        """Get user-specific skills directory."""
        return self.user_directory.format(user_id=user_id)


class FilesystemConfig(_BaseSettings):
    """Filesystem tools configuration."""

    enabled: bool = True
    user_root: str = "data/users/{user_id}/workspace"
    max_file_size_mb: int = 10

    model_config = ConfigDict(env_prefix="FILESYSTEM_")


class ShellToolConfig(_BaseSettings):
    """Shell tool configuration."""

    enabled: bool = True
    allowed_commands: list[str] = Field(
        default_factory=lambda: ["python3", "node", "echo", "date", "whoami", "pwd"]
    )
    timeout_seconds: int = 30
    max_output_kb: int = 100

    model_config = ConfigDict(env_prefix="SHELL_TOOL_")


class EmailSyncConfig(_BaseSettings):
    """Email sync configuration."""

    enabled: bool = True
    interval_minutes: int = 5
    batch_size: int = 100
    backfill_limit: int = 1000

    model_config = ConfigDict(env_prefix="EMAIL_SYNC_")


class MCPConfig(_BaseSettings):
    """MCP (Model Context Protocol) configuration."""

    enabled: bool = True
    idle_timeout_minutes: int = 30

    model_config = ConfigDict(env_prefix="MCP_")


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
    email_sync: EmailSyncConfig = Field(default_factory=EmailSyncConfig)
    mcp: MCPConfig = Field(default_factory=MCPConfig)

    model_config = ConfigDict(env_file=".env", env_nested_delimiter="__")

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
