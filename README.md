# Executive Assistant

A general purpose executive assistant agent built with LangChain and LangGraph, with multi-channel support (HTTP, CLI, Telegram).

## Features

### Core Capabilities

| Feature | Description |
|---------|-------------|
| **AI Chat** | Conversational AI with context awareness |
| **Agent Pooling** | Per-user agent pool for concurrent requests with reusable thread context |
| **Memory** | Persistent conversation history with SQLite + ChromaDB (semantic + keyword search) |
| **Checkpoints** | LangGraph checkpoint for conversation state persistence |
| **Skills** | Extensible skill system with progressive disclosure |
| **MCP Integration** | Dynamic Model Context Protocol server tools per user |

### Tools

| Category | Tools |
|----------|-------|
| **Filesystem** | `list_files`, `read_file`, `write_file`, `edit_file`, `delete_file` (HITL) |
| **File Search** | `files_glob_search` (e.g., `*.py`, `**/*.json`), `files_grep_search` (regex) |
| **Shell** | `shell_execute` (restricted to: `python3`, `node`, `echo`, `date`, `whoami`, `pwd`) |
| **Memory** | `memory_get_history`, `memory_search` |
| **Todos** | `todos_list`, `todos_add`, `todos_update`, `todos_delete`, `todos_extract` |
| **Contacts** | `contacts_list`, `contacts_get`, `contacts_add`, `contacts_update`, `contacts_delete`, `contacts_search` |
| **Time** | `time_get` with timezone support |
| **Web** | `scrape_url`, `search_web`, `map_url`, `crawl_url`, `get_crawl_status`, `cancel_crawl` (requires `FIRECRAWL_API_KEY` or `FIRECRAWL_BASE_URL`) |
| **Email** | `email_connect`, `email_disconnect`, `email_accounts`, `email_list`, `email_get`, `email_search`, `email_send`, `email_sync` |
| **Skills** | `skills_load`, `skills_list`, `sql_write_query` (skill-gated) |
| **MCP** | `mcp_list`, `mcp_reload`, `mcp_tools` |

### Progressive Disclosure

Skills use a progressive disclosure pattern to optimize token usage:

1. **List Skills** (`skills_list`) - See available skills with brief descriptions
2. **Load Skill** (`skills_load`) - Load full skill content when needed

This follows the same pattern as [claude-mem](https://github.com/thedotmack/claude-mem)'s 3-layer memory workflow for token-efficient context retrieval.

### Channels

- **HTTP API** - FastAPI server on port 8000 (`/message`, `/message/stream`, `/health`, `/health/ready`)
- **CLI** - Interactive command-line interface with streaming output
- **Telegram** - Telegram bot integration (polling and webhook modes)

## Quick Start

### Installation

```bash
# Install with all dependencies
uv pip install -e ".[cli,http,telegram,dev]"
```

### Running

```bash
# Start HTTP server
uv run ea http

# Start CLI
uv run ea cli

# Start Telegram bot
uv run ea telegram
```

### HTTP API

```bash
# Send a message
curl -X POST http://localhost:8000/message \
  -H "Content-Type: application/json" \
  -d '{"message": "hello", "user_id": "my_user"}'

# Health checks
curl http://localhost:8000/health
curl http://localhost:8000/health/ready
```

### CLI Commands

- `/help` - Show commands
- `/clear` - Clear local CLI message buffer
- `/quit` or `/exit` - Exit CLI
- End a line with `\` for multi-line input

## Memory System

The memory system is inspired by [claude-mem](https://github.com/thedotmack/claude-mem) and uses hybrid retrieval.

### Tech Stack

| Component | Technology |
|-----------|------------|
| **Message Storage** | SQLite with FTS5 (full-text search) |
| **Semantic Search** | ChromaDB (vector database) |
| **Checkpoints** | LangGraph SQLite checkpointer |
| **Pattern** | Progressive disclosure (3-layer workflow) |

### Storage Layout

```text
data/users/{user_id}/.conversation/
├── messages.db      # SQLite with FTS5
├── vectors/         # ChromaDB vectors
└── checkpoints.db   # LangGraph checkpoints (when enabled)
```

## Configuration

Configuration is in `config.yaml`.

```yaml
# Filesystem
filesystem:
  enabled: true
  root_path: "data/users/{user_id}/workspace"
  max_file_size_mb: 10

# Shell (restricted commands)
shell_tool:
  enabled: true
  allowed_commands:
    - python3
    - node
    - echo
    - date
    - whoami
    - pwd

# Memory
memory:
  messages:
    enabled: true
  checkpointer:
    retention_days: 0  # 0=disabled, -1=forever

# Skills
skills:
  directory: "src/skills"

# Email Sync
email_sync:
  enabled: true
  interval_minutes: 5
  batch_size: 100
  backfill_limit: 1000

# MCP
mcp:
  enabled: true
  idle_timeout_minutes: 30
```

### Environment Variables

Create `.env` file:

```bash
# Model/provider selection
AGENT_MODEL=ollama-cloud:minimax-m2.5

# Provider credentials/endpoints (set what you use)
OLLAMA_BASE_URL=https://ollama.com
OLLAMA_API_KEY=
OPENAI_API_KEY=
ANTHROPIC_API_KEY=

# Web tools (Firecrawl)
FIRECRAWL_API_KEY=
# FIRECRAWL_BASE_URL=http://localhost:3002  # self-hosted Firecrawl

# Optional observability
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_HOST=

# Telegram
TELEGRAM_BOT_TOKEN=
TELEGRAM_MODE=polling
# TELEGRAM_MODE=webhook
# TELEGRAM_WEBHOOK_URL=https://your-domain.example
# TELEGRAM_SECRET=your-webhook-secret
# WEBHOOK_HOST=0.0.0.0
# WEBHOOK_PORT=8080
```

Supported model prefixes for `AGENT_MODEL`: `ollama:`, `ollama-cloud:`, `openai:`, `anthropic:`.

## User Isolation

Each user gets isolated storage:

```text
data/users/{user_id}/
├── workspace/        # User files
├── skills/           # User custom skills
├── email/
│   └── emails.db     # User email store
├── .mcp.json         # User MCP server config (optional)
└── .conversation/
    ├── messages.db
    ├── vectors/
    └── checkpoints.db
```

## Email Integration

Connect email accounts with IMAP/SMTP (Gmail, Outlook, iCloud, Yahoo).

### Tools

| Tool | Description |
|------|-------------|
| `email_connect` | Connect email account (auto-backfills on connect) |
| `email_disconnect` | Remove email account |
| `email_accounts` | List connected accounts |
| `email_list` | List emails from folder |
| `email_get` | Get full email content |
| `email_search` | Search emails by subject/sender |
| `email_send` | Send new email, reply, or reply all |
| `email_sync` | Manual sync (new/full modes) |

### Auto-Sync

- On connect: full backfill (newest to earliest)
- Background: polls for new emails every `email_sync.interval_minutes`

## MCP Integration

User MCP config is loaded from `data/users/{user_id}/.mcp.json`.

Example:

```json
{
  "mcpServers": {
    "example": {
      "command": "uvx",
      "args": ["some-mcp-server"],
      "transport": "stdio"
    }
  }
}
```

Use tools:

- `mcp_list` - list configured servers and status
- `mcp_tools` - show tools available from MCP servers
- `mcp_reload` - reload config after editing `.mcp.json`

## Development

```bash
# Run tests
uv run pytest

# Lint
uv run ruff check src/

# Type check
uv run mypy src/
```

## Architecture

- **Agent**: LangChain `create_agent()` with tool calling
- **Concurrency**: Per-user `AgentPool` reusing agent instances and thread IDs
- **Middleware**: SkillMiddleware, SummarizationMiddleware, HumanInTheLoopMiddleware
- **Storage**: SQLite (messages), ChromaDB (vectors), LangGraph (checkpoints)
- **LLM Providers**: Ollama/Ollama Cloud, OpenAI, Anthropic
