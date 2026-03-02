# Executive Assistant

A general purpose executive assistant agent using LangChain create_agent() with support for multiple channels (HTTP, CLI, Telegram).

## Features

### Core Capabilities

| Feature | Description |
|---------|-------------|
| **AI Chat** | Conversational AI with context awareness |
| **Memory** | Persistent conversation history with SQLite + ChromaDB (semantic search) |
| **Checkpoints** | LangGraph checkpoint for conversation state persistence |
| **Skills** | Extensible skill system with progressive disclosure |

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
| **Web** | `scrape_url`, `search_web`, `map_url`, `crawl_url`, `get_crawl_status`, `cancel_crawl` (requires FIRECRAWL_API_KEY) |
| **Email** | `email_connect`, `email_disconnect`, `email_accounts`, `email_list`, `email_get`, `email_search`, `email_send`, `email_sync` |
| **Skills** | `skills_load`, `skills_list`, `sql_write_query` (skill-gated) |

### Progressive Disclosure

Skills use a progressive disclosure pattern to optimize token usage:

1. **List Skills** (`skills_list`) - See available skills with brief descriptions
2. **Load Skill** (`skills_load`) - Load full skill content when needed

This follows the same pattern as [claude-mem](https://github.com/thedotmack/claude-mem)'s 3-layer memory workflow for token-efficient context retrieval.

### Channels

- **HTTP API** - FastAPI server on port 8000 (`/message`, `/message/stream`, `/health`)
- **CLI** - Interactive command-line interface with rich UI
- **Telegram** - Telegram bot integration

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

# Health check
curl http://localhost:8000/health
```

## Memory System

The memory system is inspired by [claude-mem](https://github.com/thedotmack/claude-mem) - a persistent memory compression system for Claude Code.

### Tech Stack

| Component | Technology |
|-----------|------------|
| **Message Storage** | SQLite with FTS5 (full-text search) |
| **Semantic Search** | ChromaDB (vector database) |
| **Checkpoints** | LangGraph SQLite checkpointer |
| **Pattern** | Progressive disclosure (3-layer workflow) |

### Progressive Disclosure

Inspired by claude-mem's token-efficient memory retrieval:

1. **List** - View available skills/memory index
2. **Search** - Get relevant results with metadata
3. **Load** - Fetch full content only when needed

This minimizes token usage by loading detailed content only when relevant.

### Architecture

```
data/users/{user_id}/.conversation/
├── messages.db      # SQLite with FTS5
├── vectors/        # ChromaDB for semantic search
└── checkpoints.db  # LangGraph checkpoint
```

## Configuration

Configuration is in `config.yaml`:

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

# Tools
tools:
  firecrawl:
    # Set via FIRECRAWL_API_KEY env var
    # For self-hosted: FIRECRAWL_BASE_URL

# Skills
skills:
  directory: "src/skills"

# Email Sync
email_sync:
  enabled: true
  interval_minutes: 5
  batch_size: 100
  backfill_limit: 1000
```

### Environment Variables

Create `.env` file:

```bash
# Required
OLLAMA_BASE_URL=http://localhost:11434
MODEL=minimax-m2.5

# Optional
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_SECRET_KEY=...
TELEGRAM_BOT_TOKEN=...
```

## User Isolation

Each user gets isolated storage:

```
data/users/{user_id}/
├── workspace/        # User's files
├── skills/          # User's custom skills
├── email/           # User's email data
│   └── emails.db    # SQLite with emails + accounts
└── .conversation/
    ├── messages.db  # SQLite with FTS5
    ├── vectors/    # ChromaDB for semantic search
    └── checkpoints.db
```

## Email Integration

Connect email accounts with IMAP/SMTP. Supports Gmail, Outlook, iCloud, Yahoo.

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

### Usage

```
# Connect email account
connect email yourname@gmail.com with password your_app_password

# List emails
list emails from INBOX

# Send email
send email to john@example.com subject "Hello" body "Hi there"

# Reply to email
reply to email <message_id> with message "Thanks!"

# Reply all
reply all to email <message_id>
```

### Auto-Sync

- On connect: Full backfill (newest → earliest)
- Background: Polls for new emails every N minutes (config.yaml)
data/users/{user_id}/
├── workspace/        # User's files
├── skills/          # User's custom skills
├── .conversation/
│   ├── messages.db  # SQLite with FTS5
│   ├── vectors/    # ChromaDB for semantic search
│   └── checkpoints.db
```

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

- **Agent**: LangChain `create_agent()` with custom tools
- **Middleware**: SkillMiddleware, SummarizationMiddleware, HumanInTheLoopMiddleware
- **Storage**: SQLite (messages), ChromaDB (vectors), LangGraph (checkpoints)
- **LLM**: Ollama with minimax-m2.5 model
- **Memory Inspiration**: [claude-mem](https://github.com/thedotmack/claude-mem)
