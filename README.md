# Executive Assistant

A general purpose executive assistant agent built with LangChain and LangGraph, with multi-channel support (HTTP, CLI).

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
| **Subagents** | Create and manage specialized subagents with custom skills/tools |
| **Instincts** | 14-domain behavior learning system (unified with profile) |

### Instincts System

The system learns user preferences across 14 behavioral domains:

| Domain | What it captures |
|--------|-----------------|
| `personal` | Name, age, family, bio |
| `work` | Role, company, team, seniority |
| `location` | City, country, timezone |
| `interests` | Topics, hobbies, passions |
| `skills` | Experience, expertise, tech stack |
| `goals` | Objectives, targets, ambitions |
| `constraints` | Limitations, requirements |
| `communication` | Style preferences (concise, bullet points, etc.) |
| `tools` | Preferred tools, software |
| `languages` | Spoken/programming languages |
| `correction` | Corrections to AI responses |
| `workflow` | Habits, processes |
| `lesson` | Things taught to AI |
| `dislikes` | Explicitly unwanted |

Patterns are extracted via LLM from conversations and stored with confidence scores. Profile settings are stored as high-confidence instincts (confidence=1.0). |

### Subagent System

Create specialized subagents that can execute tasks in parallel or sequentially:

```bash
# Create subagent via HTTP
curl -X POST http://localhost:8080/message \
  -H "Content-Type: application/json" \
  -d '{"message": "Create subagent research-agent with skills: planning-with-files, tools: search_web,scrape_url, description: Research assistant", "user_id": "my_user"}'

# Invoke subagent (async - returns immediately, results stored in database)
curl -X POST http://localhost:8080/message \
  -H "Content-Type: application/json" \
  -d '{"message": "Invoke subagent research-agent to research: LangGraph framework", "user_id": "my_user"}'
```

**Key Features:**
- **Async invocation**: `subagent_invoke` schedules task immediately and returns right away
- **Database persistence**: Results stored in `data/jobs_results.db` for cross-process access
- **Progress tracking**: `subagent_progress` tool shows status and retrieves results

**Subagent Tools:**
- `subagent_create` - Create subagent with custom config
- `subagent_invoke` - Execute task asynchronously (schedule now)
- `subagent_list` - List all subagents
- `subagent_progress` - Get task status and results
- `subagent_validate` - Validate subagent config
- `subagent_batch` - Invoke multiple subagents in parallel
- `subagent_schedule` - Schedule one-off or recurring tasks

**Subagent Folder Structure:**
```
data/users/{user_id}/subagents/{subagent_name}/
├── config.yaml       # name, model, skills, tools, system_prompt
└── .mcp.json       # MCP server configs (optional)
```

### Tools

| Category | Tools |
|----------|-------|
| **Subagents** | `subagent_create`, `subagent_invoke`, `subagent_list`, `subagent_progress`, `subagent_validate`, `subagent_batch`, `subagent_schedule` |
| **App Builder** | `app_create`, `app_list`, `app_schema`, `app_delete`, `app_insert`, `app_update`, `app_delete_row`, `app_column_add`, `app_column_delete`, `app_column_rename`, `app_query`, `app_search_fts`, `app_search_semantic`, `app_search_hybrid` |
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

### App Builder

Build structured data apps with SQLite + FTS5 + ChromaDB (hybrid search):

```bash
# Create app with tables
app_create(app="library", tables={
    "books": {
        "title": "TEXT",
        "author": "TEXT", 
        "description": "TEXT",  # Vector indexed
        "category": "TEXT"
    }
})

# Insert data
app_insert(app="library", table="books", data={
    "title": "1984",
    "author": "Orwell", 
    "description": "Dystopian novel about totalitarianism",
    "category": "Sci-Fi"
})

# Search with hybrid (keyword + semantic)
app_search_hybrid(app="library", table="books", column="description", query="future dystopia")
```

**Search Methods:**

| Tool | Description | Best For |
|------|-------------|----------|
| `app_search_fts` | Keyword search (FTS5) | Exact matches |
| `app_search_semantic` | Vector search (ChromaDB) | Conceptual/semantic |
| `app_search_hybrid` | Combined keyword + semantic | Best of both |

**Tech Stack:**

| Component | Technology |
|-----------|------------|
| Database | SQLite with FTS5 |
| Vector Search | ChromaDB |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| Model Cache | ~/.cache/sentence-transformers/ |

**Vector-Indexed Columns:**
- TEXT columns NOT containing: `full_text`, `content`, `body` (excluded for size)
- Examples: `description`, `notes`, `title`, `summary`

**Storage Structure:**
```
data/users/{user_id}/apps/
├── library/
│   ├── data.db              # SQLite + FTS5
│   └── .chromadb/           # ChromaDB vectors
│       └── books_description
└── todo/
    └── data.db
```

### Channels

- **HTTP API** - FastAPI server on port 8080 (`/message`, `/message/stream`, `/health`, `/health/ready`)
- **CLI** - Interactive command-line interface with streaming output

## Quick Start

### Installation

```bash
# Install with all dependencies
uv pip install -e ".[cli,http,dev]"
```

### Running

```bash
# Start HTTP server
uv run ea http

# Start CLI
uv run ea cli
```

### HTTP API

```bash
# Send a message
curl -X POST http://localhost:8080/message \
  -H "Content-Type: application/json" \
  -d '{"message": "hello", "user_id": "my_user"}'

# Health checks
curl http://localhost:8080/health
curl http://localhost:8080/health/ready
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
data/users/{user_id}/
├── memory/
│   ├── memory.db     # SQLite (memories + insights)
│   └── vectors/      # ChromaDB vectors
├── messages/
│   └── messages.db  # Conversation history
└── checkpoints/     # LangGraph checkpoints
```

### Memory Types

| Type | Description | Confidence |
|------|-------------|------------|
| `fact` | Factual information (name, workplace) | 0.2-1.0 |
| `preference` | User preferences (likes dark mode) | 0.2-0.7 |
| `correction` | Corrections to AI responses | 0.7 |
| `workflow` | Habits, processes | 0.2-0.7 |
| `lesson` | Things taught to AI | 0.7-1.0 |

### Two-Layer Memory

1. **Working Memory**: High-confidence memories (≥0.5) - always injected into context
2. **Long-term Memory**: Retrieved on-demand via semantic/keyword search

### Consolidation

The system periodically runs consolidation to:
- Detect contradictions (e.g., "uses Google Workspace" vs "uses Microsoft 365")
- Generate synthesized insights from grouped memories
- Mark superseded memories

Consolidation runs every N messages (configurable via `consolidate_after_messages`).
Insights are stored in `memory.db` and can be retrieved via the API.

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
  consolidate_after_messages: 10  # 0=disabled, N=consolidate every N messages

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
# WEBHOOK_HOST=0.0.0.0
# WEBHOOK_PORT=8080
```

Supported model prefixes for `AGENT_MODEL`: `ollama:`, `ollama-cloud:`, `openai:`, `anthropic:`.

## User Isolation

Each user gets isolated storage:

```
data/users/{user_id}/
├── workspace/        # User files
├── subagents/        # User-created subagents
│   └── {name}/
│       ├── config.yaml
│       └── .mcp.json
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
- **Middleware**: SkillMiddleware, SummarizationMiddleware (with failure detection), HumanInTheLifeMiddleware
- **Storage**: SQLite (messages), ChromaDB (vectors), LangGraph (checkpoints)
- **LLM Providers**: Ollama/Ollama Cloud, OpenAI, Anthropic

## Acknowledgments

This project builds on ideas and research from several projects in the AI agent memory and search space:

| Project | Contribution |
|---------|-------------|
| [LangChain](https://github.com/langchain-ai/langchain) & [LangGraph](https://github.com/langchain-ai/langgraph) | Original agent framework. Executive Assistant started on LangChain/LangGraph before migrating to a custom SDK. LangGraph's checkpointing and graph-based agent orchestration informed the architecture. |
| [claude-mem](https://github.com/thedotmack/claude-mem) | Progressive disclosure pattern for memory retrieval (3-layer workflow: list → load → full). Our skill system and memory context injection follow this token-efficient approach. [claude-mem.ai](https://claude-mem.ai/) |
| [Claude Code](https://code.claude.com) | Auto-memory and insights system. Claude Code's approach to accumulating build commands, debugging insights, architecture notes, and code preferences across sessions directly inspired our MemoryStore's confidence-boosted recall and consolidation system. See [Claude Code Memory docs](https://code.claude.com/docs/en/memory). |
| [ASMR](https://github.com/supermemoryai/supermemory) | Agentic Search and Memory Retrieval from the Supermemory team. Demonstrated that replacing simple vector search with agentic retrieval achieves ~99% on LongMemEval, validating the hybrid (keyword + vector + field) search approach used in our MemoryStore. [Blog post](https://supermemory.ai/blog/we-broke-the-frontier-in-agent-memory-introducing-99-sota-memory-system/) |
| [LongMemEval](https://github.com/xiaowu0162/longmemeval) | Comprehensive benchmark for evaluating long-term interactive memory in chat assistants. Tests information extraction, multi-session reasoning, temporal reasoning, knowledge updates, and abstention. Informs our persona evaluation suite. [Paper](https://arxiv.org/abs/2410.10813) |
| [SQLite](https://sqlite.org/) | Foundation of our entire storage layer — per-user databases, FTS5 full-text search with BM25 scoring, WAL mode for concurrent access, and content-external FTS5 tables with triggers. The most deployed database in the world, and for good reason. |
| [ChromaDB](https://github.com/chroma-core/chroma) | Vector search engine with HNSW indexing. Powers semantic and hybrid search across memories, conversations, and user-created apps. Our benchmark (see `docs/benchmarks/`) confirmed ChromaDB's HNSW is 78x faster than brute-force at 100k rows, making it essential for interactive applications. [trychroma.com](https://www.trychroma.com/) |
| [Firecrawl](https://github.com/mendableai/firecrawl) | Web scraping and search API. Powers our `scrape_url`, `search_web`, `map_url`, `crawl_url`, and `firecrawl_agent` tools. We use the Firecrawl CLI via our CLIToolAdapter pattern, supporting both cloud and self-hosted deployments. [firecrawl.dev](https://firecrawl.dev/) |
| [Agent-Browser](https://agent-browser.dev) | Pure Rust CLI for browser automation by Vercel Labs. Powers our 20+ browser tools (`browser_open`, `browser_click`, `browser_snapshot`, etc.) using ref-based element selection (@e1, @e2) for deterministic AI interaction with ~50ms command latency. |
| [Agent Skills](https://agentskills.io) | Open format for giving agents new capabilities and expertise via folders of instructions, scripts, and resources. Originally developed by Anthropic. Our skill system (`skills_list`, `skills_load`, SkillMiddleware) follows the Agent Skills specification for on-demand capability loading with progressive disclosure. [GitHub](https://github.com/agentskills/agentskills) |
