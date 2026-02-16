"""Middleware configuration settings.

All middleware parameters are configurable via YAML only (no env vars).
Configuration is admin-managed via /data/config.yaml.

Environment variables are reserved for:
- API keys (e.g., OPENAI_API_KEY, TAVILY_API_KEY)
- URLs (e.g., DATABASE_URL, FIRECRAWL_BASE_URL)
- Deployment settings (e.g., APP_ENV, DATA_PATH)

Middleware configuration is NOT available via env vars - must use YAML.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# =============================================================================
# Custom Middleware Configurations
# =============================================================================

class MemoryContextConfig(BaseModel):
    """Configuration for MemoryContextMiddleware.

    Injects relevant user memories into prompts using progressive disclosure.
    """

    enabled: bool = Field(default=True, description="Enable memory context injection")
    max_memories: int = Field(default=5, ge=1, le=50, description="Maximum memories to inject")
    min_confidence: float = Field(default=0.7, ge=0.0, le=1.0, description="Minimum confidence threshold")
    include_types: list[str] | None = Field(
        default=None,
        description="Filter to specific memory types (null = all types)",
    )


class MemoryLearningConfig(BaseModel):
    """Configuration for MemoryLearningMiddleware.

    Automatically extracts and saves memories from conversations.
    """

    enabled: bool = Field(default=True, description="Enable automatic memory extraction")
    auto_learn: bool = Field(default=True, description="Extract memories automatically")
    min_confidence: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Minimum confidence for saving extracted memories",
    )
    extraction_model: str | None = Field(
        default=None,
        description="LLM for extraction (provider/model format, e.g., openai/gpt-4o-mini)",
    )
    max_memories_per_conversation: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum memories to extract per conversation",
    )


class LoggingConfig(BaseModel):
    """Configuration for LoggingMiddleware.

    Logs agent activity for debugging and analytics.
    """

    enabled: bool = Field(default=True, description="Enable logging")
    log_dir: str = Field(default="./data/logs", description="Log directory path")
    log_model_calls: bool = Field(default=True, description="Log model calls")
    log_tool_calls: bool = Field(default=True, description="Log tool calls")
    log_memory_access: bool = Field(default=True, description="Log memory access")
    log_errors: bool = Field(default=True, description="Log errors")
    log_format: Literal["jsonl", "json"] = Field(
        default="jsonl",
        description="Log format (jsonl or json)",
    )


class CheckinConfig(BaseModel):
    """Configuration for CheckinMiddleware.

    Periodic check-ins with the user.
    """

    enabled: bool = Field(default=False, description="Enable periodic check-ins")
    interval_minutes: int = Field(
        default=30,
        ge=5,
        le=1440,
        description="Check-in interval in minutes",
    )
    active_hours_start: int = Field(
        default=8,
        ge=0,
        le=23,
        description="Start of active hours (24-hour format)",
    )
    active_hours_end: int = Field(
        default=22,
        ge=1,
        le=24,
        description="End of active hours (24-hour format)",
    )
    idle_threshold_hours: int = Field(
        default=8,
        ge=1,
        le=168,
        description="Idle threshold in hours before check-in",
    )
    checklist: list[str] = Field(
        default_factory=lambda: [
            "Check for pending tasks",
            "Review recent conversations for follow-ups",
            "Summarize any completed work",
        ],
        description="Check-in checklist items",
    )


class RateLimitConfig(BaseModel):
    """Configuration for RateLimitMiddleware.

    Rate limits agent requests per user.
    """

    enabled: bool = Field(default=False, description="Enable rate limiting")
    max_model_calls_per_minute: int = Field(
        default=60,
        ge=1,
        le=1000,
        description="Maximum model calls per minute",
    )
    max_tool_calls_per_minute: int = Field(
        default=120,
        ge=1,
        le=2000,
        description="Maximum tool calls per minute",
    )
    window_seconds: int = Field(
        default=60,
        ge=10,
        le=3600,
        description="Rate limit time window in seconds",
    )


# =============================================================================
# Built-in DeepAgents Middleware Configurations
# =============================================================================

class SummarizationConfig(BaseModel):
    """Configuration for SummarizationMiddleware (from deepagents).

    Compresses long conversations to save tokens.
    This is a critical middleware for effectiveness testing.
    """

    enabled: bool = Field(default=False, description="Enable conversation summarization")
    max_tokens: int = Field(
        default=4000,
        ge=1000,
        le=32000,
        description="Maximum tokens after summarization",
    )
    threshold_tokens: int = Field(
        default=8000,
        ge=2000,
        le=100000,
        description="Trigger summarization when conversation exceeds this",
    )
    summary_model: str | None = Field(
        default=None,
        description="Custom summarization model (provider/model format). "
                    "Uses SUMMARIZATION_MODEL from env if null.",
    )


class TodoListConfig(BaseModel):
    """Configuration for TodoListMiddleware (from deepagents).

    Manages todo lists for task tracking.
    """

    enabled: bool = Field(default=True, description="Enable todo list middleware")
    max_todos: int = Field(
        default=100,
        ge=10,
        le=1000,
        description="Maximum todos allowed",
    )


class FilesystemConfig(BaseModel):
    """Configuration for FilesystemMiddleware (from deepagents).

    Manages file operations in the virtual filesystem.
    """

    enabled: bool = Field(default=False, description="Enable filesystem middleware")
    max_file_size_mb: int = Field(
        default=10,
        ge=1,
        le=1000,
        description="Maximum file size in MB",
    )


class SubagentConfig(BaseModel):
    """Configuration for SubagentMiddleware (from deepagents).

    Manages subagent delegation.
    """

    enabled: bool = Field(default=True, description="Enable subagent middleware")
    max_delegation_depth: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum subagent delegation depth",
    )


class HumanInTheLoopConfig(BaseModel):
    """Configuration for HumanInTheLoopMiddleware (from deepagents).

    Requires user confirmations for certain actions.
    """

    enabled: bool = Field(default=False, description="Enable human-in-the-loop confirmations")
    confirm_tool_calls: bool = Field(default=False, description="Confirm tool calls")
    confirm_subagent_calls: bool = Field(
        default=True,
        description="Confirm subagent calls",
    )


class ToolRetryConfig(BaseModel):
    """Configuration for ToolRetryMiddleware (from deepagents).

    Retries failed tool calls automatically.
    """

    enabled: bool = Field(default=True, description="Enable tool retry middleware")
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum retry attempts",
    )
    retry_on_errors: list[str] = Field(
        default_factory=lambda: ["timeout", "rate_limit", "server_error"],
        description="Error types to retry",
    )


# =============================================================================
# Main Middleware Configuration
# =============================================================================

class MiddlewareConfig(BaseModel):
    """Configuration for all middlewares.

    Includes both custom middlewares and built-in deepagents middlewares.
    All configuration is YAML-only (no env vars).
    """

    # Custom middlewares
    memory_context: MemoryContextConfig = Field(
        default_factory=MemoryContextConfig,
        description="Memory context injection configuration",
    )
    memory_learning: MemoryLearningConfig = Field(
        default_factory=MemoryLearningConfig,
        description="Memory learning and extraction configuration",
    )
    logging: LoggingConfig = Field(
        default_factory=LoggingConfig,
        description="Logging configuration",
    )
    checkin: CheckinConfig = Field(
        default_factory=CheckinConfig,
        description="Check-in middleware configuration",
    )
    rate_limit: RateLimitConfig = Field(
        default_factory=RateLimitConfig,
        description="Rate limiting configuration",
    )

    # Built-in deepagents middlewares
    summarization: SummarizationConfig = Field(
        default_factory=SummarizationConfig,
        description="Summarization middleware configuration",
    )
    todo_list: TodoListConfig = Field(
        default_factory=TodoListConfig,
        description="Todo list middleware configuration",
    )
    filesystem: FilesystemConfig = Field(
        default_factory=FilesystemConfig,
        description="Filesystem middleware configuration",
    )
    subagent: SubagentConfig = Field(
        default_factory=SubagentConfig,
        description="Subagent middleware configuration",
    )
    human_in_the_loop: HumanInTheLoopConfig = Field(
        default_factory=HumanInTheLoopConfig,
        description="Human-in-the-loop middleware configuration",
    )
    tool_retry: ToolRetryConfig = Field(
        default_factory=ToolRetryConfig,
        description="Tool retry middleware configuration",
    )
