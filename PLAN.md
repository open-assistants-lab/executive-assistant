# SDK Rewrite Plan: Custom Agent Framework

> Replace LangChain/LangGraph with a minimal, self-owned agent SDK.
> Test-driven. Incremental migration. Zero regression.
> Models.dev integration for 75+ provider compatibility.

## Key Takeaway from OpenCode/AI SDK & Models.dev Research

### Models.dev — The Provider Registry

[models.dev](https://models.dev) is an **open-source database of 111+ LLM providers** with structured model metadata. Each provider has a `provider.toml` and per-model `.toml` files:

**Provider format** (`providers/{provider_id}/provider.toml`):
```toml
name = "OpenAI"
env = ["OPENAI_API_KEY"]
npm = "@ai-sdk/openai"       # AI SDK package (our equivalent: provider type)
doc = "https://platform.openai.com/docs/models"
```

**Model format** (`providers/{provider_id}/models/{model_id}.toml`):
```toml
name = "Claude Sonnet 4"
family = "claude-sonnet"
release_date = "2025-05-22"
attachment = true       # Supports file attachments
reasoning = true        # Supports reasoning/thinking
temperature = true      # Supports temperature parameter
tool_call = true        # Supports function/tool calling
structured_output = true  # Supports JSON mode
modalities.input = ["text", "image", "pdf"]
modalities.output = ["text"]

[cost]
input = 3.00           # Per 1M tokens
output = 15.00
cache_read = 0.30
cache_write = 3.75

[limit]
context = 200_000
output = 64_000
```

**Provider type mapping** (`npm` field → our provider type):
| AI SDK `npm` value | Our provider type | API format |
|---|---|---|
| `@ai-sdk/openai` | `openai` | `/v1/chat/completions` + `/v1/responses` |
| `@ai-sdk/openai-compatible` | `openai-compatible` | `/v1/chat/completions` |
| `@ai-sdk/anthropic` | `anthropic` | `/v1/messages` |
| (provider-specific npm) | `openai-compatible` | Provider-specific baseURL |
| (Ollama) | `ollama` | `/api/chat` |

**This changes our approach significantly**: Instead of hand-coding 3 providers + a factory, we can:
1. **At build time**: Generate a Python model registry from models.dev TOML files
2. **At runtime**: Use the registry for model metadata (context limits, costs, capabilities)
3. **At config time**: Users reference models by provider ID + model ID (same as OpenCode)

### OpenCode/AI SDK Architecture

OpenCode uses [Vercel AI SDK](https://ai-sdk.dev/) (TypeScript) with [py-ai](https://github.com/vercel-labs/py-ai) (Python, experimental):
- `ai.model(provider, model_id)` — provider-agnostic model selector
- `ai.agent(tools=[...])` — agent with tool loop
- `ai.tool` — decorator for tool definitions
- `ai.stream()` / `ai.generate()` — streaming and non-streaming
- Custom agent loops via `@agent.loop`
- Hook suspension (`ai.hook`, `ai.resolve_hook`) for HITL
- `ai.mcp.get_http_tools()` — MCP integration

**py-ai is too experimental** (29 stars, 2 contributors, marked "not stable") to depend on. But its architecture is exactly right.

### Our Approach

**Build our own SDK** with models.dev as the model metadata source. This gives us:
- **111+ providers** from day one (via the `openai-compatible` adapter + models.dev metadata)
- **3 custom providers** for nonstandard APIs: Ollama, OpenAI (responses), Anthropic
- **Model capabilities** at config time: tool_call, reasoning, structured_output, context limits
- **Cost tracking**: Per-token costs from models.dev, enabling usage analytics
- **Future-proof**: When new providers appear, we add a TOML file, not code

**Our conclusion**: Build our own provider layer inspired by AI SDK's architecture, but don't depend on `py-ai` (too unstable). Use `models.dev` as a model metadata reference. Support OpenAI-compatible as the universal fallback (covers Ollama, LM Studio, llama.cpp, Together, Groq, DeepSeek, OpenRouter, etc.).

---

## Phase 0: Test Harness & Baseline (5 days)

**Goal**: Capture current behavior as regression tests before changing anything.

### 0.1 Create test directory structure
```
tests/sdk/
├── __init__.py
├── conftest.py              # Shared fixtures (mock LLM responses, test DB)
├── test_messages.py         # Message type contracts
├── test_tools.py            # Tool registry contracts
├── test_state.py            # AgentState contracts
├── test_provider_base.py    # LLMProvider interface contracts
├── test_provider_ollama.py  # Ollama provider (mocked HTTP)
├── test_provider_openai.py  # OpenAI provider (mocked HTTP)
├── test_provider_anthropic.py # Anthropic provider (mocked HTTP)
├── test_provider_factory.py # create_model_from_config
├── test_agent_loop.py       # Core agent loop
├── test_agent_loop_middleware.py # Middleware hooks
├── test_agent_loop_hitl.py  # Human-in-the-loop
├── test_middleware_base.py   # Custom Middleware base
├── test_memory_middleware.py # MemoryMiddleware migration
├── test_skill_middleware.py  # SkillMiddleware migration
├── test_summarization_middleware.py # SummarizationMiddleware migration
├── test_tool_migration.py    # Per-tool migration verification
├── test_adapter_cli.py       # CLI adapter
├── test_adapter_http.py      # HTTP adapter
└── test_conformance.py       # Full conformance vs LangChain
```

### 0.2 Write conformance tests against current LangChain implementation
- Tool calling: given a tool-defined function, invoke it through the agent loop, verify correct tool selection and result
- Streaming: verify SSE events match expected format (`type: tool`, `type: ai`, `type: done`)
- Middleware order: Memory → Skill → Summarization, verify each fires in sequence
- Error handling: LLM returns error, tool throws exception, model returns no tool calls

### 0.3 Write contract tests for each of the 29 tools
- Capture input/output pairs for every tool under `src/tools/`
- Each test: `tool.invoke({"user_id": "test", ...params})` → verify output schema
- These become the golden tests that both old and new implementations must pass

### 0.4 Write LLM provider contract tests
- Mock HTTP responses for Ollama (`/api/chat`), OpenAI (`/v1/chat/completions`), Anthropic (`/v1/messages`)
- Verify: request format, response parsing, tool call extraction, streaming chunk parsing, error handling

### 0.5 Run all existing tests, record baseline
- `uv run pytest tests/` — record pass count
- All existing unit tests must continue to pass throughout migration

**Exit criteria**: Conformance + contract test suite green. Baseline recorded.

---

## Phase 0.5: API Contracts + WebSocket Protocol + Test Page (3-4 days)

**Goal**: Lock the frontend-server API contract before SDK work begins. Refactor HTTP into a clean router structure. Add WebSocket for bidirectional agent communication. Provide a minimal test UI for manual verification.

Why this before the SDK: The API surface (endpoints, request/response shapes, WS message types) is independent of whether the agent runs on LangChain or our custom `AgentLoop`. By locking the contract now, Flutter development can start in parallel with SDK phases 1-3. When the SDK replaces LangChain internals, only the WS handler changes — the contract stays the same.

### 0.5.1 HTTP API Contract Tests

Write contract tests for all 40+ existing HTTP endpoints. These tests verify:
- Request/response shapes (Pydantic model validation)
- HTTP status codes
- Error handling patterns
- Per-user isolation (user_id scoping)

```python
# tests/sdk/test_api_contracts.py

# Health
GET  /health                        → {"status": "healthy"}
GET  /health/ready                  → {"status": "ready"}

# Conversation
GET  /conversation?user_id=&limit=  → {"messages": [...]}
DELETE /conversation?user_id=       → {"status": "cleared"}

# Message (non-streaming)
POST /message                       → MessageResponse

# Message (SSE streaming) — remains until WS replaces it
POST /message/stream                → SSE stream

# Memories
GET    /memories?user_id=&domain=&memory_type=&min_confidence=&limit=&scope=&project_id=
POST   /memories?trigger=&action=&domain=&memory_type=&user_id=
PUT    /memories/{memory_id}?trigger=&action=&confidence=&user_id=
DELETE /memories/{memory_id}?user_id=
POST   /memories/search             → MemorySearchRequest
POST   /memories/search-all         → SearchAllRequest
POST   /memories/consolidate?user_id=
POST   /memories/connections        → ConnectionRequest
GET    /memories/insights?user_id=&limit=&domain=
DELETE /memories/insights/{insight_id}?user_id=
POST   /memories/insights/search    → InsightSearchRequest
GET    /memories/stats?user_id=

# Contacts
GET    /contacts?user_id=
GET    /contacts/search?query=&user_id=
POST   /contacts?email=&name=&phone=&company=&user_id=
PUT    /contacts/{contact_id}?email=&name=&phone=&company=&user_id=
DELETE /contacts/{contact_id}?user_id=

# Todos
GET    /todos?user_id=
POST   /todos?content=&priority=&user_id=
PUT    /todos/{todo_id}?content=&status=&priority=&user_id=
DELETE /todos/{todo_id}?user_id=

# Email
GET    /email/accounts?user_id=
POST   /email/accounts              → EmailConnectRequest
DELETE /email/accounts/{account_name}?user_id=
GET    /email/messages?account_name=&limit=&folder=&user_id=
GET    /email/messages/{email_id}?account_name=&user_id=
GET    /email/search?query=&account_name=&user_id=
POST   /email/send?to=&subject=&body=&account_name=&user_id=

# Workspace (files)
GET    /workspace/{path}?user_id=
POST   /workspace/{path}?user_id=   → {"content": "..."}
DELETE /workspace/{path}?user_id=
GET    /workspace/read/{path}?user_id=

# Sync
GET    /sync/status?user_id=
POST   /sync/pin/{path}?user_id=
DELETE /sync/pin/{path}?user_id=
POST   /sync/download/{path}?user_id=
GET    /sync/stream?user_id=         → SSE stream

# Skills
GET    /skills?user_id=
POST   /skills?name=&description=&content=&user_id=
DELETE /skills/{skill_name}?user_id=

# Subagents
GET    /subagents?user_id=
POST   /subagents?name=&description=&model=&skills=&tools=&system_prompt=&user_id=
DELETE /subagents/{subagent_name}?user_id=
GET    /subagents/jobs?user_id=
GET    /subagents/jobs/{job_id}
POST   /subagents/invoke?name=&task=&user_id=
POST   /subagents/batch              → list[dict]
POST   /subagents/schedule?name=&task=&run_at=&cron=&user_id=
DELETE /subagents/jobs/{job_id}?user_id=
```

Each endpoint gets a test that:
1. Creates the request with valid params
2. Verifies the response shape matches the Pydantic model
3. Verifies error handling (missing required params returns 422)
4. Uses a test user_id to isolate test data

### 0.5.2 WebSocket Protocol Design

Design a clean JSON message protocol for bidirectional agent communication. This replaces the messy SSE streaming in `/message/stream`.

**Client → Server messages:**

```json
// Send a message to the agent
{"type": "user_message", "content": "What's on my schedule today?", "user_id": "alice"}

// Approve a pending tool call (HITL)
{"type": "approve", "call_id": "call_abc123"}

// Reject a pending tool call (HITL)
{"type": "reject", "call_id": "call_abc123", "reason": "I don't want to delete that file"}

// Edit tool call arguments before approval
{"type": "edit_and_approve", "call_id": "call_abc123", "edited_args": {"path": "/safe/path.txt"}}

// Cancel an ongoing agent execution
{"type": "cancel"}

// Ping/heartbeat
{"type": "ping"}
```

**Server → Client messages:**

```json
// AI text token (streamed)
{"type": "ai_token", "content": "You have", "session_id": "sess_123"}

// Tool call started
{"type": "tool_start", "tool": "email_list", "call_id": "call_abc123", "args": {"folder": "INBOX"}}

// Tool call completed
{"type": "tool_end", "tool": "email_list", "call_id": "call_abc123", "result_preview": "Found 5 emails..."}

// Human-in-the-loop interrupt: agent wants approval
{"type": "interrupt", "call_id": "call_abc123", "tool": "files_delete", "args": {"path": "/important.txt"}, "allowed_actions": ["approve", "reject", "edit"]}

// Middleware event (verbose mode)
{"type": "middleware", "name": "MemoryMiddleware", "event": "before_agent", "data": {...}}

// Reasoning/thinking token (for reasoning models)
{"type": "reasoning", "content": "Let me check the schedule first..."}

// Agent execution complete
{"type": "done", "response": "You have 3 meetings today..."}

// Error
{"type": "error", "message": "Connection to model failed", "code": "MODEL_ERROR"}

// Pong
{"type": "pong"}
```

**Why WS over SSE:**
- Bidirectional: client can approve/reject/cancel on the same connection
- Proper framing: JSON messages instead of `data: ...\n\n` parsing
- Simpler code: no separate `/approve` endpoint, everything flows through one connection
- Better for Flutter: `web_socket_channel` package is mature and simple
- Connection state: the WS connection IS the session, no need for `_pending_approvals` dict

### 0.5.3 HTTP Router Refactor

Split the monolithic `src/http/main.py` (1707 lines) into a clean package:

```
src/http/
├── __init__.py
├── main.py              # FastAPI app + lifespan (~80 lines)
├── models.py            # All Pydantic request/response models (~100 lines)
├── router_conversation.py  # WS endpoint for agent chat (~200 lines)
├── router_memories.py      # Memory CRUD endpoints (~100 lines)
├── router_contacts.py      # Contacts CRUD endpoints (~80 lines)
├── router_todos.py         # Todos CRUD endpoints (~60 lines)
├── router_email.py         # Email endpoints (~80 lines)
├── router_workspace.py     # File/workspace endpoints (~80 lines)
├── router_sync.py          # File sync + SSE stream (~80 lines)
├── router_skills.py        # Skills CRUD endpoints (~60 lines)
├── router_subagents.py     # Subagent endpoints (~80 lines)
└── ws_protocol.py           # WS message types + parsing (~60 lines)
```

**Key changes:**
- All request/response shapes defined as Pydantic models in `models.py`
- WebSocket endpoint at `/ws/conversation` replaces `/message/stream`
- Old `/message/stream` (SSE) kept for backward compatibility, marked deprecated
- Each router is <100 lines, easy to test in isolation
- `main.py` just does `app.include_router(...)` + lifespan

### 0.5.4 Contract Test Suite

```
tests/api/
├── __init__.py
├── conftest.py              # FastAPI TestClient fixture + test user setup/teardown
├── test_health.py            # GET /health, GET /health/ready
├── test_conversation.py      # GET/DELETE /conversation
├── test_message.py           # POST /message (non-streaming)
├── test_message_stream.py    # POST /message/stream (SSE)
├── test_ws_conversation.py   # WS /ws/conversation (new)
├── test_memories.py          # All /memories/* endpoints
├── test_contacts.py          # All /contacts/* endpoints
├── test_todos.py             # All /todos/* endpoints
├── test_email.py             # All /email/* endpoints
├── test_workspace.py         # All /workspace/* endpoints
├── test_sync.py              # All /sync/* endpoints
├── test_skills.py             # All /skills endpoints
├──── test_subagents.py       # All /subagents/* endpoints
└── test_ws_protocol.py       # WS message parsing/serialization unit tests
```

Tests use `pytest-asyncio` + FastAPI's `TestClient` (sync) and `httpx.AsyncClient` (async). For WebSocket tests, use `TestClient.websocket`. Tool invocations that require real services (email, MCP, etc.) are mocked.

### 0.5.5 Minimal Test UI

Single HTML file (`tests/api/test_harness.html`) that:
- Connects to WS `/ws/conversation`
- Has a chat input and response display area
- Shows streaming tokens in real-time
- Shows tool calls (start/end) with expandable details
- Has buttons for approve/reject on interrupts
- Has tabs for CRUD operations (memories, contacts, todos, etc.)
- Works with any backend (current LangChain or future SDK)

```
tests/api/test_harness.html  (~400 lines, no build step, vanilla JS + CSS)
```

This gives immediate visual verification that the API works, and serves as a reference for the Flutter implementation.

**Exit criteria**:
1. All 40+ HTTP endpoints have contract tests passing
2. WebSocket protocol documented with JSON schema
3. `src/http/` refactored into router package (1707 → ~800 lines across 12 files)
4. Legacy SSE endpoint still works (backward compatible)
5. Test harness HTML page works in browser
6. All existing unit tests still pass

---

## Phase 1: Core SDK — Messages, Tools, State (7-10 days)

**Goal**: Replace `langchain_core.messages`, `@tool` decorator, and `AgentState`. Zero LangChain imports in these modules.

### 1.1 `src/sdk/messages.py` — Message types (~60 lines)

```python
"""Message types for the agent SDK.

Drop-in replacement for langchain_core.messages.
Also provides .to_langchain() / .from_langchain() for dual-running.
"""
from pydantic import BaseModel

class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict

class Message(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str | list[dict] = ""
    tool_calls: list[ToolCall] = []
    tool_call_id: str | None = None
    name: str | None = None

    # Convenience constructors
    @classmethod
    def system(cls, content: str) -> "Message": ...
    @classmethod
    def user(cls, content: str) -> "Message": ...
    @classmethod
    def assistant(cls, content: str, tool_calls: list[ToolCall] | None = None) -> "Message": ...
    @classmethod
    def tool_result(cls, tool_call_id: str, content: str) -> "Message": ...

    # LangChain interop (removed after migration)
    def to_langchain(self) -> Any: ...
    @classmethod
    def from_langchain(cls, msg: Any) -> "Message": ...
```

**Tests**: `test_messages.py` — serialization, equality, conversion to/from LangChain format, Pydantic validation errors.

### 1.2 `src/sdk/tools.py` — Tool registry (~100 lines)

Inspired by `ai.tool` from py-ai and `@tool` from LangChain:

```python
"""Tool definition and registry for the agent SDK."""
from typing import Callable
from pydantic import BaseModel

class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters: dict  # JSON Schema
    function: Callable  # Not serialized

class ToolRegistry:
    """Registry for tools available to an agent."""
    def __init__(self): ...
    def register(self, func: Callable | None = None, *, name: str | None = None) -> Callable: ...
    def get(self, name: str) -> ToolDefinition: ...
    def list(self) -> list[ToolDefinition]: ...
    def to_openai_format(self) -> list[dict]: ...
    def to_anthropic_format(self) -> list[dict]: ...

def tool(func: Callable | None = None, *, name: str | None = None) -> Callable:
    """Decorator that extracts JSON schema from type hints + docstring."""
    ...
```

**Tests**: `test_tools.py` — schema generation from type hints, registry CRUD, duplicate detection, validation errors, OpenAI/Anthropic format output.

### 1.3 `src/sdk/state.py` — AgentState (~30 lines)

```python
"""Agent state passed through the agent loop and middleware."""
from dataclasses import dataclass, field

@dataclass
class AgentState:
    messages: list["Message"] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any: ...
    def update(self, updates: dict[str, Any]) -> None: ...
```

**Tests**: `test_state.py` — update, merge, message replacement, extra dict operations.

### 1.4-1.5 Migrate all 29 tools

Migrate 5 tools first as proof-of-concept, then remaining 24 in batches of 5-6.

Migration pattern:
```python
# Before (LangChain)
from langchain_core.tools import tool

@tool
def time_get(user_id: str = "default") -> str:
    """Get the current time."""
    ...

# After (SDK)
from src.sdk.tools import tool

@tool
def time_get(user_id: str = "default") -> str:
    """Get the current time."""
    ...
```

During migration, each tool gets a dual-import guard:
```python
try:
    from src.sdk.tools import tool as sdk_tool
    USE_SDK = True
except ImportError:
    from langchain_core.tools import tool as sdk_tool
    USE_SDK = False
```

**Tests**: `test_tool_migration.py` — verify identical input/output for all 29 tools under both registries.

**Exit criteria**: All 29 tools working with new registry. Conformance tests pass.

---

## Phase 2: LLM Provider Abstraction + Models.dev Registry (7-10 days)

**Goal**: Replace `ChatOllama`, `init_chat_model`, `langchain-openai`, `langchain-anthropic` with direct HTTP calls + models.dev model metadata.

### 2.0 `src/sdk/registry.py` — Model Registry from models.dev (~200 lines)

At **build time** (or via a CLI command), fetch models.dev data and generate a Python registry:

```python
"""Model registry sourced from models.dev TOML data.

Usage:
    # Update registry (run occasionally or in CI)
    python -m src.sdk.registry update

    # In code
    from src.sdk.registry import get_model_info, list_models, get_provider

    model = get_model_info("anthropic", "claude-sonnet-4-20250514")
    # ModelInfo(
    #   id="claude-sonnet-4-20250514",
    #   name="Claude Sonnet 4",
    #   family="claude-sonnet",
    #   provider_id="anthropic",
    #   tool_call=True,
    #   reasoning=True,
    #   structured_output=True,
    #   context_window=200000,
    #   output_limit=64000,
    #   cost=ModelCost(input=3.0, output=15.0, ...),
    #   modalities=ModelModalities(input=["text","image","pdf"], output=["text"]),
    # )

    # List available models
    models = list_models(provider="ollama")  # Filter by provider
    models = list_models(tool_call=True)       # Filter by capability
"""

@dataclass
class ModelCost:
    input: float
    output: float
    reasoning: float | None = None
    cache_read: float | None = None
    cache_write: float | None = None

@dataclass
class ModelInfo:
    id: str
    name: str
    provider_id: str
    family: str | None
    tool_call: bool
    reasoning: bool
    structured_output: bool
    temperature: bool
    context_window: int
    output_limit: int
    cost: ModelCost | None
    modalities_input: list[str]
    modalities_output: list[str]
    open_weights: bool
    status: str | None  # "alpha", "beta", "deprecated"

@dataclass
class ProviderInfo:
    id: str
    name: str
    env: list[str]           # e.g. ["ANTHROPIC_API_KEY"]
    type: str                # "ollama" | "openai" | "openai-compatible" | "anthropic"
    base_url: str | None     # default API endpoint
    doc_url: str | None
```

The registry data is stored as a **pre-generated Python file** (`src/sdk/registry_data.py`) containing all 111+ providers and their models. This is updated via `python -m src.sdk.registry update` which fetches from the models.dev GitHub repo.

**Why pre-generated instead of runtime fetch?**
- No network dependency at startup (critical for CLI responsiveness)
- No API rate limits
- Models.dev data changes rarely (new models monthly, not hourly)
- Users can run `ea models update` to refresh

### 2.1 `src/sdk/providers/base.py` — LLMProvider interface (~50 lines)

```python
class LLMProvider(ABC):
    @abstractmethod
    async def chat(self, messages: list[Message], tools: list[ToolDefinition] | None = None,
                   model: str | None = None, **kwargs) -> Message: ...

    @abstractmethod
    async def chat_stream(self, messages: list[Message], tools: list[ToolDefinition] | None = None,
                          model: str | None = None, **kwargs) -> AsyncIterator[StreamChunk]: ...

    @abstractmethod
    def count_tokens(self, text: str, model: str | None = None) -> int: ...

    @abstractmethod
    def get_model_info(self, model: str) -> ModelInfo: ...

    @property
    @abstractmethod
    def provider_id(self) -> str: ...
```

### 2.2 `src/sdk/providers/ollama.py` — Ollama provider (~120 lines)

Direct HTTP to `http://localhost:11434/api/chat`. Handles:
- Standard completion with `/api/chat`
- Tool calling (Ollama's native format)
- Streaming (NDJSON per-line)
- Model listing via `/api/tags`
- Error handling (connection refused, model not found)

### 2.3 `src/sdk/providers/openai.py` — OpenAI + OpenAI-compatible provider (~150 lines)

**This is the workhorse** — covers OpenAI, Azure OpenAI, Together, Groq, DeepSeek, OpenRouter, Fireworks, LM Studio, llama.cpp, and **all 80+ OpenAI-compatible providers from models.dev**.

```python
class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str | None = None, base_url: str = "https://api.openai.com/v1",
                 organization: str | None = None): ...

    # Configurable base_url makes this work for ALL openai-compatible providers:
    # - Together: base_url="https://api.together.xyz/v1"
    # - Groq: base_url="https://api.groq.com/openai/v1"
    # - DeepSeek: base_url="https://api.deepseek.com/v1"
    # - OpenRouter: base_url="https://openrouter.ai/api/v1"
    # - LM Studio: base_url="http://localhost:1234/v1"
    # - llama.cpp: base_url="http://localhost:8080/v1"
    # - Any custom endpoint
```

Covers all providers in models.dev that use `@ai-sdk/openai-compatible` npm package.

### 2.4 `src/sdk/providers/anthropic.py` — Anthropic provider (~130 lines)

Direct HTTP to `https://api.anthropic.com/v1/messages`:
- Streaming SSE parsing (Anthropic-specific format: `message_start`, `content_block_start`, `content_block_delta`, etc.)
- Tool use blocks (different from OpenAI's `tool_calls`)
- `x-api-key` auth, `anthropic-version` header
- Extended thinking support (for Claude's reasoning mode)

### 2.5 `src/sdk/providers/factory.py` — Provider factory (~80 lines)

```python
def create_provider(config: LLMConfig) -> LLMProvider:
    """Create LLM provider from configuration.

    Uses models.dev registry for model metadata and capability checks.
    Supports config-driven provider setup (same pattern as OpenCode).
    """

def create_model_from_config() -> LLMProvider:
    """Drop-in replacement for src.llm.providers.create_model_from_config().
    Reads from config.yaml and environment variables.
    """
```

**Config format** (in `config.yaml`, inspired by OpenCode):
```yaml
llm:
  default_provider: "ollama"
  default_model: "minimax-m2.5"

  providers:
    ollama:
      type: "ollama"
      base_url: "http://localhost:11434"     # default
      # models listed from models.dev + any custom overrides

    openai:
      type: "openai"
      api_key_env: "OPENAI_API_KEY"           # env var name
      # base_url: "https://api.openai.com/v1"  # default, override for Azure etc.
      models:                                    # override models.dev defaults
        gpt-4o:
          context_window: 128000

    anthropic:
      type: "anthropic"
      api_key_env: "ANTHROPIC_API_KEY"
      models:
        claude-sonnet-4-20250514:
          context_window: 200000

    # Any OpenAI-compatible provider (80+ from models.dev)
    openrouter:
      type: "openai-compatible"
      api_key_env: "OPENROUTER_API_KEY"
      base_url: "https://openrouter.ai/api/v1"

    groq:
      type: "openai-compatible"
      api_key_env: "GROQ_API_KEY"
      base_url: "https://api.groq.com/openai/v1"

    deepseek:
      type: "openai-compatible"
      api_key_env: "DEEPSEEK_API_KEY"
      base_url: "https://api.deepseek.com/v1"

    together:
      type: "openai-compatible"
      api_key_env: "TOGETHER_API_KEY"
      base_url: "https://api.together.xyz/v1"

    lmstudio:
      type: "openai-compatible"
      base_url: "http://localhost:1234/v1"    # no API key needed
      # api_key: "lm-studio"                  # or hardcoded

    llamacpp:
      type: "openai-compatible"
      base_url: "http://localhost:8080/v1"     # no API key needed
```

**User-facing config** (for the Flutter app's settings screen):
```json
{
  "provider": "anthropic",
  "model": "claude-sonnet-4-20250514",
  "api_key_env": "ANTHROPIC_API_KEY",
  "base_url": "https://api.anthropic.com"
}
```

Users can also configure via environment variables (same as OpenCode):
```bash
# Quick setup for any provider
export ANTHROPIC_API_KEY=sk-...
export OPENAI_API_KEY=sk-...
export GROQ_API_KEY=gsk_...
ea cli   # auto-detects available providers
```

### 2.6 `src/sdk/registry_update.py` — CLI command to update model data

```bash
# Update model registry from models.dev
ea models update                    # fetch latest from models.dev GitHub
ea models list                     # show all available models
ea models list --provider ollama   # filter by provider
ea models list --tool-call          # only models with tool calling
ea models info claude-sonnet-4     # show details for a model
```

This fetches the TOML files from `https://github.com/sst/models.dev`, generates `src/sdk/registry_data.py`, and validates the schema.

### 2.7 Integration test: swap `get_model()` to return new provider

Run `test_agent_conformance.py` with the new provider layer. Both old and new must pass.

**Exit criteria**: All three provider types working (ollama, openai/openai-compatible, anthropic). Streaming works. Tool calling parsed correctly. `get_model()` swappable via config. Models.dev registry contains 111+ providers with model metadata.

---

## Phase 3: Agent Loop (5-7 days)

**Goal**: Replace `create_agent()` with a custom while-loop.

### 3.1 `src/sdk/loop.py` — Core agent loop (~200 lines)

```python
class AgentLoop:
    """Replaces langchain.agents.create_agent() with a simple while-loop."""

    def __init__(self, provider: LLMProvider, tools: list[ToolDefinition],
                 system_prompt: str | None = None,
                 middlewares: list[Middleware] | None = None,
                 max_iterations: int = 25): ...

    async def run(self, messages: list[Message]) -> list[Message]:
        """Run the agent loop to completion. Returns final messages."""
        ...

    async def run_stream(self, messages: list[Message]) -> AsyncIterator[StreamEvent]:
        """Yield streaming events: text deltas, tool calls, tool results, done."""
        ...

    async def run_single(self, messages: list[Message]) -> Message:
        """Single model call (no tool loop). For summarization, extraction, etc."""
        ...
```

The core loop is ~30 lines:
```python
async def run(self, messages):
    state = AgentState(messages=messages)

    # Before agent hooks
    for mw in self.middlewares:
        updates = await mw.abefore_agent(state)
        if updates: state.update(updates)

    for i in range(self.max_iterations):
        # Before model hooks
        for mw in self.middlewares:
            updates = await mw.abefore_model(state)
            if updates: state.update(updates)

        # LLM call
        response = await self.provider.chat(state.messages, tools=self.tools)

        state.messages.append(response)

        # After model hooks
        for mw in self.middlewares:
            updates = await mw.aafter_model(state)
            if updates: state.update(updates)

        # Check for tool calls
        if not response.tool_calls:
            break

        # Execute tool calls
        for tc in response.tool_calls:
            tool_wrapped = False
            for mw in self.middlewares:
                tc.arguments = mw.wrap_tool_call(tc.name, tc.arguments)
            result = await self._execute_tool(tc)
            state.messages.append(result)

    # After agent hooks
    for mw in self.middlewares:
        updates = mw.after_agent(state)
        if updates: state.update(updates)

    return state.messages
```

**Tests**: `test_agent_loop.py` — basic loop, max iterations, tool errors, no-tool-call exit, streaming chunks.

### 3.2 Middleware hook execution

Already covered in the loop above. Tests verify hook order, state updates, early exit (return `None` to skip).

### 3.3 Human-in-the-loop

```python
class AgentLoop:
    def __init__(self, ..., interrupt_on: set[str] | None = None): ...

    async def _execute_tool(self, tc: ToolCall) -> Message:
        if tc.name in self.interrupt_on:
            # Suspend and wait for human approval
            event = StreamEvent(type="interrupt", tool_call=tc)
            yield event  # In streaming mode
            # In non-streaming mode, raise InterruptException
        result = self.registry.get(tc.name).function(**tc.arguments)
        return Message.tool_result(tc.id, str(result))
```

**Tests**: `test_agent_loop_hitl.py` — interrupt flow, approval, rejection, edit.

### 3.4 Wire `AgentPool` / `run_agent()` to use new loop

Add a feature flag: `USE_SDK_AGENT_LOOP=true` in config. When true, use `AgentLoop`. When false, use `create_agent()`.

**Exit criteria**: Agent loop passes `test_agent_conformance.py`. Streaming works for CLI and HTTP.

---

## Phase 4: Middleware Migration (5-7 days)

**Goal**: Replace `AgentMiddleware` with custom `Middleware` base class. Migrate all three middlewares.

### 4.1 `src/sdk/middleware.py` — Custom Middleware (~80 lines)

```python
class Middleware:
    """Base middleware class. Drop-in replacement for langchain.agents.middleware.AgentMiddleware."""

    def before_agent(self, state: AgentState) -> dict | None: ...
    def after_agent(self, state: AgentState) -> dict | None: ...
    def before_model(self, state: AgentState) -> dict | None: ...
    def after_model(self, state: AgentState) -> dict | None: ...
    async def abefore_model(self, state: AgentState) -> dict | None: ...
    async def aafter_model(self, state: AgentState) -> dict | None: ...
    def wrap_tool_call(self, tool_name: str, tool_input: dict) -> dict: ...
```

Key differences from LangChain's `AgentMiddleware`:
- No `Runtime` parameter (we don't use it and it's a LangGraph-specific concept)
- No `@hook_config()` decorator (no `can_jump_to` — we handle flow control in the loop)
- No `state_schema` class attribute (just use `AgentState.extra` dict)
- No generic type parameters (simpler)

**Tests**: `test_middleware_base.py` — hook ordering, state updates, None passthrough.

### 4.2 MemoryMiddleware migration

Remove: `from langchain.agents.middleware import AgentMiddleware, AgentState, hook_config`
Remove: `from langgraph.runtime import Runtime`
Remove: `@hook_config()` decorators

Replace: `AgentMiddleware[MemoryState]` → `Middleware`
Replace: `AgentState` → our `AgentState`
Replace: `Runtime` parameter → removed (never used in the method body)

The business logic in `before_agent` and `after_agent` stays identical. Only the class hierarchy and decorators change.

**Tests**: `test_memory_middleware.py` — extraction, injection, turn counting, correction detection (same as current behavior).

### 4.3 SkillMiddleware migration

Same pattern as MemoryMiddleware. Remove LangChain imports, switch base class.

**Tests**: `test_skill_middleware.py` — prompt injection, registry reload, loaded skills tracking.

### 4.4 SummarizationMiddleware migration

This is the most complex migration because it currently extends `LangChainSummarizationMiddleware`. We need to reimplement:

1. Token counting (use `tiktoken` or provider's tokenizer)
2. Message truncation logic (simple: drop oldest messages until under threshold)
3. Summary generation (call LLM to summarize removed messages)
4. Callback on summary (already exists: `on_summarize`)

~150 lines of custom code replacing the inherited LangChain logic.

**Tests**: `test_summarization_middleware.py` — trigger threshold, summary callback, failure handling, duplicate prevention.

### 4.5 Remove dual-mode flag

Once all three middlewares work with the custom base class, remove the `USE_SDK_AGENT_LOOP` flag. New loop only.

**Exit criteria**: No `langchain.agents.middleware` or `langgraph.runtime` imports remain. All conformance tests pass.

---

## Phase 5: Checkpointer & State (2-3 days)

### Decision: Remove or Replace?

The checkpointer is currently **disabled** (`CHECKPOINT_ENABLED=false`). Two options:

**Option A: Remove entirely** (recommended)
- Delete `src/storage/checkpoint.py`
- Remove checkpoint code from `src/storage/database.py`
- Remove all `BaseCheckpointSaver` imports
- The `ConversationStore` already persists messages per-user

**Option B: Replace with custom SQLite persistence** (~100 lines)
- Simple `save_state(thread_id, user_id, state_dict)` / `load_state(thread_id, user_id)`
- Only needed for resumable conversations across server restarts

**Recommendation**: Option A. YAGNI. If resumable conversations are needed later, write a simple checkpointer then (~1 day of work).

**Tests**: Verify nothing references checkpointer after removal.

---

## Phase 6: Adapter Migration (3 days)

**Goal**: CLI, HTTP, and Telegram adapters use new SDK exclusively. WS conversation handler swaps from LangChain to AgentLoop.

### 6.1 `src/cli/main.py`
Replace `run_agent_stream()` to use `AgentLoop.run_stream()`. The CLI already handles SSE-style streaming, so this is a straightforward swap.

### 6.2 `src/http/router_conversation.py` (the WS handler)
Replace the WS handler's internal agent call from `run_agent_stream()` to `AgentLoop.run_stream()`. The WS protocol (designed in Phase 0.5) stays identical — only the backend changes. The API contract tests from Phase 0.5 verify no regression.

Also removes the legacy SSE `/message/stream` endpoint (was deprecated in Phase 0.5).

### 6.3 `src/http/router_*.py` (CRUD endpoints)
No changes needed — these call tools directly, not through LangChain.

### 6.4 `src/telegram/main.py`
Same pattern. Telegram adapter is simpler (no streaming).

### 6.5 `src/agents/subagent/manager.py`
Replace `create_agent()` with `AgentLoop`. The subagent manager creates isolated agent instances — now using the new loop.

**Tests**: `test_adapter_cli.py`, `test_adapter_http.py`, `test_ws_conversation.py` — verify identical behavior to current implementation. Phase 0.5 contract tests still pass.

**Exit criteria**: All three adapters working. No LangChain imports in adapter code. Legacy SSE endpoint removed.

---

## Phase 7: Cleanup & Removal (2 days)

### 7.1 Remove from `pyproject.toml`
```
REMOVE:
- langchain>=1.2.0
- langchain-core>=1.2.0
- langchain-ollama
- langchain-anthropic
- langchain-openai
- langgraph>=1.0.0
- langgraph-checkpoint-sqlite>=3.0.0
- langgraph-checkpoint-postgres>=3.0.0
- langgraph-sdk>=0.3.0
- langgraph-prebuilt>=1.0.0

KEEP:
- langchain-mcp-adapters>=0.2.1  (MCP integration, small and isolated)
```

### 7.2 Verify zero LangChain imports
```bash
rg "from langchain|from langgraph|import langchain|import langgraph" src/ \
   --glob '!**/mcp/**'
```
Must return zero results.

### 7.3 Run full test suite
All 60 bug-fix tests must still pass. All conformance tests must pass.

### 7.4 Benchmark comparison

| Metric | Current (LangChain) | Target (SDK) |
|--------|---------------------|-------------|
| Import time | ~10.4s | <3s |
| Dependencies | 14 LC packages | 1 (`langchain-mcp-adapters`) |
| SDK code | ~8,200 lines (LC) | ~790 lines (ours) |
| Startup time | ~6.2s LC overhead | ~0.3s ours |

---

## New `src/sdk/` Directory Structure

```
src/sdk/
├── __init__.py              # Public API exports
├── messages.py              # Message, ToolCall (~60 lines)
├── tools.py                 # @tool decorator + ToolRegistry (~100 lines)
├── state.py                 # AgentState dataclass (~30 lines)
├── registry.py              # models.dev registry loader (~150 lines)
├── registry_data.py         # Auto-generated from models.dev TOML (~3000+ lines)
├── registry_update.py       # CLI: `ea models update/list/info` (~100 lines)
├── providers/
│   ├── __init__.py          # Exports: LLMProvider, create_provider
│   ├── base.py              # LLMProvider abstract class (~50 lines)
│   ├── ollama.py            # Ollama HTTP provider (~120 lines)
│   ├── openai.py            # OpenAI + OpenAI-compatible provider (~150 lines)
│   ├── anthropic.py         # Anthropic provider (~130 lines)
│   └── factory.py           # create_model_from_config (~80 lines)
├── loop.py                  # AgentLoop (while-loop + streaming) (~200 lines)
└── middleware.py             # Middleware base class (~80 lines)

Total hand-written: ~1110 lines
Auto-generated (registry_data.py): ~3000+ lines from models.dev
Replacing: 9 pip packages (8.2MB) + 49 import lines across 32 files
```

### models.dev Registry Data

The `registry_data.py` file is **auto-generated** from models.dev TOML files and contains:
- 111+ provider configurations (env vars, base URLs, provider types)
- 500+ model definitions (context windows, costs, capabilities)
- Capability flags: `tool_call`, `reasoning`, `structured_output`, `temperature`

This data enables:
1. **Model selection UI** in the Flutter app: "Show me models that support tool calling"
2. **Cost tracking**: Token costs per model from models.dev pricing data
3. **Capability gating**: Automatically disable tool calling for models that don't support it
4. **Context window management**: Automatically truncate messages to fit the model's context limit
5. **Provider validation**: Verify API key is set before attempting connection
src/sdk/
├── __init__.py              # Public API exports
├── messages.py              # Message, ToolCall (~60 lines)
├── tools.py                 # @tool decorator + ToolRegistry (~100 lines)
├── state.py                 # AgentState dataclass (~30 lines)
├── providers/
│   ├── __init__.py          # Exports: LLMProvider, create_provider
│   ├── base.py              # LLMProvider abstract class (~40 lines)
│   ├── ollama.py            # Ollama HTTP provider (~120 lines)
│   ├── openai.py            # OpenAI-compatible provider (~120 lines)
│   ├── anthropic.py         # Anthropic provider (~120 lines)
│   └── factory.py           # create_model_from_config (~50 lines)
├── loop.py                  # AgentLoop (while-loop + streaming) (~200 lines)
└── middleware.py             # Middleware base class (~80 lines)

Total: ~790 lines
```

---

## Timeline

| Phase | Duration | Dependency | Can Parallel? |
|-------|----------|------------|--------------|
| **0** Test Harness | 5 days | None | — |
| **0.5** API Contracts + WS + Refactor | 3-4 days | Phase 0 | Yes, with Phase 1 |
| **1** Messages & Tools | 7-10 days | Phase 0 | Yes, with Phase 0.5 |
| **2** LLM Providers | 5-7 days | Phase 0 | Yes, with Phase 0.5 |
| **3** Agent Loop | 5-7 days | Phase 1 + 2 | No |
| **4** Middleware | 5-7 days | Phase 3 | No |
| **5** Checkpointer | 2-3 days | Phase 3 | Yes, with Phase 4 |
| **6** Adapters (use WS handler) | 3 days | Phase 4 | No |
| **7** Cleanup | 2 days | Phase 6 | No |
| **Total** | **7-9 weeks** | | |

Phase 0.5 can start as soon as Phase 0 conformance tests are written (day 3-4 of Phase 0). The API contract tests are independent of SDK internals — they test the HTTP/WS interface, not the agent loop.

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| LangChain behavior differs from our loop | Conformance tests in Phase 0 capture exact behavior |
| Tool calling format varies across providers | Provider-specific format normalization in each provider class |
| Anthropic tool use format incompatible | Dedicated Anthropic provider with format conversion |
| MCP integration breaks | Keep `langchain-mcp-adapters`, wrap its output back into our `ToolDefinition` |
| Streaming format differs | Stream chunk normalization in `AgentLoop.run_stream()` |
| Existing bug fixes regress | All 60 bug-fix tests run against new code |
| Startup time doesn't improve | Profile import chains, use lazy imports for providers |
| Frontend blocked on SDK completion | Phase 0.5 locks API contract early — Flutter dev starts parallel to SDK work |
| WS protocol changes after Flutter starts | Protocol tests in `test_ws_protocol.py` catch breaking changes |
| HTTP→WS migration breaks existing clients | Legacy SSE `/message/stream` kept until Phase 7 |
| Monolithic HTTP file makes refactoring risky | Phase 0.5 splits into routers first, then adds WS incrementally |

---

## What We Keep

| Component | Source | Reason |
|-----------|--------|--------|
| `langchain-mcp-adapters` | pip package | MCP is complex (JSON-RPC, server management, tool discovery), this package is small and doesn't pull in the rest of LangChain |
| `config.yaml` structure | Existing | Model configuration format already works |
| Per-user SQLite + ChromaDB | Existing | No change needed |
| All 29 tools | Existing | Only `@tool` decorator changes |
| All 3 middleware classes | Existing (migrated) | Only base class changes |
| Memory, Contacts, Email, etc. | Existing | No change needed |
| **HTTP API CRUD endpoints** | Phase 0.5 refactored | Router structure stays, only conversation handler changes with SDK |
| **WebSocket protocol** | Phase 0.5 new | Contract locked, implementation swaps from LangChain to AgentLoop |
| **Test harness HTML** | Phase 0.5 new | Works with any backend implementation |
| FastAPI + uvicorn | Existing | Web framework, no LangChain dependency |

## What We Remove

| Component | Lines Saved | Replacement |
|-----------|-------------|-------------|
| `langchain` | ~2.4MB | `sdk/tools.py` (100 lines) |
| `langchain-core` | ~4.1MB | `sdk/messages.py` (60 lines) |
| `langchain-ollama` | ~208KB | `sdk/providers/ollama.py` (120 lines) |
| `langchain-openai` | ~428KB | `sdk/providers/openai.py` (120 lines) |
| `langchain-anthropic` | ~368KB | `sdk/providers/anthropic.py` (120 lines) |
| `langgraph` | ~1.0MB | `sdk/loop.py` (200 lines) |
| `langgraph-checkpoint-sqlite` | — | Removed (checkpointer disabled) |
| `langgraph-checkpoint-postgres` | — | Removed (not used) |
| `langgraph-sdk` | ~468KB | Removed (use HTTP directly) |
| `langgraph-prebuilt` | — | Removed (not used) |
| `langsmith` | — | Removed (not used) |
| **Total removed** | **~10MB code** | **~790 lines** |

---

## Post-Rewrite Opportunities

Once the custom SDK is in place, these become trivial to add:

1. **New providers**: Add `groq.py`, `deepseek.py`, `together.py` — each ~50 lines since they're OpenAI-compatible
2. **Model switching at runtime**: `GET /model/switch` endpoint for the Flutter app
3. **Token counting & cost tracking**: Built into `LLMProvider` interface
4. **Streaming observability**: `ai.telemetry`-style hooks for monitoring
5. **Custom agent loops**: `@agent.loop` decorator pattern from py-ai for subagents
6. **Batch inference**: Multiple LLM calls in parallel for multi-perspective analysis