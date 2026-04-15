# Executive Assistant - Agent Guidelines

This document provides guidelines for agents working on this codebase.

---

## 1. Build, Lint, and Test Commands

### Installation
```bash
# Install with all dependencies
uv pip install -e ".[cli,http,telegram,dev]"

# Install specific extras
uv pip install -e ".[cli]"      # CLI only
uv pip install -e ".[http]"      # HTTP API only
uv pip install -e ".[telegram]"  # Telegram bot only
uv pip install -e ".[dev]"      # Development tools
```

### Running the Application
```bash
uv run ea cli        # Start CLI (with streaming support)
uv run ea http      # Start HTTP server (with SSE streaming)
uv run ea telegram  # Start Telegram bot
```

### Linting and Type Checking
```bash
# Run ruff linter
uv run ruff check src/

# Auto-fix linting issues
uv run ruff check src/ --fix

# Run mypy type checker
uv run mypy src/
```

### Testing (TDD - Test Driven Development)
```bash
# Run all tests
uv run pytest

# Run SDK tests only
uv run pytest tests/sdk/ -v

# Run a single test file
uv run pytest tests/sdk/test_tools.py

# Run a single test function
uv run pytest tests/sdk/test_tools.py::TestToolDecorator::test_basic_decoration

# Run tests with coverage
uv run pytest --cov=src --cov-report=html

# Run persona evaluation (25 personas)
uv run python tests/evaluation/evaluate.py
```

### Docker
```bash
# Start PostgreSQL
cd docker && docker compose up -d

# Stop PostgreSQL
cd docker && docker compose down

# Build and run app in Docker
cd docker && docker compose up --build
```

---

## 2. Code Style Guidelines

### Python Version
- Minimum: Python 3.11
- Use modern Python features (type hints, structural pattern matching)

### Imports (PEP 8 + Ruff)
```python
# Standard library first
import os
import json
from pathlib import Path
from typing import Any, Optional

# Third-party libraries
from pydantic import Field
from fastapi import FastAPI

# Local imports (absolute)
from src.config import get_settings
from src.sdk.messages import Message, StreamChunk

# Sort imports with: uv run ruff check src/ --fix
```

### Formatting
- Line length: 100 characters
- Use Black-compatible formatting via Ruff
- 4 spaces for indentation (no tabs)

### Type Hints (Required)
```python
# Use type hints for all function signatures
def process_message(message: str, user_id: str = "default") -> dict[str, Any]:
    ...

# Use | for unions (Python 3.10+)
def get_value(key: str | None) -> str:
    ...

# Use Optional for nullable
def find_item(name: Optional[str]) -> Item | None:
    ...
```

### Naming Conventions
- **Variables/functions**: `snake_case` (e.g., `get_logger`, `user_id`)
- **Classes**: `PascalCase` (e.g., `ExecutiveAssistantCLI`, `Logger`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `MAX_RETRIES`, `DEFAULT_TIMEOUT`)
- **Private members**: `_leading_underscore` (e.g., `_internal_state`)

### Tool Naming Pattern
All tools must follow `category_{verb}` pattern:
```python
# Email tools
email_connect, email_disconnect, email_accounts
email_list, email_get, email_search
email_send, email_sync

# Contacts tools
contacts_list, contacts_get, contacts_add, contacts_update, contacts_delete, contacts_search

# Todos tools
todos_list, todos_add, todos_update, todos_delete, todos_extract

# File tools
files_glob_search, files_grep_search, files_list, files_read, files_write, files_edit, files_delete

# Other tools
shell_execute, time_get, memory_get_history, memory_search, skills_list, skills_load
```

### Pydantic Models
```python
from pydantic import BaseModel, Field

class AgentConfig(BaseModel):
    """Agent configuration."""
    name: str = Field(default="Executive Assistant")
    model: str = Field(default="ollama:minimax-m2.5")
    
    class Config:
        env_prefix = "AGENT_"
        extra = "ignore"  # Allow extra fields from env
```

### Error Handling
```python
# Use specific exceptions
try:
    result = await agent.ainvoke({"messages": messages})
except ValueError as e:
    logger.error("validation_error", {"error": str(e)}, user_id=user_id)
    raise
except Exception as e:
    logger.error("unexpected_error", {"error": str(e), "error_type": type(e).__name__}, user_id=user_id)
    raise
```

---

## 3. Current Architecture & Discoveries

### SDK Architecture (Custom, Replacing LangChain/LangGraph)

The codebase has a **custom agent SDK** (`src/sdk/`) that replaces LangChain/LangGraph. The old LangChain code still exists in `src/agents/`, `src/llm/`, `src/middleware/`, and `src/tools/` but is bridged via `src/sdk/langchain_adapter.py` (TEMPORARY — to be removed in Phase 8).

**SDK Core (~5,500 lines, 24 files, 432 tests):**

| Module | Lines | Purpose |
|--------|-------|---------|
| `messages.py` | 438 | `Message`, `ToolCall`, `StreamChunk` — unified message types with block-structured streaming |
| `tools.py` | 280 | `@tool`, `ToolDefinition`, `ToolAnnotations`, `ToolResult`, `ToolRegistry` |
| `loop.py` | 707 | `AgentLoop` (ReAct), `RunConfig`, `CostTracker`, `Interrupt`, guardrails, handoffs, tracing |
| `providers/` | ~1,500 | `OllamaLocal`, `OllamaCloud`, `OpenAIProvider`, `AnthropicProvider`, `GeminiProvider` |
| `registry.py` | 354 | models.dev integration — 4172+ models, 110+ providers, auto-updated |
| `validation.py` | 158 | `normalize_tool_schema()`, `repair_tool_call()` |
| `guardrails.py` | 60 | `InputGuardrail`, `OutputGuardrail`, `ToolGuardrail`, `GuardrailTripwire` |
| `handoffs.py` | 92 | `Handoff`, `HandoffInput` — model-driven agent transfer |
| `tracing.py` | 172 | `TraceProvider`, `Span`, `SpanContext`, `ConsoleTraceProcessor`, `JsonTraceProcessor` |
| `native_tools.py` | 102 | SDK-native `time_get` (first migrated tool) |
| `langchain_adapter.py` | 137 | **TEMPORARY** — wraps LangChain tools as SDK ToolDefinitions |

**Key Design Decisions:**
1. **models.dev integration**: Registry fetches from `https://models.dev/api.json`, caches locally at `data/cache/models.json` with 5-min TTL, falls back to built-in subset. 4172+ models vs. old 20 hardcoded.
2. **Block-structured streaming**: `text_start/delta/end`, `tool_input_start/delta/end`, `reasoning_start/delta/end`, `tool_result`, `interrupt`, `done`, `error`. Backward-compat aliases: `ai_token→text_delta`, `tool_start→tool_input_start`, `reasoning→reasoning_delta`.
3. **ToolAnnotations** (MCP-style): `readOnly`, `destructive`, `idempotent`, `openWorld`, `title`. Auto-approves read-only tools, interrupts on destructive ones.
4. **ToolResult** dual format: `content` (human-readable) + `structured_content` (machine-parseable) + `audience` (user/assistant).
5. **Provider escape hatches**: `provider_options` on inputs (keyed by provider name), `provider_metadata` on outputs. Enables Anthropic `thinking`, Gemini `thinkingConfig`, OpenAI `logprobs` etc.
6. **Reasoning as first-class content**: `Message.reasoning` field persists thinking tokens across turns. Anthropic `thinking` blocks handled in `to_anthropic()`/`from_anthropic_block()`.
7. **Sequential tool execution**: AgentLoop executes tools one at a time (parallel deferred).
8. **No checkpoints**: LangGraph checkpoint system was permanently disabled. Conversation history is managed by `MemoryMiddleware` + `SummarizationMiddleware`.

**Known Provider Behaviors:**
- OpenAI/Anthropic no longer emit duplicate `tool_end` — fixed by Phase 5 block-structured refactor
- Gemini streaming accumulates tool calls across chunks properly
- `provider_options` are plumbed through but reasoning opt-in (Anthropic thinking, Gemini thinkingConfig) must be set per-request — not auto-enabled

### HTTP Layer

Three endpoints, all SDK-powered:
- **REST**: `POST /message` — returns `MessageResponse`
- **SSE**: `POST /message/stream` — Server-Sent Events
- **WebSocket**: `/ws/conversation` — bidirectional with HITL interrupt/approve/reject

Both SSE and WS routers now handle block-structured events (`text_start/delta/end`, `tool_input_start/delta/end`, `reasoning_start/delta/end`, `tool_result`) alongside backward-compat types (`ai_token`, `tool_start`, `tool_end`, `reasoning`).

### Database/Storage

All user data isolated per-user under `data/users/{user_id}/`:
```
data/users/{user_id}/
├── email/
│   └── emails.db
├── contacts/
│   └── contacts.db
├── todos/
│   └── todos.db
└── conversation/
    └── messages.db
```

Decision: **SQLite + ChromaDB per-user even for team/enterprise** (not shared DB).

---

## 4. Coding Concerns & Pitfalls to Avoid

### CRITICAL: LangChain imports are temporary
Only 3 files still import LangChain:
- `src/sdk/messages.py` — `.to_langchain()` / `.from_langchain()` (dual-running bridge)
- `src/sdk/middleware_memory.py` — imports `langchain_core.messages.HumanMessage`
- `src/sdk/middleware_summarization.py` — imports `langchain_core.messages.HumanMessage, SystemMessage`

**Do NOT add new LangChain imports.** All new code should use SDK types (`Message`, `StreamChunk`, `ToolDefinition`). Phase 8 will remove all LangChain dependencies.

### CRITICAL: StreamChunk event types
The `StreamChunk.type` field is a `Literal` with **16 values**. When adding new event handling, always use `chunk.canonical_type` for comparison, not `chunk.type` directly, because backward-compat aliases map:
- `ai_token` → canonical `text_delta`
- `tool_start` → canonical `tool_input_start`
- `reasoning` → canonical `reasoning_delta`

### CRITICAL: user_id must be passed as separate parameter
```python
# CORRECT
logger.info("event_name", {"key": "value"}, user_id=user_id)

# WRONG — user_id inside data dict shows "default" in logs
logger.info("event_name", {"key": "value", "user_id": user_id})
```

### CRITICAL: Provider options are keyed by provider_id
When passing provider-specific options:
```python
# CORRECT — only Anthropic sees its options
provider_options={"anthropic": {"thinking": {"type": "enabled", "budget_tokens": 10000}}}

# WRONG — all providers see this
kwargs={"thinking": {"type": "enabled"}}  # leaks to OpenAI/Gemini
```

### CRITICAL: models.dev registry uses lazy loading
The registry (`src/sdk/registry.py`) fetches from `https://models.dev/api.json` on first access, caches to `data/cache/models.json`. If the API is unreachable, it falls back to a built-in subset. **Never hardcode model info — always use `get_model_info()` or `list_models()`.**

### CRITICAL: No parallel tool execution (by design)
The AgentLoop executes tools sequentially. This was a deliberate decision. If you need parallel execution, it requires a separate `ToolExecutor` class with async concurrency — do NOT just add `asyncio.gather()` in the loop.

### Watch out: ToolAnnotations.auto_approval only works for non-destructive tools
The `_should_interrupt()` method checks: if `destructive=True AND read_only=False` → interrupt. A tool that is both `destructive` AND `read_only` won't interrupt (read-only wins). This is intentional — a read-only destructive tool is a contradiction that defaults to safe.

### Watch out: TraceProvider spans are async context managers
```python
# CORRECT — async context manager
async with provider.start_span(SpanType.LLM_CALL, "call_0") as span:
    span.set_meta("tokens", 100)

# For sync-only tests, use start_span_sync/end_span
span = provider.start_span_sync(SpanType.AGENT, "test_run")
span.finish()
provider.end_span(span)
```

### Watch out: Ollama has two provider classes
- `OllamaLocal` — OpenAI-compatible at `/v1/chat/completions` (localhost or custom)
- `OllamaCloud` — Native `/api/chat` with Bearer auth (ollama.com)

Auto-detection happens in `create_model_from_config()`: if `OLLAMA_BASE_URL` points to ollama.com or `OLLAMA_API_KEY` is set, it uses `OllamaCloud`.

### Watch out: AgentLoop constructor changed
The `AgentLoop` now takes `run_config: RunConfig | None = None` instead of just `max_iterations`. If creating loops manually, use:
```python
loop = AgentLoop(
    provider=provider,
    tools=[...],
    system_prompt="...",
    middlewares=[...],
    run_config=RunConfig(max_llm_calls=50, cost_limit_usd=10.0),
)
```

---

## 5. Logging Best Practices

### Always Use the Logger
```python
from src.app_logging import get_logger, timer

logger = get_logger()

# Use timer for operations with duration tracking
with timer("operation_name", {"key": "value"}, user_id=user_id, channel="cli") as t:
    result = await do_work()
    
# Log at appropriate levels
logger.debug("detailed_info", {"data": "..."}, user_id=user_id)
logger.info("action_completed", {"result": "..."}, user_id=user_id)
logger.warning("potential_issue", {"warning": "..."}, user_id=user_id)
logger.error("operation_failed", {"error": "..."}, user_id=user_id)
logger.info("system_event", {"info": "..."}, user_id="system")
```

### Log Format
`data/logs/YYYY-MM-DD.jsonl`:
```json
{"timestamp": "2026-02-20T03:00:00Z", "user_id": "alice_test", "event": "agent.response", "level": "info", "channel": "cli", "data": {"response": "Hello!"}}
```

### Sensitive Data
The logger automatically redacts fields containing: `api_key`, `password`, `secret`, `token`, `key`

---

## 6. Project Structure

```
executive-assistant/
├── src/
│   ├── __init__.py
│   ├── __main__.py              # CLI entry point
│   ├── app_logging.py           # Logging with timer
│   ├── cli/main.py              # CLI interface
│   ├── http/
│   │   ├── main.py              # FastAPI app
│   │   ├── models.py             # Request/response models
│   │   ├── ws_protocol.py        # WS message types (16+ types)
│   │   └── routers/
│   │       ├── conversation.py   # REST + SSE endpoints
│   │       ├── ws.py             # WebSocket endpoint
│   │       └── ...               # Other routers
│   ├── telegram/main.py         # Telegram bot
│   ├── agents/
│   │   ├── factory.py           # LangChain agent factory (DEPRECATED)
│   │   ├── manager.py           # LangChain agent pool (DEPRECATED)
│   │   └── subagent/           # Subagent system (LANGCHAIN)
│   ├── config/settings.py       # Configuration
│   ├── llm/providers.py         # LangChain LLM providers (DEPRECATED)
│   ├── storage/
│   │   ├── conversation.py      # Message storage
│   │   ├── user.py             # User management
│   │   └── ...                  # (checkpoint.py removed)
│   ├── sdk/                     # ★ Custom Agent SDK (THE CORE)
│   │   ├── __init__.py          # Public API exports
│   │   ├── messages.py          # Message, ToolCall, StreamChunk
│   │   ├── tools.py             # @tool, ToolDefinition, ToolAnnotations, ToolResult, ToolRegistry
│   │   ├── state.py             # AgentState
│   │   ├── loop.py              # AgentLoop, Interrupt, RunConfig, CostTracker
│   │   ├── middleware.py         # Middleware ABC
│   │   ├── middleware_memory.py  # MemoryMiddleware (SDK-native)
│   │   ├── middleware_skill.py   # SkillMiddleware (SDK-native)
│   │   ├── middleware_summarization.py  # SummarizationMiddleware
│   │   ├── native_tools.py      # ToolRegistry with get_native_tools() / get_native_tool_names()
│   │   ├── langchain_adapter.py  # LangChain bridge (TEMPORARY)
│   │   ├── runner.py             # create_sdk_loop, run_sdk_agent (HTTP wiring)
│   │   ├── registry.py          # models.dev integration (4172+ models)
│   │   ├── registry_update.py    # CLI: update models from GitHub
│   │   ├── validation.py        # normalize_tool_schema, repair_tool_call
│   │   ├── guardrails.py        # InputGuardrail, OutputGuardrail, ToolGuardrail
│   │   ├── handoffs.py          # Handoff, HandoffInput
│   │   ├── tracing.py           # TraceProvider, Span, ConsoleTraceProcessor
│   │   ├── tools_core/          # ★ SDK-native tool implementations
│   │   │   ├── cli_adapter.py   # CLIToolAdapter base class (firecrawl, browser-use)
│   │   │   ├── time.py         # time_get
│   │   │   ├── shell.py        # shell_execute
│   │   │   ├── filesystem.py   # 7 file tools
│   │   │   ├── file_search.py  # files_glob_search, files_grep_search
│   │   │   ├── file_versioning.py  # 4 version tools
│   │   │   ├── todos.py        # 5 todo tools
│   │   │   ├── contacts.py     # 6 contact tools
│   │   │   ├── memory.py       # 5 memory tools
│   │   │   ├── email.py        # 8 email tools
│   │   │   ├── firecrawl.py    # 8 firecrawl CLI tools
│   │   │   └── browser_use.py  # 20 browser-use CLI tools
│   │   └── providers/
│   │       ├── base.py           # LLMProvider ABC, ModelInfo, ModelCost
│   │       ├── ollama.py         # OllamaLocal + OllamaCloud
│   │       ├── openai.py         # OpenAIProvider
│   │       ├── anthropic.py      # AnthropicProvider (with thinking blocks)
│   │       ├── gemini.py         # GeminiProvider (with thinkingConfig)
│   │       ├── factory.py        # create_provider, create_model_from_config
│   │       └── __init__.py
│   ├── tools/                   # LangChain @tool functions (93 tools, MIGRATING)
│   │   ├── email/               # email_connect, list, get, search, send, sync
│   │   ├── contacts/             # contacts CRUD
│   │   ├── todos/                # todos CRUD + LLM extraction
│   │   ├── filesystem.py         # files_list, read, write, edit, delete
│   │   ├── file_search.py        # files_glob_search, files_grep_search
│   │   ├── shell.py              # shell_execute
│   │   ├── memory.py             # memory_get_history, memory_search
│   │   ├── time.py               # time_get (LANGCHAIN version)
│   │   ├── firecrawl.py          # scrape_url, search_web, etc.
│   │   └── vault/               # Credential storage
│   └── skills/                  # Skills system
│       ├── middleware.py         # SkillMiddleware
│       ├── registry.py           # SkillRegistry
│       └── tools.py             # skills_list, skills_load
├── tests/
│   ├── sdk/                     # ★ SDK unit tests (432 tests)
│   │   ├── test_messages.py
│   │   ├── test_tools.py
│   │   ├── test_phase5_6.py     # Guardrails, handoffs, tracing, annotations
│   │   ├── test_registry.py      # models.dev registry
│   │   ├── test_providers.py     # Provider contracts
│   │   ├── test_sdk_loop.py      # AgentLoop tests
│   │   └── ...
│   ├── api/                      # HTTP endpoint tests (~100)
│   ├── unit/                     # LangChain-era unit tests
│   └── evaluation/               # Persona evaluation
├── config.yaml
└── pyproject.toml
```

---

## 7. Configuration

### Environment Variables
- Use `.env` for local development
- Use `.env.example` as template
- All config via `src/config/settings.py`

### Config Priority
1. Environment variables (highest)
2. `.env` file
3. `config.yaml`
4. Default values (lowest)

---

## 8. Phase Progress

| Phase | Status | Tests | Description |
|-------|--------|-------|-------------|
| **0** | ✅ Done | 194 | Test harness & baseline |
| **0.5** | ✅ Done | 100 API + 32 WS | API contracts + WS protocol |
| **1** | ✅ Done | 204 | Core SDK (Messages, Tools, State) |
| **2** | ✅ Done | 51 | LLM Provider abstraction |
| **3** | ✅ Done | 48 | Agent Loop |
| **4** | ✅ Done | 347 total | Middleware + SDK HTTP wiring |
| **5** | ✅ Done | +63 new | Structured Streaming + Tool Annotations |
| **6** | ✅ Done | (in 5) | Guardrails, Handoffs, Tracing, RunConfig, CostTracker |
| **models.dev** | ✅ Done | +22 | Dynamic model registry (4172+ models) |
| **7** | 🔄 In Progress | — | Tool Migration (LangChain → SDK-native) |
| **8** | 🔲 Future | — | Cleanup & LangChain removal |
| **9** | 🔲 Future | — | Extract & Open Source SDK |

### Remaining Work for Phase 5+6 Exit Criteria

- [x] All StreamChunk events use block-structured format
- [x] Backward-compat aliases pass existing tests
- [x] Reasoning persists in Message and conversation history
- [x] `provider_options` flow through to provider calls
- [x] Tool annotations on native tools (`time_get`) + langchain adapter defaults
- [x] Auto-approval based on `ToolAnnotations.destructive`
- [x] `repair_tool_call()` handles malformed JSON
- [x] No duplicate `tool_end` events
- [ ] Integration test: reasoning model returns thinking content (need live API)
- [x] 432+ SDK tests passing

### Phase 7: Tool Migration Status

**65 tools migrated to `src/sdk/tools_core/`:**

| Module | Tools | Count |
|--------|-------|-------|
| `time.py` | `time_get` | 1 |
| `shell.py` | `shell_execute` | 1 |
| `filesystem.py` | `files_list`, `files_read`, `files_write`, `files_edit`, `files_delete`, `files_mkdir`, `files_rename` | 7 |
| `file_search.py` | `files_glob_search`, `files_grep_search` | 2 |
| `file_versioning.py` | `files_versions_list`, `files_versions_restore`, `files_versions_delete`, `files_versions_clean` | 4 |
| `todos.py` | `todos_list`, `todos_add`, `todos_update`, `todos_delete`, `todos_extract` | 5 |
| `contacts.py` | `contacts_list`, `contacts_get`, `contacts_add`, `contacts_update`, `contacts_delete`, `contacts_search` | 6 |
| `memory.py` | `memory_get_history`, `memory_search`, `memory_search_all`, `memory_search_insights`, `memory_connect` | 5 |
| `email.py` | `email_connect`, `email_disconnect`, `email_accounts`, `email_list`, `email_get`, `email_search`, `email_send`, `email_sync` | 8 |
| `firecrawl.py` | `scrape_url`, `search_web`, `map_url`, `crawl_url`, `get_crawl_status`, `cancel_crawl`, `firecrawl_status`, `firecrawl_agent` | 8 |
| `browser_use.py` | `browser_open`, `browser_state`, `browser_click`, `browser_input`, `browser_type`, `browser_keys`, `browser_scroll`, `browser_screenshot`, `browser_eval`, `browser_get_title`, `browser_get_text`, `browser_get_html`, `browser_get_url`, `browser_tab_new`, `browser_tab_switch`, `browser_tab_close`, `browser_wait_text`, `browser_sessions`, `browser_close_all`, `browser_status` | 20 |

**NOT YET MIGRATED:**
- Apps (14 tools) — `src/tools/apps/tools.py`
- MCP (3 tools) — `src/tools/mcp/tools.py`
- Skills (3 tools) — `src/skills/tools.py`
- Subagent (10 tools) — `src/agents/subagent/tools.py`

**SKIPPED (will not migrate — Telegram bot uses LangChain agent directly):**
- `telegram_send_message_tool` — `src/telegram/main.py`
- `telegram_send_file_tool` — `src/telegram/main.py`
  Reason: Telegram bot is a standalone LangChain-based bot. It will be rewritten entirely to use the SDK in a future phase, not adapted tool-by-tool.

---

## 9. Dependencies

### Adding Dependencies
```bash
uv add package_name          # Runtime dependency
uv add --dev package_name    # Development dependency
uv add --group cli package_name  # CLI group
```

### Version Pinning
- Use minimum versions in `pyproject.toml` (e.g., `>=1.0.0`)
- Lock versions in `uv.lock` (committed to repo)

### LangChain Dependencies (TO BE REMOVED in Phase 8)
Still present but temporary:
- `langchain`, `langchain-core`, `langchain-ollama`, `langchain-anthropic`, `langchain-openai`
- `langgraph`, `langgraph-checkpoint-sqlite`, `langgraph-sdk`, `langgraph-prebuilt`, `langsmith`
- KEEP: `langchain-mcp-adapters` (MCP integration, small and isolated)