"""Custom Agent SDK - message types, tools, providers, and agent loop.

Public API:
    Message, ToolCall, StreamChunk - message types
    tool, ToolRegistry, ToolDefinition, ToolAnnotations, ToolResult - tool system
    AgentState - agent loop state
    LLMProvider, ModelInfo, ModelCost - provider base types
    create_provider, create_model_from_config - factory functions
    OllamaLocal, OllamaCloud - Ollama providers
    OpenAIProvider, AnthropicProvider, GeminiProvider - other providers
    AgentLoop, Interrupt, RunConfig, CostTracker, Usage - agent loop
    Middleware - middleware base class
    MemoryMiddleware - memory extraction/injection (SDK-native)
    SummarizationMiddleware - conversation summarization (SDK-native)
    ProgressMiddleware - subagent progress tracking + doom loop detection
    InstructionMiddleware - subagent course-correction + cancel signal handling
    HookManager, HookConfig, HookResult, HookDecision - shell hooks
    InputGuardrail, OutputGuardrail, ToolGuardrail, GuardrailResult, GuardrailTripwire - guardrails
    Handoff, HandoffInput - handoffs
    TraceProvider, TraceProcessor, Span, SpanType - tracing
    normalize_tool_schema, repair_tool_call - validation
    get_model_info, list_models, get_provider, list_providers, refresh - models.dev registry
    HybridDB, SearchMode, EmbeddingModelError - hybrid search database
    AgentDef, SubagentResult, TaskStatus, TaskCancelledError - subagent models
    WorkQueueDB, get_work_queue - work queue database
    SubagentCoordinator, get_coordinator - subagent coordination
"""

from src.sdk.coordinator import SubagentCoordinator, get_coordinator
from src.sdk.guardrails import (
    GuardrailResult,
    GuardrailTripwire,
    InputGuardrail,
    OutputGuardrail,
    ToolGuardrail,
)
from src.sdk.handoffs import Handoff, HandoffInput
from src.sdk.hybrid_db import EmbeddingModelError, HybridDB, SearchMode
from src.sdk.loop import AgentLoop, CostTracker, Interrupt, RunConfig
from src.sdk.messages import Message, StreamChunk, ToolCall, Usage
from src.sdk.middleware import Middleware
from src.sdk.middleware_instruction import InstructionMiddleware
from src.sdk.middleware_memory import MemoryMiddleware
from src.sdk.middleware_progress import ProgressMiddleware
from src.sdk.middleware_summarization import SummarizationMiddleware
from src.sdk.providers.base import LLMProvider, ModelCost, ModelInfo
from src.sdk.providers.factory import create_model_from_config, create_provider
from src.sdk.providers.ollama import OllamaCloud, OllamaLocal
from src.sdk.registry import get_model_info, get_provider, list_models, list_providers, refresh
from src.sdk.state import AgentState
from src.sdk.subagent_models import (
    AgentDef,
    CostLimitExceededError,
    MaxCallsExceededError,
    SubagentResult,
    TaskCancelledError,
    TaskStatus,
)
from src.sdk.tools import ToolAnnotations, ToolDefinition, ToolRegistry, ToolResult, tool
from src.sdk.tracing import (
    ConsoleTraceProcessor,
    JsonTraceProcessor,
    Span,
    SpanType,
    TraceProcessor,
    TraceProvider,
)
from src.sdk.validation import normalize_tool_schema, repair_tool_call
from src.sdk.work_queue import WorkQueueDB, get_work_queue

__all__ = [
    "Message",
    "ToolCall",
    "StreamChunk",
    "tool",
    "ToolRegistry",
    "ToolDefinition",
    "ToolAnnotations",
    "ToolResult",
    "Usage",
    "AgentState",
    "LLMProvider",
    "ModelInfo",
    "ModelCost",
    "create_provider",
    "create_model_from_config",
    "OllamaLocal",
    "OllamaCloud",
    "get_model_info",
    "list_models",
    "get_provider",
    "list_providers",
    "refresh",
    "AgentLoop",
    "Interrupt",
    "RunConfig",
    "CostTracker",
    "Middleware",
    "MemoryMiddleware",
    "InstructionMiddleware",
    "ProgressMiddleware",
    "SummarizationMiddleware",
    "HookManager",
    "HookConfig",
    "HookResult",
    "HookDecision",
    "InputGuardrail",
    "OutputGuardrail",
    "ToolGuardrail",
    "GuardrailResult",
    "GuardrailTripwire",
    "Handoff",
    "HandoffInput",
    "HybridDB",
    "SearchMode",
    "EmbeddingModelError",
    "TraceProvider",
    "TraceProcessor",
    "ConsoleTraceProcessor",
    "JsonTraceProcessor",
    "Span",
    "SpanType",
    "normalize_tool_schema",
    "repair_tool_call",
    "AgentDef",
    "SubagentResult",
    "TaskStatus",
    "TaskCancelledError",
    "MaxCallsExceededError",
    "CostLimitExceededError",
    "WorkQueueDB",
    "get_work_queue",
    "SubagentCoordinator",
    "get_coordinator",
]
