# Executive Assistant Technical Architecture Documentation

**Version:** 1.0.0
**Last Updated:** January 21, 2026
**Project:** Executive Assistant - Multi-channel AI Agent Platform

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
- **ReAct Agent Architecture**: Reasoning → Action → Observation cycle
- **Multi-Channel Support**: Telegram bot and HTTP REST API
- **Privacy-First Storage**: Thread-scoped data isolation with group collaboration
- **Tool-Based Intelligence**: Dynamic tool selection based on context
- **State Persistence**: PostgreSQL-backed checkpointing for conversation memory
- **Production-Ready**: Middleware stack with rate limiting, retry logic, and monitoring

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
| **Vector Store** | LanceDB | Semantic search/knowledge base |
| **Tabular Data** | SQLite (sqlite_db_storage.py, db_tools.py) | Transactional, permanent data (timesheets, CRM, tasks) |
| **Memories** | SQLite + FTS5 (mem_storage.py) | Embedded memories with full-text search |
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
│   ├── agent/                     # Agent logic & graph
│   │   ├── graph.py              # LangGraph StateGraph definition
│   │   ├── nodes.py              # ReAct nodes: call_model, call_tools
│   │   ├── state.py              # AgentState TypedDict
│   │   ├── prompts.py            # System prompts for reasoning
│   │   ├── langchain_agent.py    # LangChain agent runtime
│   │   ├── status_middleware.py   # Real-time progress tracking
│   │   ├── middleware_debug.py    # Debug middleware
│   │   ├── todo_display.py       # Todo list display logic
│   │   ├── topic_classifier.py   # Message classification
│   │   ├── router.py             # Conditional edge routing
│   │   ├── checkpoint_utils.py   # Checkpoint management
│   │   └── langchain_state.py    # LangChain state wrapper
│   │
│   ├── channels/                  # Communication channels
│   │   ├── base.py              # Abstract BaseChannel class
│   │   ├── telegram.py          # Telegram bot implementation
│   │   ├── http.py              # FastAPI HTTP channel
│   │   └── management_commands.py # CLI commands (/mem, /vs, /db, /file)
│   │
│   ├── storage/                   # Data persistence layer
│   │   ├── checkpoint.py        # LangGraph PostgreSQL checkpointer
│   │   ├── file_sandbox.py      # Secure file operations (thread-scoped)
│   │   ├── db_storage.py        # Legacy DuckDB DB storage (deprecated)
│   │   ├── db_tools.py          # SQLite DB tool implementations
│   │   ├── sqlite_db_storage.py # SQLite backend (context + shared)
│   │   ├── vs_tools.py          # Vector store tool implementations
│   │   ├── lancedb_storage.py   # LanceDB vector store backend
│   │   ├── group_storage.py     # Group workspace management
│   │   ├── group_workspace.py   # Group workspace utilities
│   │   ├── user_registry.py     # User identity & merge management
│   │   ├── meta_registry.py     # Metadata/ownership tracking
│   │   ├── reminder.py          # Reminder scheduling
│   │   ├── scheduled_jobs.py    # APScheduler integration
│   │   ├── chunking.py         # Document chunking for vector store
│   │   ├── mem_storage.py      # Embedded memory storage
│   │   ├── helpers.py          # Storage helper functions
│   │   └── workers.py          # Async worker pool
│   │
│   ├── tools/                    # LangChain tool implementations
│   │   ├── registry.py          # Tool registry (get_all_tools)
│   │   ├── python_tool.py       # Python code execution (sandboxed)
│   │   ├── time_tool.py        # Timezone-aware time queries
│   │   ├── reminder_tools.py   # Reminder CRUD operations
│   │   ├── search_tool.py      # Web search (SearXNG)
│   │   ├── ocr_tool.py        # OCR image/PDF text extraction
│   │   ├── firecrawl_tool.py   # Firecrawl web scraping
│   │   ├── identity_tools.py   # User identity management
│   │   ├── mem_tools.py       # Memory extraction tools
│   │   ├── meta_tools.py      # System metadata queries
│   │   └── confirmation_tool.py # Large operation confirmation
│   │
│   ├── workflows/                # External workflow integration
│   │   ├── health.py           # Temporal health check workflow
│   │   └── temporal_client.py  # Temporal client wrapper
│   │
│   ├── skills/                   # Dynamic skill loading system
│   │   ├── registry.py         # Skill registry
│   │   ├── loader.py           # Skill loader
│   │   ├── builder.py          # Skill graph builder
│   │   ├── tool.py             # Skill tool wrapper
│   │   └── content/            # Skill definitions directory
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
│   └── main.py                 # Application entry point
│
├── tests/                        # Test suite
│   ├── test_agent.py            # Agent integration tests
│   ├── test_file_sandbox.py     # File sandbox tests
│   ├── test_db_storage.py       # DuckDB storage tests (legacy)
│   ├── test_group_storage.py    # Group storage tests
│   ├── test_lancedb_vs.py       # Vector store tests
│   ├── test_python_tool.py      # Python execution tests
│   ├── test_status_middleware.py # Middleware tests
│   ├── test_scheduled_jobs.py   # Scheduler tests
│   ├── test_temporal_api.py     # Temporal integration tests
│   └── conftest.py             # Pytest fixtures
│
├── migrations/                   # PostgreSQL schema migrations
│   ├── 001_initial_schema.sql   # Initial tables (checkpoints, users, etc.)
│   ├── 002_workspace_to_group_rename.sql
│   ├── 003_add_identities_table.sql
│   └── 004_add_verification_codes.sql
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
│   ├── groups/                  # Group-scoped storage
│   │   └── {group_id}/
│   └── users/                   # Thread-scoped storage
│       └── {thread_id}/
│           ├── files/
│           ├── db/
│           ├── vs/
│           └── mem/
│
├── pyproject.toml                # Project dependencies & scripts
├── config.yaml                   # Default configuration
├── .env.example                  # Environment template
├── Dockerfile                    # Container definition
├── docker-compose.yml            # Development stack
├── langgraph.json                # LangGraph CLI configuration
├── README.md                     # User documentation
├── TODO.md                       # Development roadmap
└── CLAUDE.md                    # Development workflow notes
```

---

## Core Components

### 1. Agent Layer (`src/executive_assistant/agent/`)

**Purpose:** Implements the ReAct reasoning loop and manages agent state.

**Key Files:**
- `graph.py`: Defines LangGraph StateGraph with ReAct nodes
- `nodes.py`: Core node implementations
  - `call_model()`: Invokes LLM with conversation history
  - `call_tools()`: Executes LangChain tools
  - `increment_iterations()`: Tracks reasoning cycles
- `state.py`: AgentState TypedDict containing:
  - `messages`: Conversation history (with `add_messages` reducer)
  - `iterations`: Loop counter (prevents infinite loops)
  - `user_id`: Multi-tenant identifier
  - `channel`: Source channel (telegram/http)
  - `structured_summary`: Topic-based conversation summary
  - `todos`: Task tracking list
- `prompts.py`: System prompts for LLM reasoning
- `langchain_agent.py`: Alternative LangChain prebuilt agent runtime
- `status_middleware.py`: Real-time progress tracking with millisecond timing
- `todo_display.py`: Todo list display formatting

**Middleware Stack (via LangChain):**
1. **SummarizationMiddleware**: Token-based conversation summarization
2. **CallLimitMiddleware**: Prevents runaway execution (max 30 model calls, 50 tool calls per message)
3. **RetryMiddleware**: Automatic retry on transient failures
4. **TodoListMiddleware**: Tracks planned tasks
5. **ContextEditingMiddleware**: Edits context for efficiency
6. **StatusUpdateMiddleware**: Streams progress updates to user
7. **TodoListDisplayMiddleware**: Displays planned tasks during execution

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
- Bot Commands: `/start`, `/reset`, `/remember`, `/debug`, `/mem`, `/reminder`, `/vs`, `/db`, `/file`, `/meta`, `/user`
- Features:
  - Inline message editing for status updates (clean UI)
  - Debug mode toggle for verbose timing information
  - Per-thread asyncio locks to prevent message interleaving
  - Message queuing with deduplication
- Thread ID: Uses Telegram `chat_id` as `thread_id`
- User Management: Anonymous → merge to persistent `user_id`

#### HttpChannel (`http.py`)
- Built with FastAPI v0.115.0+
- Endpoints:
  - `POST /message`: Send message (supports SSE streaming)
  - `GET /conversations/{id}`: Get conversation history
  - `GET /health`: Health check
- Features:
  - Server-sent events (SSE) for real-time streaming
  - JSON request/response models (Pydantic)
  - CORS support for web integrations

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
│   ├── db/
│   └── vs/
├── groups/           # scope="context" with group_id
│   └── {group_id}/
│       ├── files/
│       ├── db/
│       └── vs/
└── users/            # scope="context" without group_id
    └── {thread_id}/
        ├── files/
        ├── db/
        ├── vs/
        └── mem/
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

**DBStorage (`sqlite_db_storage.py`, `db_tools.py`)**
- **Backend**: SQLite (context + shared)
- **Purpose**: Structured/tabular data storage
- **Use Cases**: Timesheets, logs, analysis datasets
- **Tools**:
  - `create_db_table`: Create from JSON/CSV with auto schema inference
  - `insert_db_table`, `query_db`: SQL operations
  - `list_db_tables`, `describe_db_table`: Schema inspection
  - `export_db_table`, `import_db_table`: Data portability (CSV, JSON, Parquet)
- **Legacy**: `db_storage.py` retains DuckDB utilities (deprecated)

**VectorStore (`lancedb_storage.py`, `vs_tools.py`)**
- **Backend**: LanceDB with sentence-transformers embeddings
- **Model**: `all-MiniLM-L6-v2` (384 dimensions)
- **Purpose**: Long-term knowledge retrieval
- **Use Cases**: Meeting notes, decisions, documentation
- **Features**:
  - Semantic search (vector similarity)
  - Hybrid search (full-text + vector)
  - Document chunking (configurable `chunk_size`)
  - Metadata filtering
- **Tools**:
  - `create_vs_collection`: Create collection with embeddings
  - `add_vs_documents`: Add documents (auto-chunking)
  - `search_vs`: Semantic search
  - `list_vs_collections`, `delete_vs_collection`: Collection management

**GroupStorage (`group_storage.py`)**
- **Purpose**: Group workspace management for team collaboration
- **Features**:
  - Group creation with verification codes
  - Permission management (read/write)
  - Group-scoped file/DB/VS paths
  - Admin access control
- **Metadata**: Stored in PostgreSQL `groups` table

**UserRegistry (`user_registry.py`)**
- **Purpose**: User identity management and multi-thread merging
- **Features**:
  - Anonymous thread tracking (via `thread_id`)
  - Thread merge to persistent `user_id`
  - Identity verification with codes
  - Ownership tracking (all files/DBs/reminders tied to `user_id`)
- **Tables**: `user_registry`, `identities`

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
  - `db_paths`: Database ownership per thread
  - `vs_collections`: Vector store ownership per thread
- **Operations**: Track all create/delete operations

**Reminder (`reminder.py`, `scheduled_jobs.py`)**
- **Purpose**: Scheduled notification system
- **Backend**: APScheduler (in-memory) + PostgreSQL persistence
- **Features**:
  - One-time and recurring reminders
  - Recurrence rules (daily, weekly, custom)
  - Multi-thread triggering (notify across conversations)
  - Timezone-aware scheduling
- **Table**: `reminders`

### 4. Tools Layer (`src/executive_assistant/tools/`)

**Purpose:** LangChain tool implementations that the agent can invoke.

**Tool Registry (`registry.py`)**
- `get_all_tools()`: Aggregates all tool categories
- Categories:
  - File tools (9 tools): File operations
  - DB tools (8 tools): Database operations
  - Time tools (3 tools): Timezone queries
  - Reminder tools (CRUD): Reminder management
  - Python tools (2 tools): Code execution
  - Search tools (1 tool): Web search via SearXNG
  - OCR tools (2 tools): Image/PDF text extraction
  - Firecrawl tools: Web scraping
  - Identity tools: User management
  - Memory tools: Memory extraction
  - Meta tools: System metadata

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
- **Config**: `ocr` section in `config.yaml`

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

### 6. Configuration Layer (`src/executive_assistant/config/`)

**Purpose:** Centralized configuration management.

**Components:**
- `settings.py`: Pydantic Settings class (environment + YAML)
- `llm_factory.py`: LLM model creation (provider-agnostic)
- `loader.py`: Load config from `config.yaml` and `.env`
- `constants.py`: Application constants

**Configuration Sources** (priority order):
1. Environment variables (`.env`)
2. `config.yaml` (application defaults)
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
    │  • Set thread_id, user_id in ContextVars
    │  • Acquire thread lock (prevent concurrent processing)
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
    │        • Read ContextVars (thread_id, user_id)
    │        • Access storage (file, DB, VS)
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
[Tool function executes]
    │
    ├─→ Read ContextVars (_thread_id, _user_id)
    │
    ├─→ Build scoped path:
    │      • if scope="shared" → data/shared/
    │      • if scope="context" with group_id → data/groups/{group_id}/
    │      • if scope="context" without group_id → data/users/{thread_id}/
    │
    ├─→ Check permissions:
    │      • FileSandbox: path traversal protection
    │      • GroupStorage: read/write permissions
    │      • MetaRegistry: ownership verification
    │
    ├─→ Access storage backend:
    │      • File: Local filesystem
    │      • DB: SQLite (context + shared)
    │      • VS: LanceDB (collection-scoped)
    │
    ├─→ Record operation:
    │      • MetaRegistry: Update ownership tracking
    │      • UserRegistry: Update audit log
    │
    └─→ Return results to agent
```

---

## Storage Architecture

### PostgreSQL Schema

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `checkpoints` | LangGraph state snapshots | `thread_id`, `checkpoint_ns`, `checkpoint_id` |
| `checkpoint_blobs` | Large message payloads | `thread_id`, `checkpoint_id`, `blob` |
| `conversations` | Conversation metadata | `thread_id`, `user_id`, `created_at` |
| `messages` | Message audit log | `thread_id`, `message_id`, `role`, `content` |
| `file_paths` | File ownership tracking | `thread_id`, `path`, `created_at` |
| `db_paths` | Database ownership tracking | `thread_id`, `db_name`, `created_at` |
| `user_registry` | User identity management | `user_id`, `merged_from`, `created_at` |
| `identities` | Identity verification | `user_id`, `verification_code`, `expires_at` |
| `reminders` | Scheduled reminders | `reminder_id`, `user_id`, `trigger_time`, `recurrence` |
| `groups` | Group workspaces | `group_id`, `name`, `verification_code` |
| `group_members` | Group membership | `group_id`, `user_id`, `role` |

### Data Isolation Model

**Thread-Level Isolation (Default)**
- Each conversation gets unique `thread_id` (e.g., Telegram chat_id)
- Data stored under `data/users/{thread_id}/`
- Prevents cross-thread data leakage

**Group-Level Isolation**
- Teams create shared workspaces with `group_id`
- Data stored under `data/groups/{group_id}/`
- All group members can access (with permissions)

**Organization-Level Sharing**
- Admins can write to `data/shared/`
- All users can read from shared storage
- Use cases: Company-wide knowledge, templates

**Identity Merge**
- Anonymous threads can merge into persistent `user_id`
- Ownership updated: `thread_id` → `user_id`
- Enables multi-thread access to user data

### Vector Store Architecture

**LanceDB Collections**
- Per-thread or per-group collections
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
- Used by default in `config.yaml`

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

**`config.yaml`** - Application Defaults
- LLM provider settings
- Storage paths
- Agent parameters
- Middleware thresholds
- Vector store settings
- OCR configuration

**`.env`** - Environment-Specific Overrides
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

1. **Load `config.yaml`** → `Settings` object
2. **Override with `.env`** → Environment variables
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

## Deployment Architecture

### Docker Deployment

**`Dockerfile`** - Multi-stage build
- Base: `python:3.13-slim`
- Dependencies: `uv sync --frozen`
- User: `executive_assistant` (non-root)
- Ports: 8000
- Volumes: `/app/data`

**`docker-compose.yml`** - Development stack
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
- `test_group_storage.py`: Group management
- `test_lancedb_vs.py`: Vector store operations
- `test_python_tool.py`: Python execution

**Integration Tests**
- `test_agent.py`: Agent execution with mock LLM
- `test_status_middleware.py`: Middleware behavior
- `test_temporal_api.py`: Temporal integration

**System Tests**
- `test_integration_pg.py`: Full PostgreSQL integration
- `test_scheduled_jobs.py`: Reminder scheduling

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
| 1.0.0 | 2026-01-21 | Initial technical architecture documentation |

---

**Document Author:** Generated via analysis of Executive Assistant codebase
**Contact:** See repository for issues and contributions
