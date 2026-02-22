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
| **Filesystem** | `list_files`, `read_file`, `write_file`, `edit_file`, `delete_file` |
| **File Search** | `glob_search` (e.g., `*.py`, `**/*.json`), `grep_search` (regex) |
| **Shell** | `run_shell` (restricted to: `python3`, `node`, `echo`, `date`, `whoami`, `pwd`) |
| **Memory** | `get_conversation_history`, `search_conversation_hybrid` |
| **Todos** | `write_todos` for multi-step task tracking |

### Progressive Disclosure

Skills use a progressive disclosure pattern to optimize token usage:

1. **List Skills** (`list_skills`) - See available skills with brief descriptions
2. **Load Skill** (`load_skill`) - Load full skill content when needed

This follows the same pattern as [claude-mem](https://github.com/thedotmack/claude-mem)'s 3-layer memory workflow for token-efficient context retrieval.

### Channels

- **HTTP API** - FastAPI server on port 8000
- **CLI** - Interactive command-line interface
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
    retention_days: 30

# Skills
skills:
  directory: "src/skills"
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
