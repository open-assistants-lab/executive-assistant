# Executive Assistant Technical Architecture Documentation

**Version:** 1.4.0
**Last Updated:** February 4, 2026
**Project:** Executive Assistant - Multi-channel AI Agent Platform

**Recent Updates (February 2026):**
- ✅ **Implemented Unified Context System** - 4-Pillar architecture for comprehensive user context
  - **Memory Pillar**: Embedded memories with FTS5 full-text search (SQLite)
  - **Journal Pillar**: Time-series reflection logs with automatic rollups (SQLite + FTS5)
  - **Instincts Pillar**: Behavioral pattern learning with confidence scoring (JSONL + snapshot)
  - **Goals Pillar**: Long-term objectives with progress tracking (SQLite with version history)
  - Unified query interface across all pillars
  - Integrated into system prompts for enhanced context awareness
- ✅ **Implemented Journal System** - Time-series reflection with intelligent rollups
  - Daily journal entries with rich text formatting
  - Automatic time-series rollups (hourly → daily → weekly → monthly)
  - Full-text search across all journal entries
  - Context-aware retrieval for relevant historical reflections
  - Storage: `data/users/{thread_id}/journal/journal.db` (SQLite with FTS5)
- ✅ **Implemented Goals System** - Long-term objective tracking
  - Create, update, track, and complete goals
  - Progress tracking with percentage completion
  - Automatic version history for all goal changes
  - Deadline management with reminders
  - Status workflow: draft → active → completed → cancelled
  - Storage: `data/users/{thread_id}/goals/goals.db` (SQLite with versioning)
- ✅ **Implemented Onboarding System** - Structured profile creation
  - Guided profile setup with 5 key sections
  - Extracts user context (name, role, preferences, communication style, goals)
  - Automatic memory creation from onboarding responses
  - One-time setup per user thread
  - Context injection into system prompts
- ✅ **Implemented User MCP Management** - Per-conversation MCP server management
  - User-managed MCP servers (stdio + HTTP/SSE)
  - Tiered tool loading (user > admin priority)
  - Tool deduplication and hot-reload with `clear_mcp_cache()`
  - Automatic backup/restore with rotation (keeps last 5)
  - Security validation (HTTPS enforcement, server name validation, command injection prevention)
  - Storage: `data/users/{thread_id}/mcp/mcp.json` and `mcp_remote.json`
- ✅ **Implemented MCP-Skill HITL Integration** - Human-in-the-loop skill loading
  - Auto-detection of relevant skills when adding MCP servers
  - Pending skill proposals with approval workflow
  - Skill mapping database (fetch, github, clickhouse, filesystem, brave-search, puppeteer)
  - 5 HITL workflow tools: `mcp_list_pending_skills`, `mcp_approve_skill`, `mcp_reject_skill`, `mcp_edit_skill`, `mcp_show_skill`
  - Enhanced `mcp_add_server` creates proposals, `mcp_reload` loads approved skills
  - Storage: `data/users/{thread_id}/mcp/pending_skills/{skill_name}.json`
  - 60 comprehensive tests (33 storage/mapping + 27 workflow tools)
  - Files: `storage/mcp_skill_storage.py`, `tools/mcp_skill_mapping.py`, enhanced `tools/user_mcp_tools.py`

**Previous Updates (January 2026):**
- ✅ **Implemented Instinct System** - Automatic behavioral pattern learning
  - Observer: Pattern detection (corrections, repetitions, preferences)
  - Injector: Context injection into system prompts
  - Evolver: Clustering instincts into skills
  - Profiles: 6 pre-built personality presets
- ✅ Migrated to LangChain agent runtime (removed custom nodes.py)
- ✅ Implemented token usage tracking for HTTP channel (OpenAI/Anthropic)
- ✅ Added comprehensive middleware stack (summarization, retry, status updates)
- ✅ Fixed progressive disclosure bug (all 87 tools now available by default)
- ✅ Added ThreadContextMiddleware for async context propagation
- ✅ Enhanced error logging with comprehensive tracebacks
- ✅ Fixed HTTP channel non-streaming endpoint
- ✅ HTTP channel now bypasses allowlist (frontend auth pattern)

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Technology Stack](#technology-stack)
3. [Architecture Overview](#architecture-overview)
4. [Code Structure](#code-structure)
5. [Core Components](#core-components)
6. [Data Flow](#data-flow)
7. [Storage Architecture](#storage-architecture)
8. [Key Libraries & Frameworks](#key-libraries--frameworks)
9. [Configuration Management](#configuration-management)
10. [Deployment Architecture](#deployment-architecture)
11. [Testing Strategy](#testing-strategy)

---

## Project Overview

Executive Assistant is a **multi-channel AI agent platform** built on LangGraph that implements a ReAct (Reasoning + Acting) agent pattern. It provides intelligent task execution across multiple communication channels (Telegram, HTTP) with persistent state management, privacy-first multi-tenant storage, and a comprehensive toolkit for data operations.

**Key Characteristics:**
- **LangChain Agent Runtime**: High-level agent creation with middleware stack
- **ReAct Agent Pattern**: Reasoning → Action → Observation cycle
- **Multi-Channel Support**: Telegram bot and HTTP REST API with SSE streaming
- **Privacy-First Storage**: Thread-only context with per-thread data isolation
- **Tool-Based Intelligence**: All registered tools available in every conversation (count varies by configured MCP servers)
- **Instincts System**: Automatic behavioral pattern learning with confidence scoring
- **State Persistence**: PostgreSQL-backed checkpointing for conversation memory
- **Token Tracking**: Automatic usage monitoring for cost control (provider-dependent)
- **Production-Ready**: Middleware stack with summarization, retry logic, status updates, and call limits

---

## Technology Stack

### Core Frameworks
| Category | Technology | Purpose |
|----------|-----------|---------|
| **Orchestration** | LangGraph v1.0.6+ | Agent workflow/state management |
| **LLM Abstraction** | LangChain v0.3.27+ | Unified LLM interface |
| **LLM Runtime** | LangGraph-Prebuilt v1.0.6+ | Prebuilt agent components |
| **HTTP Server** | FastAPI v0.115.0+ | REST API with streaming |
| **Async Runtime** | uvicorn | ASGI server |

### LLM Providers
- **Anthropic**: Claude models (Claude Haiku/Sonnet)
- **OpenAI**: GPT models (GPT-4o, GPT-4o-mini)
- **Zhipu AI**: GLM-4 models
- **Ollama**: Local/Cloud OpenAI-compatible models

### Data Storage
| Type | Technology | Purpose |
|------|-----------|---------|
| **State/Checkpoint** | PostgreSQL (via asyncpg) | Conversation persistence |
| **Vector Database** | LanceDB | Semantic search/knowledge base |
| **Tabular Data** | SQLite (sqlite_db_storage.py, tdb_tools.py) | Transactional, permanent data (timesheets, CRM, tasks) |
| **Memories** | SQLite + FTS5 (mem_storage.py) | Embedded memories with full-text search |
| **Journal** | SQLite + FTS5 (journal_storage.py) | Time-series reflection logs with rollups |
| **Goals** | SQLite with versioning (goals_storage.py) | Long-term objectives with progress tracking |
| **Instincts** | JSONL + snapshot (instinct_storage.py) | Behavioral patterns with confidence scoring |
| **File Storage** | Local filesystem | Document/file storage |
| **Metadata Registry** | PostgreSQL | File/DB ownership tracking |

### MCP Configuration Storage
| Type | Location | Purpose |
|------|----------|---------|
| **Admin MCP** | `data/admins/mcp.json` | Admin-supplied MCP servers (applies globally) |

### Supporting Libraries
- **Job Scheduling**: APScheduler v3.10.0+
- **Task Queue**: temporalio v1.21.1+ (optional)
- **OCR**: Surya-OCR / PaddleOCR (optional, Linux x86_64)
- **Data Processing**: Pandas v2.2.0+, PyArrow
- **HTTP Client**: httpx
- **Logging**: loguru
- **Configuration**: Pydantic v2.12.5+, PyYAML

### Development Tools
- **Testing**: pytest v9.0.2+, pytest-asyncio
- **Package Management**: uv (Python 3.11+)
- **Containerization**: Docker, docker-compose

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         Channels Layer                          │
├───────────────────────┬─────────────────────────────────────────┤
│   TelegramChannel      │         HttpChannel                    │
│  (python-telegram-bot)│       (FastAPI + SSE)                  │
└───────────┬───────────┴───────────────────┬─────────────────────┘
            │                               │
            └───────────────┬───────────────┘
                            │
                ┌───────────▼───────────┐
                │   Middleware Stack    │
                │ • Summarization      │
                │ • Call Limits        │
                │ • Retry Logic        │
                │ • Todo Tracking      │
                │ • Status Updates     │
                └───────────┬───────────┘
                            │
                ┌───────────▼─────────────┐
                │   LangGraph ReAct      │
                │   Agent Graph          │
                │ ┌───────────────────┐ │
                │ │    call_model      │ │
                │ │    (LLM Reasoning) │ │
                │ └─────────┬─────────┘ │
                │           │             │
                │ ┌─────────▼─────────┐ │
                │ │   call_tools      │ │
                │ │ (Tool Execution)  │ │
                │ └─────────┬─────────┘ │
                └───────────┼────────────┘
                            │
          ┌─────────────────┼──────────────────┐
          │                 │                  │
    ┌─────▼─────┐   ┌──────▼──────┐   ┌──────▼──────┐
    │   File    │   │ Database    │   │   Vector    │
    │  Sandbox  │   │  Tools      │   │   Store     │
    └───────────┘   └─────────────┘   └─────────────┘
          │                 │                  │
          └─────────────────┼──────────────────┘
                            │
                ┌───────────▼─────────────┐
                │   Storage Backends     │
                │ • File System         │
                │ • SQLite             │
                │ • LanceDB             │
                │ • PostgreSQL          │
                └───────────────────────┘
```

### ReAct Agent Flow

The agent follows the **ReAct (Reasoning + Acting)** pattern:

1. **Reason**: LLM analyzes user request and decides on actions
2. **Act**: Execute tools (file operations, database queries, web search, etc.)
3. **Observe**: Process tool results and update context
4. **Loop**: Repeat until task complete or iteration limit reached

**State Transition:**
```
[Start] → [call_model] → [has tool_calls?] ────No──→ [END]
                    │                             Yes
                    ↓
               [call_tools] → [increment_iterations]
                    │
                    └──────────→ [call_model]
```

---

## Code Structure

```
executive_assistant/
├── src/executive_assistant/                    # Main application package
│   ├── agent/                     # Agent logic/runtime
│   │   ├── state.py              # AgentState TypedDict
│   │   ├── prompts.py            # System prompts for reasoning
│   │   ├── langchain_agent.py    # LangChain agent runtime
│   │   ├── status_middleware.py   # Real-time progress tracking
│   │   ├── middleware_debug.py    # Debug middleware
│   │   ├── todo_display.py       # Todo list display logic
│   │   ├── flow_mode.py          # Flow mode toggles
│   │   ├── checkpoint_utils.py   # Checkpoint management
│   │   └── langchain_state.py    # LangChain state wrapper
│   │
│   ├── channels/                  # Communication channels
│   │   ├── base.py              # Abstract BaseChannel class
│   │   ├── telegram.py          # Telegram bot implementation
│   │   ├── http.py              # FastAPI HTTP channel
│   │   └── management_commands.py # CLI commands (/mem, /vdb, /tdb, /file)
│   │
│   ├── storage/                   # Data persistence layer
│   │   ├── checkpoint.py        # LangGraph PostgreSQL checkpointer
│   │   ├── file_sandbox.py      # Secure file operations (thread-scoped)
│   │   ├── db_storage.py        # Legacy DuckDB TDB storage (deprecated)
│   │   ├── tdb_tools.py         # SQLite TDB tool implementations
│   │   ├── sqlite_db_storage.py # SQLite backend (context + shared)
│   │   ├── vdb_tools.py         # Vector database tool implementations
│   │   ├── lancedb_storage.py   # LanceDB vector database backend
│   │   ├── user_registry.py     # Conversation logs & ownership tracking
│   │   ├── meta_registry.py     # Metadata/ownership tracking
│   │   ├── reminder.py          # Reminder scheduling
│   │   ├── scheduled_flows.py    # APScheduler integration
│   │   ├── chunking.py         # Document chunking for vector database
│   │   ├── mem_storage.py      # Memory pillar storage (SQLite + FTS5)
│   │   ├── journal_storage.py  # Journal pillar storage (SQLite + FTS5)
│   │   ├── goals_storage.py    # Goals pillar storage (SQLite + versioning)
│   │   ├── instinct_storage.py # Instincts pillar storage (JSONL + snapshot)
│   │   └── workers.py          # Async worker pool
│   │
│   ├── tools/                    # LangChain tool implementations
│   │   ├── registry.py          # Tool registry (get_all_tools)
│   │   ├── python_tool.py       # Python code execution (sandboxed)
│   │   ├── time_tool.py        # Timezone-aware time queries
│   │   ├── reminder_tools.py   # Reminder CRUD operations
│   │   ├── search_tool.py      # Web search (SearXNG)
│   │   ├── ocr_tool.py        # OCR image/PDF text extraction
│   │   ├── mem_tools.py       # Memory pillar tools (6 tools)
│   │   ├── journal_tools.py   # Journal pillar tools (8 tools)
│   │   ├── goals_tools.py     # Goals pillar tools (10 tools)
│   │   ├── onboarding_tools.py # Onboarding tools (5 tools)
│   │   ├── context_query_tool.py # Unified 4-pillar context query
│   │   ├── firecrawl_tool.py   # Firecrawl web scraping
│   │   ├── meta_tools.py      # System metadata queries
│   │   ├── mcp_skill_mapping.py # MCP server to skill mapping
│   │   └── confirmation_tool.py # Large operation confirmation
│   │
│   ├── skills/                   # Dynamic skill loading system
│   │   ├── registry.py         # Skill registry
│   │   ├── loader.py           # Skill loader
│   │   ├── builder.py          # Skill graph builder
│   │   ├── tool.py             # Skill tool wrapper
│   │   └── content/            # Skill definitions directory
│   │
│   ├── instincts/                # Instincts pillar - behavioral pattern learning
│   │   ├── observer.py         # Pattern detection from interactions
│   │   ├── injector.py         # Context injection into system prompts
│   │   ├── evolver.py          # Clustering instincts into skills
│   │   └── profiles.py         # Pre-built personality presets
│   │
│   ├── onboarding/               # User onboarding system
│   │   ├── onboarding.py       # Guided profile creation
│   │   └── profiles.py         # Onboarding flow definitions
│   │
│   ├── config/                   # Configuration management
│   │   ├── settings.py         # Pydantic Settings class
│   │   ├── llm_factory.py      # LLM model factory
│   │   ├── loader.py           # Config loader
│   │   └── constants.py        # Application constants
│   │
│   ├── utils/                    # Utility functions
│   │
│   ├── scheduler.py             # APScheduler integration
│   ├── logging.py               # Loguru logging configuration
│   ├── dev_server.py            # LangGraph dev server entry point
│   └── src/executive_assistant/main.py   # Application entry point
│
├── tests/                        # Test suite
│   ├── test_agent.py            # Agent integration tests
│   ├── test_file_sandbox.py     # File sandbox tests
│   ├── test_db_storage.py       # DuckDB storage tests (legacy)
│   ├── test_lancedb_vdb.py      # Vector database tests
│   ├── test_python_tool.py      # Python execution tests
│   ├── test_status_middleware.py # Middleware tests
│   ├── test_scheduled_flows.py   # Scheduler tests
│   ├── test_temporal_api.py     # Temporal integration tests
│   ├── test_journal_storage.py  # Journal pillar tests
│   ├── test_goals_storage.py    # Goals pillar tests
│   ├── test_onboarding.py       # Onboarding system tests
│   └── conftest.py             # Pytest fixtures
│
├── docker/migrations/            # PostgreSQL schema migrations
│   └── 000_init.sql             # Initial tables (thread-only)
│
├── scripts/                      # Utility scripts
│   └── benchmark_results/        # Performance benchmark results
│
├── docs/                         # Documentation
│   ├── kb/                      # Knowledge base docs
│   ├── langchain-skills/        # LangChain skills documentation
│   └── ollama/                  # Ollama configuration
│
├── data/                         # Application data
│   ├── shared/                  # Organization-wide storage
│   └── users/                   # Thread-scoped storage
│       └── {thread_id}/
│           ├── files/
│           ├── tdb/
│           ├── vdb/
│           ├── mem/              # Memory pillar
│           ├── journal/          # Journal pillar
│           ├── goals/            # Goals pillar
│           └── instincts/        # Instincts pillar
│
├── pyproject.toml                # Project dependencies & scripts
├── docker/config.yaml                   # Default configuration
├── docker/.env.example                  # Environment template
├── docker/Dockerfile                    # Container definition
├── docker/docker-compose.yml            # Development stack
├── langgraph.json                # LangGraph CLI configuration
├── README.md                     # User documentation
├── TODO.md                       # Development roadmap
└── CLAUDE.md                    # Development workflow notes
```

---

## Core Components

### 1. Agent Layer (`src/executive_assistant/agent/`)

**Purpose:** Implements the LangChain/LangGraph runtime, middleware, and agent state.

**Key Files:**
- `langchain_agent.py`: Builds the runtime with middleware and tool normalization
- `state.py`: AgentState TypedDict containing:
  - `messages`: Conversation history (with `add_messages` reducer)
  - `thread_id`: Thread identifier (channel + channel user id)
  - `channel`: Source channel (telegram/http)
  - `structured_summary`: Topic-based conversation summary
  - `todos`: Task tracking list
- `prompts.py`: System prompts for LLM reasoning
- `langchain_agent.py`: LangChain agent runtime builder with middleware stack
- `status_middleware.py`: Real-time progress tracking with millisecond timing
- `todo_display.py`: Todo list display formatting
- `token_callbacks.py`: Token usage tracking (experimental, unused)

**Middleware Stack (via LangChain):**
1. **StatusUpdateMiddleware**: Real-time progress tracking with emoji indicators (🤔 Thinking, 🛠️ Tool N:, ✅ Done)
2. **ThreadContextMiddleware**: Ensures thread_id ContextVar propagates to tool execution
3. **TodoListMiddleware**: Tracks planned tasks for multi-step operations
4. **TodoListDisplayMiddleware**: Displays planned tasks during execution (if channel enabled)
5. **SummarizationMiddleware**: Token-based conversation summarization (trigger: 5,000 / target: 1,000)
6. **ContextEditingMiddleware**: Edits context by clearing old tool uses (disabled by default)
7. **ModelCallLimitMiddleware**: Max 50 LLM calls per message (prevents infinite loops)
8. **ToolCallLimitMiddleware**: Max 100 tool calls per message (prevents runaway execution)
9. **ToolRetryMiddleware**: Automatic retry on tool failures with exponential backoff
10. **ModelRetryMiddleware**: Automatic retry on model failures with exponential backoff

**ThreadContextMiddleware (Custom):**
- **Purpose**: Fix Python ContextVar not propagating across LangGraph async task boundaries
- **Implementation**: Wraps tool execution via `awrap_tool_call()`
- **Functionality**:
  - Captures current `thread_id` from ContextVar before tool call
  - Restores `thread_id` immediately before tool execution
  - Logs all tool errors with full traceback at DEBUG level
- **Critical for**: FileSandbox, TDB, VDB, and all thread-scoped storage operations

### 2. Channels Layer (`src/executive_assistant/channels/`)

**Purpose:** Handles communication between users and agent across different platforms.

#### BaseChannel (`base.py`)
Abstract base class defining channel interface:
- `start()`: Initialize channel (connect to platform)
- `stop()`: Graceful shutdown
- `send_message()`: Send response to user
- `update_status()`: Update in-progress status
- `display_todos()`: Show todo list

#### TelegramChannel (`telegram.py`)
- Uses `python-telegram-bot` v22.5+
- Bot Commands: `/start`, `/reset`, `/remember`, `/debug`, `/mem`, `/reminder`, `/vdb`, `/tdb`, `/file`, `/meta`, `/user`
- Features:
  - Inline message editing for status updates (clean UI)
  - Debug mode toggle for verbose timing information
  - Per-thread asyncio locks to prevent message interleaving
  - Message queuing with deduplication
- Thread ID: Uses Telegram `chat_id` as `thread_id`
- Thread-only context (no group support)

#### HttpChannel (`http.py`)
- Built with FastAPI v0.115.0+
- Endpoints:
  - `POST /message`: Send message (supports SSE streaming with `stream: true`)
  - `GET /conversations/{id}`: Get conversation history
  - `GET /health`: Health check
- Features:
  - Server-sent events (SSE) for real-time streaming
  - JSON request/response models (Pydantic)
  - **Open access** - authentication handled by frontend application
  - **Non-streaming endpoint** - collects all messages and returns as JSON array
- Thread ID: Format `http:{conversation_id}`
- Authorization: Bypasses allowlist (frontend auth pattern)

### 3. Storage Layer (`src/executive_assistant/storage/`)

**Purpose:** Provides thread-scoped, privacy-first data storage with multi-tenancy support.

#### Storage Hierarchy

```
data/
├── admins/           # admin-managed configuration and allowlist
│   ├── prompts/
│   │   └── prompt.md
│   ├── skills/
│   ├── mcp.json
│   └── user_allowlist.json
├── shared/           # scope="shared" (organization-wide)
│   ├── files/
│   ├── tdb/
│   └── vdb/
└── users/            # scope="context" (thread-only)
    └── {thread_id}/
        ├── files/
        ├── tdb/
        ├── vdb/
        ├── mem/              # Memory pillar - embedded memories
        ├── journal/          # Journal pillar - time-series reflections
        │   └── journal.db    # SQLite with FTS5
        ├── goals/            # Goals pillar - long-term objectives
        │   └── goals.db      # SQLite with versioning
        └── instincts/        # Instincts pillar - behavioral patterns
            ├── instincts.jsonl
            └── instincts.snapshot.json
```

#### Key Storage Components

**FileSandbox (`file_sandbox.py`)**
- **Purpose**: Secure file operations with thread isolation
- **Isolation**: Uses Python `ContextVar` for thread-scoped paths
- **Features**:
  - Path traversal protection (prevents `../../../` attacks)
  - File size limits (configurable via `MAX_FILE_SIZE_MB`)
  - File extension whitelisting
  - Ownership tracking in PostgreSQL
- **Tools**:
  - `read_file`, `write_file`: Text file I/O
  - `create_folder`, `delete_folder`, `rename_folder`: Directory management
  - `move_file`: File relocation
  - `glob_files`: Pattern matching (`*.py`, `**/*.json`)
  - `grep_files`: Regex content search

**TDBStorage (`sqlite_db_storage.py`, `tdb_tools.py`)**
- **Backend**: SQLite (context + shared)
- **Purpose**: Structured/tabular data storage
- **Use Cases**: Timesheets, logs, analysis datasets
- **Tools**:
  - `create_tdb_table`: Create from JSON/CSV with auto schema inference
  - `insert_tdb_table`, `query_tdb`: SQL operations
  - `list_tdb_tables`, `describe_tdb_table`: Schema inspection
  - `export_tdb_table`, `import_tdb_table`: Data portability (CSV, JSON, Parquet)
- **Legacy**: `db_storage.py` retains DuckDB utilities (deprecated)

**Vector Database (`lancedb_storage.py`, `vdb_tools.py`)**
- **Backend**: LanceDB with sentence-transformers embeddings
- **Model**: `all-MiniLM-L6-v2` (384 dimensions)
- **Purpose**: Long-term knowledge retrieval
- **Use Cases**: Meeting notes, decisions, documentation
- **Features**:
  - Semantic search (vector similarity)
  - Document chunking (configurable `chunk_size`)
  - Metadata filtering
- **Tools**:
  - `create_vdb_collection`: Create collection with embeddings
  - `add_vdb_documents`: Add documents (auto-chunking)
  - `search_vdb`: Semantic search
  - `vdb_list`, `drop_vdb_collection`: Collection management

**UserRegistry (`user_registry.py`)**
- **Purpose**: Conversation logs and ownership tracking
- **Features**:
  - Thread-scoped conversation history
  - Ownership tracking for files/TDB/VDB/reminders per thread
  - Message audit log for troubleshooting

**InstinctStorage (`instinct_storage.py`)**
- **Purpose**: Behavioral pattern learning with confidence scoring
- **Backend**: JSONL append-only log + compacted snapshot
- **Features**:
  - Confidence scoring (0.0-1.0, thresholds at 0.2/0.5/0.6)
  - 6 domains: communication, format, workflow, tool_selection, verification, timing
  - Automatic reinforcement and contradiction
  - Event-based audit trail
  - Thread-scoped storage
- **Tools**:
  - `create_instinct`: Manually create behavioral pattern
  - `list_instincts`: Show all learned patterns
  - `adjust_instinct_confidence`: Reinforce or contradict patterns
  - `get_applicable_instincts`: Find patterns matching context
  - `disable_instinct` / `enable_instinct`: Toggle patterns
  - `evolve_instincts`: Cluster patterns into draft skills
  - `approve_evolved_skill`: Save draft as user skill
  - `export_instincts` / `import_instincts`: Backup and sharing

**JournalStorage (`journal_storage.py`)**
- **Purpose**: Time-series reflection logs with intelligent rollups
- **Backend**: SQLite with FTS5 full-text search
- **Location**: `data/users/{thread_id}/journal/journal.db`
- **Schema**:
  - `entries`: id, timestamp, entry_text, tags, metadata
  - `rollups`: id, period_start, period_end, rollup_type, summary, entry_count
  - `entries_fts`: Full-text search virtual table
- **Features**:
  - Daily journal entries with rich text formatting
  - Automatic time-series rollups:
    - Hourly → Daily (8:00 AM)
    - Daily → Weekly (Monday 8:00 AM)
    - Weekly → Monthly (1st of month 8:00 AM)
  - Full-text search across all entries (ranked by relevance)
  - Context-aware retrieval based on query intent
  - Thread-scoped storage
- **Tools**:
  - `journal_add`: Create new journal entry
  - `journal_search`: Search entries by keyword/semantic meaning
  - `journal_get_recent`: Get recent entries (configurable limit)
  - `journal_get_by_date`: Get entries for specific date range
  - `journal_get_rollups`: Get rolled-up summaries
  - `journal_list_tags`: List all used tags
  - `journal_update`: Update existing entry
  - `journal_delete`: Remove entry
- **Integration**: Injected into system prompts via "## Recent Reflections" section

**GoalsStorage (`goals_storage.py`)**
- **Purpose**: Long-term objective tracking with progress monitoring
- **Backend**: SQLite with version history
- **Location**: `data/users/{thread_id}/goals/goals.db`
- **Schema**:
  - `goals`: id, title, description, status, deadline, progress, created_at, updated_at
  - `goal_history`: id, goal_id, changed_at, changed_field, old_value, new_value, change_reason
  - `goals_fts`: Full-text search virtual table
- **Features**:
  - Goal lifecycle: draft → active → completed → cancelled
  - Progress tracking (0-100%)
  - Deadline management with overdue detection
  - Automatic version history for all changes
  - Priority levels (low, medium, high, critical)
  - Full-text search across goals
  - Thread-scoped storage
- **Tools**:
  - `goal_create`: Create new goal
  - `goal_update`: Update goal (title, description, status, progress, deadline, priority)
  - `goal_delete`: Delete goal (archives history)
  - `goal_list`: List all goals (filterable by status/priority)
  - `goal_get`: Get goal details with history
  - `goal_search`: Search goals by keyword
  - `goal_set_progress`: Update progress percentage
  - `goal_complete`: Mark goal as completed
  - `goal_cancel`: Cancel goal
  - `goal_get_overdue`: List overdue goals
- **Integration**: Injected into system prompts via "## Active Goals" section

**OnboardingSystem (`onboarding.py`)**
- **Purpose**: Structured profile creation for new users
- **Backend**: Uses MemoryStorage to persist profile data
- **Features**:
  - Guided 5-section onboarding flow:
    1. Basic Info (name, role, timezone)
    2. Communication Style (verbosity, format preferences)
    3. Work Preferences (productivity patterns, focus hours)
    4. Goals & Objectives (short-term and long-term)
    5. Additional Context (anything else relevant)
  - Automatic memory creation from responses
  - One-time setup per thread (stored in checkpoint)
  - Context injection into system prompts
  - Optional skip for experienced users
- **Tools**:
  - `start_onboarding`: Begin onboarding flow
  - `onboarding_save_section`: Save individual section responses
  - `onboarding_complete`: Finalize and create memories
  - `onboarding_skip`: Skip onboarding
  - `onboarding_status`: Check if onboarding completed
- **Integration**:
  - Checks onboarding status at conversation start
  - If not completed, prompts user to begin
  - Completed onboarding creates 5-10 embedded memories
  - Profile data used to personalize system prompts

**UserMCPStorage (`user_mcp_storage.py`)**
- **Purpose**: Per-conversation MCP server configuration management
- **Backend**: JSON files per-thread
- **Location**: `data/users/{thread_id}/mcp/`
- **Files**:
  - `mcp.json`: Local (stdio) server configurations
  - `mcp_remote.json`: Remote (HTTP/SSE) server configurations
  - Automatic backups: `mcp.json.backup_001` to `backup_005` (rotation)
- **Features**:
  - Server name validation (alphanumeric, underscore, hyphen only)
  - Command validation (stdio servers require command)
  - URL validation (HTTPS required, localhost exception for testing)
  - Security checks (command injection prevention)
  - Backup before modifications
  - Manual restore from any backup
- **Tools**:
  - `mcp_add_server`: Add local MCP server
  - `mcp_add_remote_server`: Add remote MCP server
  - `mcp_remove_server`: Remove server
  - `mcp_list_servers`: List all configured servers
  - `mcp_show_server`: Show server details
  - `mcp_export_config`: Export configuration as JSON
  - `mcp_import_config`: Import configuration from JSON
  - `mcp_list_backups`: List available backups
  - `mcp_restore_backup`: Restore from backup
  - `mcp_reload`: Reload tools from configuration

**MCPSkillStorage (`mcp_skill_storage.py`)**
- **Purpose**: HITL workflow for skill proposals from MCP servers
- **Backend**: JSON files per-thread
- **Location**: `data/users/{thread_id}/mcp/pending_skills/`
- **Proposal Schema**:
  ```json
  {
    "skill_name": "web_scraping",
    "source_server": "fetch",
    "reason": "The fetch tool requires knowledge of web scraping best practices",
    "content": "",
    "created_at": "2026-02-01T10:00:00Z",
    "status": "pending"  // pending | approved | rejected
  }
  ```
- **Features**:
  - Create pending proposals when MCP servers added
  - Approve/reject workflow with user control
  - Edit skill content before approving
  - List pending skills (sorted by created_at, newest first)
  - Get list of approved skills for loading
- **Functions**:
  - `save_pending_skill()`: Save proposal to storage
  - `load_pending_skill()`: Load proposal by name
  - `list_pending_skills()`: Get all pending proposals
  - `approve_skill()`: Mark as approved (loads on next reload)
  - `reject_skill()`: Mark as rejected
  - `get_approved_skills()`: Get list of approved skill names

**MCP Skill Mapping (`tools/mcp_skill_mapping.py`)**
- **Purpose**: Maps MCP servers to their associated skills
- **Database**: `MCP_SERVER_SKILLS` dictionary
- **Supported Servers**:
  - `fetch` → `web_scraping`, `fetch_content` (web scraping best practices)
  - `github` → `github_api`, `code_search`, `git_operations` (API patterns)
  - `clickhouse` → `clickhouse_sql`, `database_queries` (SQL optimization)
  - `filesystem` → `file_operations`, `file_security` (auto-load=False, requires paths)
  - `brave-search` → `web_search`, `search_strategies` (query optimization)
  - `puppeteer` → `browser_automation`, `web_scraping_advanced` (DOM manipulation)
- **Functions**:
  - `get_skills_for_server(name, command)`: Detect skills for a server
  - `get_skill_recommendation_reason(name)`: Get explanation
  - `is_server_auto_load(name)`: Check if skills should be auto-proposed

**Checkpoint (`checkpoint.py`)**
- **Purpose**: LangGraph state persistence
- **Backend**: PostgreSQL (via `langgraph-checkpoint-postgres`)
- **Tables**:
  - `checkpoints`: State snapshots per thread
  - `checkpoint_blobs`: Large message payloads
- **Alternative**: In-memory for development

**MetaRegistry (`meta_registry.py`)**
- **Purpose**: Ownership tracking for audit and data migration
- **Tables**:
  - `file_paths`: File ownership per thread
  - `tdb_paths`: Transactional database ownership per thread
  - `vdb_paths`: Vector database ownership per thread
  - `adb_paths`: Analytics DB ownership per thread
- **Operations**: Track all create/delete operations

**User Allowlist (`user_allowlist.py`)**
- **Purpose**: Channel-based access control
- **Implementation**:
  - HTTP channels: **Always authorized** (authentication handled by frontend)
  - Telegram channels: **Require allowlist** (anyone can message the bot)
  - Admin thread IDs: Always authorized (from `docker/config.yaml`)
- **File**: `data/admins/user_allowlist.json`
- **Format**: `{"users": ["telegram:123456", "telegram:789012"]}`
- **Rationale**:
  - HTTP: Frontend application handles authentication (JWT sessions, OAuth, etc.)
  - Telegram: Public platform, need allowlist to prevent unauthorized access
- **Pattern**: Follows LangGraph Studio dev/up model - auth is frontend responsibility

**Reminder (`reminder.py`, `scheduled_flows.py`)**
- **Purpose**: Scheduled notification system
- **Backend**: APScheduler (in-memory) + PostgreSQL persistence
- **Features**:
  - One-time and recurring reminders
  - Recurrence rules (daily, weekly, custom)
  - Multi-thread triggering (notify across conversations)
  - Timezone-aware scheduling
- **Table**: `reminders`

### Analytics DB (DuckDB)

- Context-scoped DuckDB for analytics queries.
- Stored at `data/users/{thread_id}/analytics/duckdb.db`.
- Tool: `query_adb` (read/write SQL for analysis).

### 4. Tools Layer (`src/executive_assistant/tools/`)

**Purpose:** LangChain tool implementations that the agent can invoke.

**Tool Registry (`registry.py`)**
- `get_all_tools()`: Aggregates all tool categories (131 total tools)
- **All tools available by default** - No progressive disclosure filtering
  - Token overhead: ~10,500 tokens (5% of 200K context)
  - Prevents multi-step workflow breakage
  - Deprecated: `get_tools_for_request()` (kept for compatibility; not used in runtime)
- Categories:
  - File tools (11 tools): File operations
  - TDB tools (10 tools): Database operations
  - ADB tools (5 tools): Analytics database operations
  - VDB tools (7 tools): Vector database operations
  - Time tools (3 tools): Timezone queries
  - Reminder tools (4 tools): Reminder management
  - Python tools (2 tools): Code execution
  - Search tools (2 tools): Web search via SearXNG
  - Browser tools (1 tool): Playwright scraping
  - OCR tools (2 tools): Image/PDF text extraction
  - Firecrawl tools (3 tools): Web scraping
  - Agent tools (6 tools): Mini-agent creation and management
  - Flow tools (5 tools): Workflow automation
  - Memory tools (6 tools): Memory extraction and search
  - Journal tools (8 tools): Time-series reflection with rollups
  - Goals tools (10 tools): Long-term objective tracking
  - Onboarding tools (5 tools): Structured profile creation
  - Meta tools (3 tools): System metadata
  - Instinct tools (13 tools): Behavioral pattern learning
  - MCP tools (14 tools): Configurable MCP server integration
    - Server management: add, remove, list, show servers (local + remote)
    - Configuration: export, import, list backups, restore backup
    - Hot-reload: clear MCP cache and reload tools
    - HITL workflow: list pending skills, approve, reject, edit, show skills
  - Confirmation tool (1 tool): Large operation confirmation
  - Skills tool (1 tool): Dynamic skill loading
  - Context tool (1 tool): Unified 4-pillar context query

**Python Tool (`python_tool.py`)**
- **Purpose**: Safe Python code execution for data processing
- **Security**:
  - 30-second timeout
  - Thread-scoped I/O (via `file_sandbox` paths)
  - Whitelisted modules: `json`, `csv`, `math`, `datetime`, `random`, `statistics`, `urllib`, `pandas`, `numpy`
  - Path traversal protection
- **Tools**:
  - `python_exec`: Execute Python code
  - `python_exec_file`: Execute Python file

**Time Tool (`time_tool.py`)**
- **Purpose**: Timezone-aware time queries
- **Tools**:
  - `get_current_time(timezone)`: Get time in specific timezone
  - `get_current_date(timezone)`: Get date in specific timezone
  - `list_timezones()`: List available timezones

**Search Tool (`search_tool.py`)**
- **Purpose**: Web search via SearXNG
- **Features**: Privacy-focused search aggregation
- **Config**: `SEARXNG_HOST` environment variable

**OCR Tool (`ocr_tool.py`)**
- **Purpose**: Extract text from images and PDFs
- **Engines**: Surya-OCR (default) or PaddleOCR (Linux x86_64 only)
- **Features**:
  - PDF text extraction (multi-page)
  - Image OCR (PNG, JPG, etc.)
  - Structured extraction with LLM (JSON output)
- **Config**: `ocr` section in `docker/config.yaml`

### 5. Skills System (`src/executive_assistant/skills/`)

**Purpose:** Progressive disclosure of advanced patterns through dynamic skill loading.

**Components:**
- `registry.py`: Skill registration
- `loader.py`: Load skill definitions from `.skill` files
- `builder.py`: Build LangGraph graphs from skills
- `tool.py`: Wrap skills as LangChain tools
- `content/`: Skill definition files

**Example Skill:** `react-agent.skill` (17KB)
- Defines ReAct agent pattern as a reusable skill
- Can be loaded via `load_skill` tool

### 6. Instincts System (`src/executive_assistant/instincts/`)

**Purpose:** Automatic behavioral pattern learning from user interactions.

**Components:**

**Observer (`observer.py`)**
- **Purpose**: Detect behavioral patterns in user messages
- **Pattern Types**:
  - Corrections: "Actually, I meant..." → Apologize and adjust
  - Repetitions: "Do it again..." → Follow same pattern
  - Verbosity: "Be concise" / "More detail" → Adjust response length
  - Format: "Use JSON" / "Bullet points" → Output format preference
- **Features**:
  - Regex-based pattern detection
  - Automatic reinforcement of existing patterns
  - Creates new instincts with 0.5-0.8 initial confidence
  - Integrated into message flow (BaseChannel.handle_message)

**Injector (`injector.py`)**
- **Purpose**: Load applicable instincts into system prompts
- **Features**:
  - Context-aware filtering (matches user message to triggers)
  - Confidence-based formatting (bold for ≥0.8, conditional for lower)
  - Fallback to all high-confidence instincts if no matches
  - Domain-specific sections (Communication, Format, Workflow, etc.)
- **Integration**: Called in `get_system_prompt()` between BASE_PROMPT and CHANNEL_APPENDIX

**Evolver (`evolver.py`)**
- **Purpose**: Cluster related instincts into reusable skills
- **Algorithm**:
  1. Group instincts by domain
  2. Extract keywords from triggers
  3. Find common themes (≥2 instincts sharing keywords)
  4. Build cluster with avg confidence
  5. Generate draft skill with behavioral patterns
- **Requirements**: Minimum 2 instincts per cluster, ≥0.6 avg confidence
- **HITL**: Human-in-the-loop approval required (approve_evolved_skill tool)

**Profiles (`profiles.py`)**
- **Purpose**: Quick personality configuration with preset instincts
- **Available Profiles**:
  1. **Concise Professional**: Brief, business-focused (3 instincts)
  2. **Detailed Explainer**: Thorough with examples (3 instincts)
  3. **Friendly Casual**: Conversational, approachable (3 instincts)
  4. **Technical Expert**: Precise technical language (4 instincts)
  5. **Agile Developer**: Iterative, testing-focused (3 instincts)
  6. **Analyst Researcher**: Data-driven analysis (4 instincts)
- **Tools**:
  - `list_profiles`: Browse available profiles
  - `apply_profile`: Apply profile to current thread
  - `create_custom_profile`: Build custom personality pack

**System Prompt Assembly Order:**
```python
system_prompt = (
    BASE_PROMPT +              # "You are {AGENT_NAME}..."
    ADMIN_PROMPT +             # Admin policies (safety, etc.)
    INSTINCTS_SECTION +        # "## Behavioral Patterns\nApply these..."
    CHANNEL_APPENDIX           # "HTTP/Telegram Formatting..."
)
```

**Storage Schema:**
```json
{
  "id": "uuid",
  "trigger": "user asks quick questions",
  "action": "respond briefly, skip detailed explanations",
  "domain": "communication",
  "source": "session-observation",
  "confidence": 0.8,
  "status": "enabled",
  "created_at": "2026-01-31T10:00:00Z"
}
```

### 7. Configuration Layer (`src/executive_assistant/config/`)

**Purpose:** Centralized configuration management.

**Components:**
- `settings.py`: Pydantic Settings class (environment + YAML)
- `llm_factory.py`: LLM model creation (provider-agnostic)
- `loader.py`: Load config from `docker/config.yaml` and `docker/.env`
- `constants.py`: Application constants

**Configuration Sources** (priority order):
1. Environment variables (`docker/.env`)
2. `docker/config.yaml` (application defaults)
3. Pydantic defaults

**Key Settings:**
- `DEFAULT_LLM_PROVIDER`: LLM provider selection (anthropic, openai, zhipu, ollama)
- `CHECKPOINT_STORAGE`: postgres or memory
- `EXECUTIVE_ASSISTANT_CHANNELS`: Comma-separated list (telegram, http)
- `MAX_ITERATIONS`: Max ReAct loops (default: 20)
- Middleware thresholds (max_tokens, call limits, etc.)

### 7. Workflows Layer (`src/executive_assistant/workflows/`)

**Purpose:** Integration with external workflow engines (currently Temporal).

**Components:**
- `health.py`: Health check workflow
- `temporal_client.py`: Temporal client wrapper

**Usage:** Optional integration for long-running, durable workflows.

### 8. Scheduler (`scheduler.py`)

**Purpose:** APScheduler integration for reminder notifications.

**Features:**
- Async job scheduling
- Job persistence (optional)
- Graceful shutdown

---

## Data Flow

### Message Processing Flow

```
[User Message]
    │
    ↓
[Channel Layer]  (TelegramChannel or HttpChannel)
    │  • Normalize message to HumanMessage
    │  • Set thread_id in ContextVars
    │  • Acquire thread lock (prevent concurrent processing)
    │  • Observe message for instinct patterns (non-blocking)
    │
    ↓
[Middleware Stack] (LangChain)
    │  • Summarization (if token limit exceeded)
    │  • Call limits (check max calls per message)
    │  • Status updates (enable streaming)
    │  • Todo tracking
    │
    ↓
[LangGraph ReAct Agent]
    │
    ├─→ [System Prompt Assembly]
    │      • BASE_PROMPT (core role)
    │      • ADMIN_PROMPT (safety policies)
    │      • INSTINCTS_SECTION (learned patterns)
    │      • CHANNEL_APPENDIX (formatting)
    │
    ├─→ [call_model Node]
    │      • Load conversation history from state
    │      • Invoke LLM with system prompt + messages
    │      • Record timing (milliseconds)
    │      • Check for tool_calls
    │
    ├─→ [Route: Tools or End?]
    │      • If tool_calls: go to tools
    │
    ├─→ [call_tools Node]
    │      • Execute tool functions
    │      • Each tool:
    │        • Read ContextVars (thread_id)
    │        • Access storage (file, TDB, VDB)
    │        • Return results
    │
    ├─→ [increment_iterations Node]
    │      • iterations += 1
    │
    └─→ [Loop back to call_model] or [END]
         │
         ↓
[Middleware Stack]
    │  • Final status update
    │  • Call limit logging
    │
    ↓
[Channel Layer]
    │  • Stream AIMessage chunks (if streaming)
    │  • Or send complete response
    │  • Edit status message (if enabled)
    │
    ↓
[Checkpoint Saver] (PostgreSQL)
    │  • Save final state to checkpoints table
    │  • Async write (non-blocking)
    │
    ↓
[User receives response]
```

### Tool Execution Flow

```
[Agent calls tool]
    │
    ↓
[ThreadContextMiddleware.awrap_tool_call()]
    │  • Capture thread_id from ContextVar
    │  • Set thread_id again (ensure propagation)
    │  • Log any errors with full traceback
    │
    ↓
[Tool function executes]
    │
    ├─→ Read ContextVars (_thread_id) ✓ (now works!)
    │
    ├─→ Build scoped path:
    │      • if scope="shared" → data/shared/
    │      • if scope="context" → data/users/{thread_id}/
    │
    ├─→ Check permissions:
    │      • FileSandbox: path traversal protection
    │      • MetaRegistry: ownership verification
    │
    ├─→ Access storage backend:
    │      • File: Local filesystem
    │      • TDB: SQLite (context + shared)
    │      • VDB: LanceDB (collection-scoped)
    │
    ├─→ Record operation:
    │      • MetaRegistry: Update ownership tracking
    │      • UserRegistry: Update audit log
    │
    └─→ Return results to agent
```

### MCP-Skill HITL Flow

When users add MCP servers, the system automatically proposes relevant skills:

```
[User adds MCP server]
    │
    ↓
[mcp_add_server tool]
    │  • Validate server configuration
    │  • Save to mcp.json or mcp_remote.json
    │  • Check skill mapping database
    │
    ├─→ [For each associated skill]
    │      • Check if already approved
    │      • Create MCPSkillProposal
    │      • Save to pending_skills/{skill_name}.json
    │      • Status: "pending"
    │
    ↓
[User reviews proposals]
    │
    ├─→ mcp_list_pending_skills()
    │   • Shows all pending skills
    │   • Displays source server and reason
    │   • Sorted by created_at (newest first)
    │
    ├─→ mcp_show_skill(skill_name)
    │   • Shows skill details
    │   • Displays current content
    │   • Shows available actions
    │
    ├─→ mcp_edit_skill(skill_name, content) [optional]
    │   • Customize skill content
    │   • Preserves status
    │
    ├─→ mcp_approve_skill(skill_name)
    │   • Changes status to "approved"
    │   • Will load on next reload
    │
    └─→ mcp_reject_skill(skill_name)
        • Changes status to "rejected"
        • Won't be loaded
    │
    ↓
[mcp_reload tool]
    │  • clear_mcp_cache() - Clear tool cache
    │  • Load tools from all configured servers
    │  • get_approved_skills() - Get approved skill list
    │  • For each approved skill:
    │     • load_skill(skill_name)
    │     • Inject skill content into agent context
    │
    ↓
[Agent now has tools + expertise]
```

**Key Benefits:**
- **Transparency**: Users see exactly what skills will be loaded
- **Control**: Users approve/reject individual skills
- **Customization**: Users can edit skills before loading
- **Safety**: Skills require explicit approval
- **Context**: Skills teach agent how/when/why to use tools

---

## Storage Architecture

### PostgreSQL Schema

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `checkpoints` | LangGraph state snapshots | `thread_id`, `checkpoint_ns`, `checkpoint_id` |
| `checkpoint_blobs` | Large message payloads | `thread_id`, `checkpoint_id`, `blob` |
| `conversations` | Conversation metadata | `thread_id`, `created_at` |
| `messages` | Message audit log | `thread_id`, `message_id`, `role`, `content` |
| `file_paths` | File ownership tracking | `thread_id`, `path`, `created_at` |
| `tdb_paths` | TDB ownership tracking | `thread_id`, `tdb_path`, `created_at` |
| `vdb_paths` | VDB ownership tracking | `thread_id`, `vdb_path`, `created_at` |
| `adb_paths` | Analytics DB ownership tracking | `thread_id`, `adb_path`, `created_at` |
| `reminders` | Scheduled reminders | `reminder_id`, `thread_id`, `trigger_time`, `recurrence` |

**Note:** Instincts are stored in the filesystem (JSONL + snapshot) under `data/users/{thread_id}/instincts/`, not in PostgreSQL.

### Data Isolation Model

**Thread-Level Isolation (Default)**
- Each conversation gets unique `thread_id` (e.g., Telegram chat_id)
- Data stored under `data/users/{thread_id}/`
- Prevents cross-thread data leakage

**Organization-Level Sharing**
- Admins can write to `data/shared/`
- All users can read from shared storage
- Use cases: Company-wide knowledge, templates

Thread-only context
- Enables multi-thread access to user data

### Unified Context System (4-Pillar Architecture)

The agent maintains comprehensive user context through four integrated pillars:

```
┌─────────────────────────────────────────────────────────────────┐
│                    UNIFIED CONTEXT SYSTEM                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────┐│
│  │   MEMORY     │  │   JOURNAL    │  │  INSTINCTS   │  │GOALS││
│  │   Pillar     │  │   Pillar     │  │   Pillar     │  │Pillar││
│  └──────────────┘  └──────────────┘  └──────────────┘  └─────┘│
│         │                 │                 │              │    │
│         ▼                 ▼                 ▼              ▼    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │         Unified Query Interface (context_router)        │   │
│  └─────────────────────────────────────────────────────────┘   │
│         │                                                       │
│         ▼                                                       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │    Context Injection into System Prompts                │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Pillar 1: Memory (MemStorage)**
- **Storage**: SQLite + FTS5 at `data/users/{thread_id}/mem/memories.db`
- **Purpose**: Long-term fact retention (names, preferences, decisions)
- **Retrieval**: Full-text search with relevance ranking
- **Tools**: 6 tools (extract_memory, search_memories, list_memories, update_memory, delete_memory, get_relevant_context)

**Pillar 2: Journal (JournalStorage)**
- **Storage**: SQLite + FTS5 at `data/users/{thread_id}/journal/journal.db`
- **Purpose**: Time-series reflections with automatic rollups
- **Retrieval**: Temporal queries (recent, date range) + semantic search
- **Rollups**: Hourly → Daily → Weekly → Monthly
- **Tools**: 8 tools (add, search, get_recent, get_by_date, get_rollups, list_tags, update, delete)

**Pillar 3: Instincts (InstinctStorage)**
- **Storage**: JSONL + snapshot at `data/users/{thread_id}/instincts/`
- **Purpose**: Behavioral pattern learning with confidence scoring
- **Domains**: 6 categories (communication, format, workflow, tool_selection, verification, timing)
- **Retrieval**: Context-aware filtering + confidence thresholds
- **Tools**: 13 tools (create, list, adjust_confidence, get_applicable, enable/disable, evolve, approve_evolved, export/import)

**Pillar 4: Goals (GoalsStorage)**
- **Storage**: SQLite with versioning at `data/users/{thread_id}/goals/goals.db`
- **Purpose**: Long-term objectives with progress tracking
- **Status Workflow**: draft → active → completed → cancelled
- **Retrieval**: Status filtering, priority sorting, overdue detection
- **Tools**: 10 tools (create, update, delete, list, get, search, set_progress, complete, cancel, get_overdue)

**Integration Flow:**
1. **Message Received** → Query all 4 pillars in parallel
2. **Context Assembly** → Combine results with relevance scoring
3. **Prompt Injection** → Insert into system prompt as structured sections:
   - "## Relevant Memories"
   - "## Recent Reflections" (Journal)
   - "## Behavioral Patterns" (Instincts)
   - "## Active Goals"
4. **Agent Reasoning** → LLM uses unified context for decisions
5. **Context Update** → New information automatically stored in appropriate pillars

**Storage Locations Summary:**
```
data/users/{thread_id}/
├── mem/              # Memory Pillar
│   └── memories.db   # SQLite + FTS5
├── journal/          # Journal Pillar
│   └── journal.db    # SQLite + FTS5
├── instincts/        # Instincts Pillar
│   ├── instincts.jsonl
│   └── instincts.snapshot.json
└── goals/            # Goals Pillar
    └── goals.db      # SQLite with versioning
```

### Vector Database Architecture

**LanceDB Collections**
- Per-thread collections
- Embeddings via sentence-transformers
- Metadata filtering support

**Document Chunking**
- Split documents into ~3000 character chunks
- Overlap for context preservation
- Configurable via `vector_store.chunk_size`

**Search Options**
1. **Semantic Search**: Vector similarity (cosine distance)
2. **Full-Text Search**: Keyword matching
3. **Hybrid Search**: Combined score

---

## Key Libraries & Frameworks

### LangGraph (`langgraph >= 1.0.6`)
**Role:** Agent orchestration and state management
**Key Features Used:**
- `StateGraph`: Build custom agent graphs
- `add_messages` reducer: Automatic message history accumulation
- `BaseCheckpointSaver`: State persistence interface
- `RunnableConfig`: Per-invocation configuration

**Key Components:**
```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres import PostgresSaver
```

### LangChain (`langchain >= 0.3.27`)
**Role:** Unified LLM and tool interface
**Key Features Used:**
- `BaseChatModel`: Provider-agnostic LLM interface
- `BaseTool`: Tool implementation base class
- Middleware stack: Summarization, retry, limits
- `StructuredTool`: Tools with JSON schemas

**Key Components:**
```python
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool, tool
from langchain.agents.middleware import (
    SummarizationMiddleware,
    CallLimitMiddleware,
    TodoListMiddleware,
)
```

### LLM Providers

**Anthropic (`langchain-anthropic >= 0.3.22`)**
- Claude models (Haiku, Sonnet)
- Used by default in `docker/config.yaml`

**OpenAI (`langchain-openai >= 0.3.35`)**
- GPT models (GPT-4o, GPT-4o-mini)
- Alternative to Anthropic

**Zhipu AI (`zhipuai`)**
- GLM-4 models
- Chinese LLM provider

**Ollama (`langchain-ollama >= 0.3.1`)**
- Local models or Ollama Cloud
- Privacy-focused option

### FastAPI (`fastapi >= 0.115.0`)
**Role:** HTTP channel implementation
**Key Features Used:**
- ASGI async server
- Pydantic models for validation
- Server-Sent Events (SSE) streaming
- CORS support

**Key Components:**
```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
```

### APScheduler (`apscheduler >= 3.10.0`)
**Role:** Reminder scheduling
**Key Features Used:**
- Async job scheduling
- Cron-like recurrence rules
- Timezone-aware triggers

**Key Components:**
```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
```

### DuckDB (`duckdb >= 1.1.0`) (legacy)
**Role:** Thread-scoped database
**Key Features Used:**
- Embedded, no external process needed
- SQL compatibility
- Fast in-memory queries
- CSV/JSON/Parquet import/export

### LanceDB (`lancedb >= 0.15.0`)
**Role:** Vector store for semantic search
**Key Features Used:**
- Embedded vector database
- Sentence-transformers integration
- Hybrid search (vector + full-text)
- Metadata filtering

### psycopg + asyncpg (`asyncpg >= 0.30.0`)
**Role:** PostgreSQL async driver
**Key Features Used:**
- Async connection pooling
- Prepared statements
- Type safety

### Pydantic (`pydantic >= 2.12.5`)
**Role:** Configuration and validation
**Key Features Used:**
- `BaseSettings`: Environment variable management
- Type validation
- YAML configuration loading

**Key Components:**
```python
from pydantic import BaseModel, Field, BaseSettings
from pydantic_settings import BaseSettings
```

### Loguru (`loguru >= 0.7.2`)
**Role:** Structured logging
**Key Features Used:**
- JSON logging
- Log rotation
- Millisecond timestamps
- Context-aware logging

### Python Standard Library
- `asyncio`: Async runtime
- `pathlib`: Path manipulation
- `contextvars`: Thread-scoped context
- `datetime`, `timezone`: Time handling

---

## Configuration Management

### Configuration Files

**`docker/config.yaml`** - Application Defaults
- LLM provider settings
- Storage paths
- Agent parameters
- Middleware thresholds
- Vector store settings
- OCR configuration

**`docker/.env`** - Environment-Specific Overrides
- API keys (secrets)
- Channel configuration
- Database credentials
- External service URLs

**Admin Customization (`data/admins/`)**
- `prompts/prompt.md`: Prepended before the system prompt (admin-only).
- `skills/`: Loaded as additional skills at startup (admin-only).
- `mcp.json`: Loaded when MCP adapters are available (admin-only).
- `user_allowlist.json`: Access control list managed by admins.

**`pyproject.toml`** - Project Metadata
- Dependencies
- Build configuration
- Scripts (`executive_assistant`, `executive_assistant-dev`)

### Configuration Loading

1. **Load `docker/config.yaml`** → `Settings` object
2. **Override with `docker/.env`** → Environment variables
3. **Validate with Pydantic** → Type checking
4. **Use in application** → `settings` singleton

**Example:**
```python
from executive_assistant.config import settings

# Access settings
provider = settings.DEFAULT_LLM_PROVIDER
max_iter = settings.MAX_ITERATIONS
```

### LLM Factory

**`llm_factory.py`** creates provider-agnostic models:
```python
from executive_assistant.config import create_model

# Creates model based on DEFAULT_LLM_PROVIDER
model = create_model()  # Returns BaseChatModel
```

**Supported Providers:**
- `anthropic`: Claude models
- `openai`: GPT models
- `zhipu`: GLM-4 models
- `ollama`: Local/Cloud models

---

## Token Usage Tracking

Executive Assistant monitors token consumption to control costs and understand usage patterns:

### Implementation

**HTTP Channel Token Tracking** (`channels/http.py`):
- Extracts `usage_metadata` from AIMessage objects in the event stream
- Logs input/output/total tokens per conversation: `tokens={input}+{output}={total}`
- **Provider Support**:
  - ✅ OpenAI: Full token tracking (input + output + total)
  - ✅ Anthropic: Full token tracking
  - ❌ Ollama: No metadata provided (usage not tracked)

### Token Breakdown

Typical token usage for a conversation:

| Component | Token Count | Notes |
|-----------|-------------|-------|
| System prompt | ~50 tokens | "You are Jen, a personal AI assistant..." |
| Tools (dynamic count) | Variable | Tool names, descriptions, JSON schemas |
| Instincts (variable) | ~100-500 tokens | Learned behavioral patterns |
| Conversation messages | Variable | Grows with each turn (±30-80 tokens per round) |
| **Total (Round 1)** | ~8,250 tokens | System + tools + first user message |
| **Total (Round 5)** | ~8,700 tokens | +450 tokens from 4 conversation turns |

### Example Log Output

```bash
CH=http CONV=http_user123 TYPE=token_usage | message tokens=7581+19=7600
CH=http CONV=http_user123 TYPE=token_usage | message tokens=7900+808=8708
CH=http CONV=http_user123 TYPE=token_usage | message tokens=8726+803=9529
```

**Interpretation**:
- Input tokens grow as conversation context is preserved
- Output tokens vary based on response complexity
- Cache hits (OpenAI) reduce effective token cost significantly

### Summarization Middleware

**Configuration** (`docker/config.yaml`):
```yaml
middleware:
  summarization:
    enabled: true
    max_tokens: 5000     # Trigger: 5,000 conversation messages
    target_tokens: 1000  # Target: 1,000 messages after summarization
```

**Important Notes**:
- Threshold applies to **conversation messages only**, not total LLM input
- Does NOT count the ~8,100 token system prompt + tools + instincts overhead
- With 128K context window (GPT-OSS 20B), 5,000 messages is very conservative
- Summarization calls the LLM to compress older messages into a summary

**When to Adjust**:
- **Lower threshold** (500-1,000): For faster summarization, more aggressive compression
- **Higher threshold** (10,000+): For longer conversations before summarization
- **Use fractional triggering**: `trigger: 0.4` (40% of model context window)

---

## Deployment Architecture

### Docker Deployment

**`docker/Dockerfile`** - Multi-stage build
- Base: `python:3.13-slim`
- Dependencies: `uv sync --frozen`
- User: `executive_assistant` (non-root)
- Ports: 8000
- Volumes: `/app/data`

**`docker/docker-compose.yml`** - Development stack
```yaml
services:
  executive_assistant:    # Agent application
  postgres:  # PostgreSQL for state persistence
```

### Production Deployment

**Environment Variables Required:**
```bash
# LLM Provider
DEFAULT_LLM_PROVIDER=anthropic  # or openai, zhipu, ollama
ANTHROPIC_API_KEY=sk-ant-xxx

# Channels
EXECUTIVE_ASSISTANT_CHANNELS=telegram,http

# Telegram
TELEGRAM_BOT_TOKEN=your-bot-token

# PostgreSQL
POSTGRES_HOST=postgres
POSTGRES_PASSWORD=executive_assistant_password

# Optional: External Services
SEARXNG_HOST=https://your-searxng.com
FIRECRAWL_API_KEY=fc-xxx
```

### Development Workflow

**Local Testing (Recommended):**
```bash
# Start PostgreSQL
docker compose up -d postgres

# Run locally (no Docker rebuild needed)
uv run executive_assistant

# Run HTTP only
EXECUTIVE_ASSISTANT_CHANNELS=http uv run executive_assistant
```

**Docker Deployment:**
```bash
# Build and run all services
docker compose up -d

# Rebuild executive_assistant container
docker compose build --no-cache executive_assistant
```

### Scaling Considerations

**Stateless Channels:**
- HTTP channel can scale horizontally (multiple instances)
- Load balancer distributes traffic

**Stateful Agent:**
- PostgreSQL checkpointing enables persistence
- Multiple instances share state via PostgreSQL

**Storage:**
- File storage: Use networked volume (NFS, S3, etc.)
- Vector store: LanceDB embedded (one instance per agent)

---

## Testing Strategy

### Test Framework
- **pytest v9.0.2+**: Test runner
- **pytest-asyncio v1.3.0+**: Async test support
- **pytest-recording**: HTTP request recording/replay

### Test Categories

**Unit Tests**
- `test_file_sandbox.py`: File operations
- `test_db_storage.py`: DuckDB operations (legacy)
- `test_lancedb_vdb.py`: Vector database operations
- `test_python_tool.py`: Python execution

**Integration Tests**
- `test_agent.py`: Agent execution with mock LLM
- `test_status_middleware.py`: Middleware behavior
- `test_temporal_api.py`: Temporal integration

**System Tests**
- `test_integration_pg.py`: Full PostgreSQL integration
- `test_scheduled_flows.py`: Reminder scheduling

### Test Fixtures (`conftest.py`)
- Mock LLM responses
- Test data generation
- Async event loop management

### VCR Cassettes
- Record live LLM calls for replay in tests
- Avoid hitting rate limits
- Enable deterministic tests

**Recording:**
```bash
RUN_LIVE_LLM_TESTS=1 uv run pytest -m "langchain_integration and vcr" --record-mode=once
```

---

## Appendix: Key Concepts

### ReAct Pattern
The agent follows the **ReAct** (Reasoning + Acting) pattern:
1. **Reason**: LLM analyzes request and decides what to do
2. **Act**: Execute tools to gather information or perform actions
3. **Observe**: Process results and update context
4. **Loop**: Repeat until task complete

### Context Variables
Python `ContextVar` provides thread-scoped context:
```python
_thread_id: ContextVar[str] = ContextVar("_thread_id", default=None)
```

This ensures:
- Thread isolation (no cross-thread data leakage)
- Async propagation (works with asyncio)
- Zero performance overhead

### Middleware Chain
LangChain middleware wraps tool/model calls:
```
[User Request]
  → [TodoListMiddleware] (track planned tasks)
  → [SummarizationMiddleware] (reduce context if needed)
  → [CallLimitMiddleware] (check call limits)
  → [RetryMiddleware] (retry on failure)
  → [Model/Tool]
  → [StatusUpdateMiddleware] (stream progress)
  → [TodoListDisplayMiddleware] (show todos)
  → [User Response]
```

### Checkpointing
LangGraph saves state after each node execution:
- Resume from checkpoint after interruption
- Multi-session conversations
- Debug agent decisions

### Tool Selection
The LLM chooses tools dynamically based on:
- Request context
- Available tools
- Tool descriptions and schemas

This enables:
- Context-aware behavior
- Dynamic tool chains
- Multi-step reasoning

---

## Document Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.4.0 | 2026-02-04 | Implemented Unified Context System (4 Pillars): Memory, Journal, Instincts, Goals; Added Onboarding System |
| 1.3.0 | 2026-02-01 | Implemented User MCP Management and MCP-Skill HITL Integration |
| 1.2.0 | 2026-01-31 | Implemented Instinct System (Observer, Injector, Evolver, Profiles) |
| 1.1.0 | 2026-01-28 | Added ThreadContextMiddleware, HTTP auth bypass, error logging enhancements |
| 1.0.0 | 2026-01-21 | Initial technical architecture documentation |

### Key Changes in v1.4.0

**New Feature: Unified Context System (4-Pillar Architecture)**
- **Memory Pillar**: Long-term fact retention with FTS5 full-text search
  - Storage: SQLite at `data/users/{thread_id}/mem/memories.db`
  - 6 tools: extract_memory, search_memories, list_memories, update_memory, delete_memory, get_relevant_context
  - Retrieval: Full-text search with relevance ranking
- **Journal Pillar**: Time-series reflections with intelligent rollups
  - Storage: SQLite at `data/users/{thread_id}/journal/journal.db`
  - 8 tools: add, search, get_recent, get_by_date, get_rollups, list_tags, update, delete
  - Rollups: Hourly → Daily → Weekly → Monthly
  - Full-text search across all entries
- **Instincts Pillar**: Behavioral pattern learning (existing system, now integrated)
  - Storage: JSONL + snapshot at `data/users/{thread_id}/instincts/`
  - 13 tools: create, list, adjust_confidence, get_applicable, enable/disable, evolve, approve_evolved, export/import
  - 6 domains: communication, format, workflow, tool_selection, verification, timing
- **Goals Pillar**: Long-term objective tracking with progress monitoring
  - Storage: SQLite at `data/users/{thread_id}/goals/goals.db`
  - 10 tools: create, update, delete, list, get, search, set_progress, complete, cancel, get_overdue
  - Status workflow: draft → active → completed → cancelled
  - Version history for all changes
- **Unified Query Interface**: Single entry point for querying all pillars
- **Context Injection**: All pillars injected into system prompts as structured sections
- **Integration Flow**: Parallel query → relevance scoring → prompt injection → agent reasoning

**New Feature: Journal System**
- Daily journal entries with rich text formatting
- Automatic time-series rollups (hourly → daily → weekly → monthly)
- Full-text search across all journal entries
- Context-aware retrieval for relevant historical reflections
- Tags and metadata support
- Storage: `data/users/{thread_id}/journal/journal.db` (SQLite with FTS5)
- 8 comprehensive tools for journal management

**New Feature: Goals System**
- Create, update, track, and complete long-term goals
- Progress tracking with percentage completion
- Deadline management with overdue detection
- Automatic version history for all goal changes
- Priority levels (low, medium, high, critical)
- Status workflow: draft → active → completed → cancelled
- Storage: `data/users/{thread_id}/goals/goals.db` (SQLite with versioning)
- 10 comprehensive tools for goal management

**New Feature: Onboarding System**
- Guided profile creation for new users
- 5-section onboarding flow:
  1. Basic Info (name, role, timezone)
  2. Communication Style (verbosity, format preferences)
  3. Work Preferences (productivity patterns, focus hours)
  4. Goals & Objectives (short-term and long-term)
  5. Additional Context (anything else relevant)
- Automatic memory creation from responses
- One-time setup per thread
- Context injection into system prompts
- 5 onboarding tools for guided setup

**Architecture Improvements:**
- 4-pillar unified context architecture provides comprehensive user understanding
- All pillars use thread-scoped storage for privacy
- Unified query interface for parallel pillar searches
- Context injection provides LLM with rich, structured context
- Journal rollups enable efficient time-series analysis
- Goals version history provides complete audit trail
- Onboarding creates strong initial context foundation

**Tool Count:**
- Increased from 101 to 131 tools (+30 new tools)
  - +8 Journal tools
  - +10 Goals tools
  - +5 Onboarding tools
  - +1 Unified context query tool
  - +6 Memory enhancement tools

**Token Impact:**
- Total tool overhead: ~10,500 tokens (up from ~8,100)
- Still only 5% of 200K context window
- Rich context awareness outweighs token cost

**Storage Updates:**
- Added 3 new SQLite databases per thread:
  - `journal.db` (FTS5-enabled)
  - `goals.db` (with versioning)
  - Enhanced `memories.db` (existing)
- All 4 pillars now have dedicated storage backends

**New Files:**
- `src/executive_assistant/storage/journal_storage.py` (200+ lines)
- `src/executive_assistant/storage/goals_storage.py` (300+ lines)
- `src/executive_assistant/onboarding/onboarding.py` (150+ lines)
- `src/executive_assistant/tools/journal_tools.py` (250+ lines)
- `src/executive_assistant/tools/goals_tools.py` (300+ lines)
- `src/executive_assistant/tools/onboarding_tools.py` (120+ lines)
- `src/executive_assistant/tools/context_query_tool.py` (80+ lines)

### Key Changes in v1.3.0

**New Feature: User MCP Management**
- Per-conversation MCP server configuration (separate from admin MCP)
- Support for stdio (command-line) and HTTP/SSE (remote) servers
- Tiered loading: User tools override admin tools when names conflict
- Tool deduplication: Prevents duplicate tools with same name
- Hot-reload: `clear_mcp_cache()` for updating tools without restart
- Security validation:
  - Server name validation (alphanumeric, underscore, hyphen only)
  - Command injection prevention (validates command format)
  - HTTPS enforcement for remote servers (localhost exception)
  - JSON validation for env/headers arguments
- Backup/Restore:
  - Automatic backups before modifications (keeps last 5)
  - Manual restore from any backup point
  - Rotation: Oldest backup deleted when exceeding limit
- Storage: `data/users/{thread_id}/mcp/mcp.json` and `mcp_remote.json`

**New Feature: MCP-Skill HITL Integration**
- Skill mapping database: Maps MCP servers to associated skills
- Auto-detection: When adding servers, relevant skills are proposed
- Human-in-the-loop workflow:
  - `mcp_list_pending_skills`: Show all proposals
  - `mcp_show_skill`: View skill details before deciding
  - `mcp_approve_skill`: Approve skill (loads on next reload)
  - `mcp_reject_skill`: Reject skill (won't be loaded)
  - `mcp_edit_skill`: Customize skill content
- Storage: `data/users/{thread_id}/mcp/pending_skills/{skill_name}.json`
- Enhanced tools:
  - `mcp_add_server`: Now creates skill proposals
  - `mcp_reload`: Now loads approved skills into context
- Supported servers: fetch, github, clickhouse, filesystem, brave-search, puppeteer

**Architecture Improvements:**
- Separation of concerns: MCP config vs skill proposals
- Status workflow: pending → approved/rejected
- Proposal metadata: source_server, reason, created_at
- Audit trail: All proposals stored with timestamps
- Thread isolation: Each conversation has its own servers and skills

**Testing:**
- 33 tests for storage and skill mapping (`test_mcp_skill_hitl.py`)
- 27 tests for HITL workflow tools (`test_mcp_hitl_tools.py`)
- Total: 60 tests, all passing
- Test coverage: Proposal lifecycle, mapping detection, tool integration, error handling

**New Files:**
- `src/executive_assistant/storage/mcp_skill_storage.py` (130+ lines)
- `src/executive_assistant/tools/mcp_skill_mapping.py` (117 lines)
- `src/executive_assistant/tools/user_mcp_tools.py` (700+ lines, enhanced)
- `tests/test_mcp_skill_hitl.py` (400+ lines)
- `tests/test_mcp_hitl_tools.py` (500+ lines)

**Tool Count:**
- Increased from 87 to 101 tools (+14 MCP management tools)

### Key Changes in v1.2.0

**New Feature: Instinct System**
- Automatic behavioral pattern learning from user interactions
- Observer: Detects corrections, repetitions, verbosity/format preferences
- Injector: Loads applicable instincts into system prompts
- Evolver: Clusters related instincts into reusable skills
- Profiles: 6 pre-built personality presets (Concise Professional, Detailed Explainer, etc.)
- 13 instinct tools for management and evolution
- JSONL + snapshot storage for auditability

**Architecture Improvements:**
- System prompt assembly now includes instincts between BASE_PROMPT and CHANNEL_APPENDIX
- Observer integrated into message flow (non-blocking pattern detection)
- Confidence scoring (0.0-1.0) with automatic thresholds
- Human-in-the-loop approval for skill evolution

**Tool Count:**
- Dynamic based on enabled features and MCP servers

### Key Changes in v1.1.0

**Bug Fixes:**
- Fixed progressive disclosure bug causing tool loss mid-conversation
- Fixed thread_id ContextVar not propagating to tool execution
- Fixed HTTP channel non-streaming endpoint (missing `stream_agent_response` method)
- Enhanced error logging with full tracebacks at DEBUG level

**Architecture Improvements:**
- All registered tools are available by default (token cost depends on active toolset)
- HTTP channel bypasses allowlist (frontend authentication pattern)
- ThreadContextMiddleware ensures context propagation across async boundaries
- Deprecated `get_tools_for_request()` in favor of loading all tools

**New Components:**
- `src/executive_assistant/agent/thread_context_middleware.py` - Context propagation middleware
- `src/executive_assistant/instincts/` - Complete instinct learning system (observer, injector, evolver, profiles)
- Enhanced `is_authorized()` in `user_allowlist.py` - Channel-specific authorization

---

**Document Author:** Generated via analysis of Executive Assistant codebase
**Contact:** See repository for issues and contributions
