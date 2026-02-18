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
    min_confidence: float = Field(
        default=0.7, ge=0.0, le=1.0, description="Minimum confidence threshold"
    )
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


class CheckpointCleanupConfig(BaseModel):
    """Configuration for CheckpointCleanupMiddleware.

    Removes old messages from checkpoint after summarization to prevent database bloat.
    """

    enabled: bool = Field(
        default=False,
        description="Disabled in runtime; retained for backward-compatible config parsing",
    )
    keep_buffer_messages: int = Field(
        default=5,
        ge=0,
        le=50,
        description="Number of messages to keep before summary as context buffer",
    )
    backup_enabled: bool = Field(
        default=True,
        description="Keep conversation history file in virtual filesystem as backup",
    )


class TodoDisplayConfig(BaseModel):
    """Configuration for TodoDisplayMiddleware.

    Enhances todo list display with progress tracking and status indicators.
    This is a DISPLAY-ONLY middleware - it doesn't modify todo state.
    """

    enabled: bool = Field(default=True, description="Enable enhanced todo display")
    enable_progress_tracking: bool = Field(
        default=True,
        description="Track tool calls and update todo progress automatically",
    )
    auto_mark_complete: bool = Field(
        default=False,
        description="Automatically mark todos as complete when tools finish (conservative)",
    )


class ToolDisplayConfig(BaseModel):
    """Configuration for ToolDisplayMiddleware.

    Displays tool calls and results as separate messages in real-time.
    """

    enabled: bool = Field(
        default=False,
        description="Disabled in runtime; channel renderers handle tool display",
    )
    show_args: bool = Field(default=True, description="Show tool arguments")
    show_result: bool = Field(default=True, description="Show tool result preview")
    show_duration: bool = Field(default=True, description="Show execution duration")
    show_thinking: bool = Field(default=True, description="Show agent thinking before tool calls")


# =============================================================================
# Built-in DeepAgents Middleware Configurations
# =============================================================================
# NOTE: The following middlewares are BUILT-IN to create_deep_agent and are
# always enabled in the standard stack with hardcoded parameters.
#
# Built-in middlewares (always included, NOT configurable via this system):
# - FilesystemMiddleware (deepagents) - tool_token_limit_before_evict=20000
# - SubAgentMiddleware (deepagents) - no configurable parameters
# - SummarizationMiddleware (deepagents) - trigger/keep computed from model.profile
# - AnthropicPromptCachingMiddleware - hardcoded
# - PatchToolCallsMiddleware - hardcoded
#
# The configuration below only controls SummarizationMiddleware trigger/keep
# behavior via model.profile setting. Other middlewares use their defaults.


class SummarizationConfig(BaseModel):
    """Configuration for SummarizationMiddleware (from deepagents).

    Compresses long conversations to save tokens.
    This middleware is always enabled in the standard stack.

    The trigger threshold is controlled by setting model.profile["max_input_tokens"]
    in the agent factory, which causes _compute_summarization_defaults() to use:
    - trigger = ("fraction", 0.85) of max_input_tokens
    - keep = ("fraction", 0.10) of max_input_tokens

    Configured threshold_tokens determines the max_input_tokens value:
    max_input_tokens = threshold_tokens / 0.85

    Note: trim_tokens_to_summarize and summary_prompt are hardcoded in create_deep_agent
    and cannot be configured via this system.
    """

    threshold_tokens: int = Field(
        default=8000,
        ge=2000,
        le=100000,
        description="Trigger summarization when conversation exceeds this. "
        "Sets model.profile max_input_tokens to threshold/0.85",
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
    checkpoint_cleanup: CheckpointCleanupConfig = Field(
        default_factory=CheckpointCleanupConfig,
        description="Checkpoint cleanup configuration (removes summarized messages)",
    )
    todo_display: TodoDisplayConfig = Field(
        default_factory=TodoDisplayConfig,
        description="Todo display configuration (enhances todo list presentation)",
    )
    tool_display: ToolDisplayConfig = Field(
        default_factory=ToolDisplayConfig,
        description="Tool display configuration (shows tool calls/results in real-time)",
    )

    # Built-in deepagents middlewares (always enabled)
    # Only summarization trigger is configurable via model.profile
    summarization: SummarizationConfig = Field(
        default_factory=SummarizationConfig,
        description="Summarization middleware configuration (always enabled)",
    )
