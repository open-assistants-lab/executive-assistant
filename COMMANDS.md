# Executive Assistant - Available Commands

## Overview

This document lists all available commands and endpoints for interacting with the Executive Assistant across different interfaces (CLI, Telegram, HTTP API).

---

## CLI Commands (Typer)

**Usage:** `uv run ea <command> [options]`

| Command | Description | Options |
|---------|-------------|---------|
| **`ea config`** | Show current configuration | None |
| **`ea message "<text>"`** | Send a single message and exit | `--user`, `-u` (User ID, default: "default")<br>`--thread`, `-t` (Thread ID) |
| **`ea cli`** | Start interactive session | `--user`, `-u` (User ID, default: "default")<br>`--thread`, `-t` (Thread ID) |
| **`ea models`** | List available LLM providers | None |
| **`ea http`** | Start HTTP API server | `--host`, `-h` (Host, default: "0.0.0.0")<br>`--port`, `-p` (Port, default: 8000)<br>`--reload` (Hot reload) |
| **`ea telegram`** | Start Telegram bot | None |
| **`ea acp`** | Start ACP server (IDE integration) | None |

### Interactive CLI Commands

**Inside `ea cli` interactive session:**

| Command | Description |
|---------|-------------|
| `exit` or `quit` | Exit the interactive session |
| `/help` | Show available commands and tools |
| `/model [provider/model]` | Show or change model |
| `/clear` | Clear conversation history (starts new thread) |

**Note:** All administrative commands start with `/` in interactive mode.

---

## Administrative Commands (Cross-Interface)

These commands work across **CLI, HTTP, and Telegram** interfaces:

| Command | CLI | HTTP | Telegram | Description |
|---------|-----|-----|----------|-------------|
| **`/help`** | `ea help` | `GET /api/v1/commands/help` | `/help` | Show available commands and tools |
| **`/model [model]`** | `ea model [provider/model]` | `GET/POST /api/v1/commands/model` | `/model [provider/model]` | Show or change model |
| **`/clear`** | `ea clear [-u user_id]` | `POST /api/v1/commands/clear` | `/clear` | Clear conversation history |

**Usage Examples:**

```bash
# CLI
uv run ea help                              # Show help
uv run ea model openai/gpt-4o               # Change model
uv run ea model                              # Show current model
uv run ea clear -u user-123                   # Clear history for user

# HTTP API
curl http://localhost:8000/api/v1/commands/help
curl http://localhost:8000/api/v1/commands/model
curl -X POST http://localhost:8000/api/v1/commands/model \
  -H "Content-Type: application/json" \
  -d '{"model": "openai/gpt-4o", "user_id": "user-123"}'
curl -X POST http://localhost:8000/api/v1/commands/clear \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user-123"}'

# Telegram
/start          # Start conversation
/help           # Show commands
/model          # Show current model
/model ollama/qwen3-coder-next  # Change model
/clear          # Clear history
```

---

## Telegram Bot Commands

**Usage:** Send commands as messages in Telegram

| Command | Description | Usage |
|---------|-------------|-------|
| **`/start`** | Start conversation, show welcome message | `/start` |
| **`/help`** | Show available commands | `/help` |
| **`/model`** | Show or change LLM model | `/model` (show current)<br>`/model openai/gpt-4o` (change model) |
| **`/clear`** | Clear conversation history | `/clear` |

**Note:** Any other text message is treated as a conversation message to the agent.

---

## HTTP API Endpoints

**Base URL:** `http://localhost:8000/api/v1` (configurable via `--host` and `--port`)

### Administrative Endpoints

| Endpoint | Method | Description | Request/Response |
|----------|--------|-------------|------------------|
| **`/commands/help`** | GET | Show help text with available commands | Response: `{help_text: "..."}` |
| **`/commands/model`** | GET | Get current model for user | Response: `{provider: "...", model: "...", full_model: "..."}` |
| **`/commands/model`** | POST | Change model for user | Request: `{model: "openai/gpt-4o", user_id: "..."}`<br>Response: `{message: "Model changed to: openai/gpt-4o"}` |
| **`/commands/clear`** | POST | Clear conversation history | Request: `{user_id: "...", thread_id?: "..."}`<br>Response: `{message: "...", new_thread_id: "..."}` |

### Health Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Overall health check |
| `/health/ready` | GET | Readiness check (is server ready to accept requests?) |
| `/health/live` | GET | Liveness check (is server alive?) |

### Chat Endpoints

| Endpoint | Method | Description | Request Body |
|----------|--------|-------------|--------------|
| **`/message`** | POST | Send message, get response | `{message: str, user_id: str, thread_id?: str, stream?: bool}` |
| **`/message/stream`** | POST | Send message, stream response (Server-Sent Events) | `{message: str, user_id: str, thread_id?: str}` |
| **`/summarize`** | POST | Summarize text (bypasses agent) | `{text: str, max_length?: int}` |

### `/message` Response

```json
{
  "content": "Agent response text",
  "thread_id": "user-123-cli",
  "tool_calls": [
    {
      "id": "tool_id",
      "name": "web_search",
      "args": {"query": "..."}
    }
  ],
  "todos": [
    {
      "content": "Task description",
      "status": "completed",
      "display_status": "✅"
    }
  ]
}
```

### `/message/stream` Response

Server-Sent Events (SSE) stream with event types:
- `{"type": "tool_call", "tool": "...", "args": {...}}`
- `{"type": "content", "content": "...", "is_tool_result": bool}`
- `{"type": "todos", "todos": [...]}`
- `{"type": "middleware", "name": "...", "status": "..."}`
- `{"type": "thread", "thread_id": "..."}`
- `{"type": "done"}`

---

## Command Reference by Interface

### CLI (Command Line)

```bash
# Show configuration
uv run ea config

# Send single message
uv run ea message "What is the weather in Sydney?"
uv run ea message "Plan: 1) Research, 2) Summarize" --user my-user

# Interactive session
uv run ea cli
# Inside: type messages, 'exit' to quit, 'clear' to reset

# List available models
uv run ea models

# Start HTTP server
uv run ea http
uv run ea http --port 8080 --reload

# Start Telegram bot
uv run ea telegram

# Start ACP server
uv run ea acp
```

### Telegram Bot

```bash
# Start bot
uv run ea telegram

# In Telegram (as user):
/start          # Start conversation
/help           # Show commands
/model          # Show current model
/model ollama/qwen3-coder-next  # Change model
/clear          # Clear history
# Any text      # Chat with agent
```

### HTTP API

```bash
# Start server
uv run ea http

# Administrative commands
# Get help
curl http://localhost:8000/api/v1/commands/help

# Get current model
curl http://localhost:8000/api/v1/commands/model?user_id=user-123

# Change model
curl -X POST http://localhost:8000/api/v1/commands/model \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai/gpt-4o",
    "user_id": "user-123"
  }'

# Clear conversation history
curl -X POST http://localhost:8000/api/v1/commands/clear \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user-123"
  }'

# Send message
curl -X POST http://localhost:8000/api/v1/message \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is the weather in Sydney?",
    "user_id": "user-123",
    "thread_id": "custom-thread"
  }'

# Stream message
curl -X POST http://localhost:8000/api/v1/message/stream \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is the weather in Sydney?",
    "user_id": "user-123"
  }'

# Summarize text
curl -X POST http://localhost:8000/api/v1/summarize \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Long text to summarize...",
    "max_length": 200
  }'
```

---

## Built-in Tools (Available to Agent)

The agent has access to these tools (regardless of interface):

| Tool | Description |
|------|-------------|
| **`get_current_time`** | Get current time in any timezone |
| **`web_search`** | Search the web (Tavily or Firecrawl) |
| **`web_scrape`** | Scrape content from a URL |
| **`web_crawl`** | Crawl a website (multiple pages) |
| **`web_map`** | Map a website (discover all URLs) |
| **`memory_search`** | Search memory store |
| **`memory_timeline`** | Get timeline context around a memory |
| **`memory_get`** | Get full memory details by ID |
| **`memory_save`** | Save information to memory |
| **`write_todos`** | Create/manage todo list (built-in) |

---

## Middleware Features

The agent has middleware that provides:

| Feature | Trigger | Output |
|---------|---------|--------|
| **Memory Context** | Every query | Injects relevant memories into prompt |
| **Memory Learning** | After conversation | Extracts and saves memories |
| **Todo Display** | After agent | Enhances todo display with progress indicators |
| **Summarization** | When token limit exceeded | Compresses conversation history |
| **Logging** | All actions | Logs to `/data/logs/agent-<date>.jsonl` |
| **Rate Limiting** | All actions | Enforces per-user rate limits |

---

## Thread ID Management

**Current Behavior:**

| Interface | Default Thread ID Format | Example |
|----------|-------------------------|---------|
| **CLI** | `{user_id}-cli` | `default-cli` |
| **CLI (interactive)** | `{user_id}-interactive` | `default-interactive` |
| **Telegram** | `telegram-{user_id}` | `telegram-123456789` |
| **HTTP API** | `{user_id}-default` | `default-default` |

**After Phase 7 (Daily Checkpoint Rotation):**

| Interface | Thread ID Format | Example |
|----------|------------------|---------|
| **All interfaces** | `{user_id}-{date}` | `user-123-2026-02-18` |

**Planned (Phase 7):** Progressive disclosure tools for accessing old checkpoints:
- `history_list(days)` - List available dates
- `history_load(date)` - Load conversation from specific date
- `history_search(query)` - Search across conversations

---

## Missing Commands (Not Yet Implemented)

Based on TODO.md Phase 7 CLI Experience section:

| Planned Command | Description | Status |
|-----------------|-------------|--------|
| `/model <model>` | Change model mid-session | ❌ Not in CLI (only Telegram) |
| Command history (up/down arrows) | Navigate command history | ❌ Not implemented |
| Auto-completion | Tab-complete commands | ❌ Not implemented |
| Multi-line input | Multi-line message support | ❌ Not implemented |

**Note:** The TODO.md mentions these as future improvements for the CLI, but they are not currently implemented.
