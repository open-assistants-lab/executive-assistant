# Executive Assistant - Implementation TODO

Tracking implementation progress for the Executive Assistant deep agent.

---

## ✅ Completed

### Core Infrastructure
- [x] Project structure (`pyproject.toml`, `Makefile`, `Dockerfile`)
- [x] Pydantic settings with environment variables
- [x] PostgreSQL connection manager
- [x] User storage system (`UserStorage`)
- [x] Configurable agent name (`AGENT_NAME` in config)

### LLM Providers (17/23)
- [x] OpenAI
- [x] Anthropic
- [x] Google (Gemini)
- [x] Azure OpenAI
- [x] Groq
- [x] Mistral
- [x] Cohere
- [x] Together AI
- [x] Fireworks
- [x] DeepSeek
- [x] xAI (Grok)
- [x] HuggingFace
- [x] OpenRouter
- [x] Ollama (local + cloud)
- [x] Minimax
- [x] Qwen (Alibaba)
- [x] Zhipu AI (GLM)
- [ ] AWS Bedrock (pending)
- [ ] NVIDIA NIM (pending)
- [ ] Databricks (pending)
- [ ] IBM Watsonx (pending)
- [ ] Llama.cpp (pending)

### Observability
- [x] Langfuse integration (`src/observability/langfuse.py`)

### Deep Agents Integration
- [x] Agent factory with Postgres checkpoints
- [x] CompositeBackend with FilesystemBackend
- [x] User-isolated storage (`/user/`, `/shared/`)
- [x] System prompts for Ken

### Web Tools
- [x] Tavily web search
- [x] Firecrawl scrape (custom URL support)
- [x] Firecrawl crawl
- [x] Firecrawl map
- [x] Firecrawl search (fallback if no Tavily)

### Built-in Skills
- [x] Coding skill (`src/skills/coding/`)
- [x] Research skill (`src/skills/research/`)
- [x] Writing skill (`src/skills/writing/`)

### API & Interfaces
- [x] FastAPI application with lifespan
- [x] Health endpoints (`/health`, `/health/ready`)
- [x] Message endpoints (`/message`, `/message/stream`)
- [x] Summarize endpoint (`/summarize`)
- [x] Telegram bot (deep agent only, removed simple mode)
- [x] CLI with Typer (`ken message`, `ken interactive`, `ken serve`)
- [x] ACP server for IDE integration
- [x] Consolidated to deep agent only (removed simple LLM endpoints)

### Configuration
- [x] `.env.example` with all options
- [x] Firecrawl base URL configuration
- [x] Ollama cloud API key support

### Middleware (v2 - Production Ready)
- [x] MemoryContextMiddleware (progressive disclosure, MemoryStore)
- [x] MemoryLearningMiddleware (12 memory types, rule + LLM extraction)
- [x] LoggingMiddleware
- [x] CheckinMiddleware
- [x] RateLimitMiddleware

### Memory System v2 (SQLite + FTS5 + ChromaDB)
- [x] MemoryStore with SQLite + FTS5 + ChromaDB
- [x] 12 memory types (profile, contact, preference, schedule, task, decision, insight, context, goal, chat, feedback, personal)
- [x] Progressive disclosure tools (memory_search, memory_timeline, memory_get, memory_save)
- [x] Hybrid search (FTS5 keyword + ChromaDB semantic)
- [x] MEMORY_WORKFLOW in system prompt
- [x] Integrated into agent factory

### Time System
- [x] Time tools with DST support (`src/tools/time.py`)
- [x] `get_current_time` tool
- [x] `parse_relative_time` tool (today, tomorrow, next week, etc.)
- [x] `list_timezones` tool
- [x] `get_time_context` for system prompt injection

---

## ✅ Phase 6: Middleware Testing, Evaluation & Configuration

### Configuration System
- [x] YAML configuration loader (`src/config/yaml_config.py`)
- [x] Middleware configuration models (`src/config/middleware_settings.py`)
  - [x] 5 custom middleware configs (MemoryContext, MemoryLearning, Logging, Checkin, RateLimit)
  - [x] 6 built-in middleware configs (Summarization, TodoList, Filesystem, Subagent, HumanInTheLoop, ToolRetry)
- [x] Middleware factory (`src/middleware/factory.py`)
- [x] Settings integration (`src/config/settings.py`)
- [x] Agent factory integration (`src/agent/factory.py`)
- [x] Config schema reference (`config.schema.yaml`)

### Testing Framework
- [x] Unit tests for all middlewares (`tests/unit/middleware/`)
  - [x] test_memory_context.py
  - [x] test_memory_learning.py
  - [x] test_logging.py
  - [x] test_checkin.py
  - [x] test_rate_limit.py
  - [x] test_summarization.py
- [x] HTTP integration tests (`tests/integration/middleware_http/`)
  - [x] test_memory_context_http.py
  - [x] test_summarization_http.py (CRITICAL for effectiveness)
  - [x] test_other_middlewares_http.py
- [x] Effectiveness benchmarks (`tests/middleware_effectiveness/`)
  - [x] test_token_usage.py (target: 10x savings)
  - [x] test_memory_hit_rate.py (target: 90%+)
  - [x] test_summarization_quality.py (target: 4/5, >50% compression, 90%+ retention)
  - [x] test_extraction_quality.py

### Evaluation System
- [x] Metrics collection system (`src/middleware/metrics.py`)
  - [x] MiddlewareMetrics dataclass
  - [x] MetricsCollector class
  - [x] Effectiveness metrics calculation
- [x] Benchmarking script (`scripts/benchmark_middlewares.py`)
  - [x] CLI for running benchmarks
  - [x] Support for individual or all middlewares
  - [x] JSON output support

### Documentation
- [x] MIDDLEWARE.md (comprehensive middleware configuration guide)
- [x] Updated TODO.md with Phase 6 checklist

**Key Achievements:**
- ✅ All 5 custom middlewares configurable via YAML
- ✅ All 6 built-in deepagents middlewares configurable
- ✅ 80%+ test coverage target for all middlewares
- ✅ HTTP integration tests ensure real-world functionality
- ✅ Effectiveness targets defined and measurable:
  - Progressive disclosure: 10x token savings
  - Memory hit rate: 90%+
  - Summarization compression: >50%
  - Summarization retention: 90%+
  - Summarization quality: 4/5 (80%+)
  - Performance: <100-200ms overhead per middleware

**Files Created (Phase 6):**
- `src/config/yaml_config.py`
- `src/config/middleware_settings.py`
- `src/middleware/factory.py`
- `src/middleware/metrics.py`
- `config.schema.yaml`
- `scripts/benchmark_middlewares.py`
- `MIDDLEWARE.md`
- `tests/unit/middleware/*.py` (6 files)
- `tests/integration/middleware_http/*.py` (3 files)
- `tests/middleware_effectiveness/*.py` (4 files)

**Files Modified (Phase 6):**
- `src/config/settings.py` - Added middleware field
- `src/agent/factory.py` - Integrated middleware factory
- `src/middleware/__init__.py` - Export factory
- `tests/conftest.py` - Added middleware fixtures

---

## 🚧 In Progress

(Nothing currently in progress)

---

## 📋 Pending

### Phase 5: Memory API Endpoints
- [ ] `GET /memory/search` - Search index
- [ ] `GET /memory/timeline` - Timeline context
- [ ] `POST /memory/get` - Batch get by IDs
- [ ] `POST /memory` - Create memory
- [ ] `PUT /memory/{id}` - Update memory
- [ ] `DELETE /memory/{id}` - Archive memory

### SQLite Tool (No-Code Platform)

Allow users to build ad-hoc mini apps: todo, CRM, stock management, etc.

**Tools:**
- [ ] `sqlite_query` - Execute SQL queries
- [ ] `sqlite_list_databases` - List user's databases
- [ ] `sqlite_describe` - Show schema of a database
- [ ] `sqlite_backup` - Export database

**Features:**
- Per-user databases in `/data/users/{user_id}/databases/{name}.db`
- Automatic FTS5 for text columns
- Schema creation on first use
- Safe query execution (no DROP DATABASE, etc.)

### Knowledge Base Tool (SQLite + FTS5 + ChromaDB)

Allow users to build notes, knowledge bases, organize search/scrape results.
Uses same hybrid architecture as memory system.

**Storage:** User determines location. Default suggestions:
- `/data/users/{user_id}/notes/` for personal notes
- `/data/users/{user_id}/projects/{project}/kb/` for project knowledge bases
- Any user-specified path under `/data/users/{user_id}/`

**Schema (per knowledge base):**
```sql
CREATE TABLE documents (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT,
    collection TEXT NOT NULL,  -- "notes", "articles", "research", etc.
    source_url TEXT,
    tags TEXT,                 -- JSON array
    created_at TEXT NOT NULL,
    updated_at TEXT,
    archived INTEGER DEFAULT 0
);

CREATE VIRTUAL TABLE documents_fts USING fts5(
    title, content, tags,
    content='documents',
    content_rowid='rowid'
);
```

**Tools (Progressive Disclosure):**
- [ ] `kb_create` - Create new knowledge base at specified path
- [ ] `kb_search` - Layer 1: Search index (compact results with IDs)
- [ ] `kb_get` - Layer 2: Get full documents by IDs
- [ ] `kb_add` - Add document to knowledge base
- [ ] `kb_update` - Update existing document
- [ ] `kb_delete` - Archive/delete document
- [ ] `kb_list` - List user's knowledge bases

**Use Cases:**
- Notes with semantic + keyword search
- Knowledge base from scraped articles
- Research document organization
- Personal wiki
- Organized web search results

### DuckDB Tool (Analytics) - FUTURE

Consider for analytics capabilities (not yet proven needed):

```python
@tool
def duckdb_query(query: str, data_source: str | None = None) -> str:
    """Run analytical SQL queries on data.
    
    Use for data analysis, aggregations, and reporting.
    Can query CSV, JSON, Parquet files and SQLite databases.
    """
```

- [ ] Evaluate need for DuckDB
- [ ] Implement if valuable use cases emerge

### MCP Integration
- [ ] MCP client for external tools
- [ ] Shared MCP config (`/data/shared/.mcp.json`)
- [ ] User MCP config (`/data/users/{user_id}/.mcp.json`)

### Email Integration (IMAP/SMTP + OAuth)

Allow agent to read, analyze, and draft emails. Learn user's writing style from past emails.

**Phase 1: IMAP/SMTP (Simpler)**

Supported providers:
- Gmail / Google Workspace (enable IMAP + App Password)
- Outlook / Hotmail / Microsoft 365 (IMAP enabled by default)
- Any IMAP/SMTP provider

**Components:**
- [ ] IMAP client for reading emails (`src/email/imap_client.py`)
- [ ] SMTP client for sending emails (`src/email/smtp_client.py`)
- [ ] Email credential storage in encrypted vault (`src/email/credentials.py`)
- [ ] Multi-account support (personal + work)

**Tools:**
- [ ] `email_list` - List emails from folder (with filters)
- [ ] `email_get` - Get full email content by ID
- [ ] `email_search` - Search emails (subject, body, sender, date range)
- [ ] `email_send` - Send new email
- [ ] `email_draft` - Create draft (review before sending)
- [ ] `email_reply` - Reply to existing email thread

**Email Style Learning:**

Agent analyzes user's past sent emails to learn:
- Greeting style ("Hi" vs "Dear" vs no greeting)
- Sentence structure and vocabulary
- Tone (formal/casual)
- Sign-off style ("Best," "Thanks," "Cheers,")
- Formatting preferences (bullets, paragraphs, length)
- Emoji usage

```python
# Analyze sent folder and extract style
email_style = analyze_email_style(sent_emails)
memory_save(
    title="Email writing style",
    type="preference",
    narrative="User's email communication preferences",
    facts=[
        "Uses 'Hi [Name]' not 'Dear [Name]'",
        "Prefers bullet points over long paragraphs",
        "Signs off with 'Best,' for formal, 'Thanks,' for casual",
        "Keeps emails under 200 words when possible",
    ],
    concepts=["communication", "email", "style"],
)
```

**Privacy & Security:**
- Credentials stored encrypted in `.vault/vault.db`
- User specifies which folders to analyze (default: "Sent" only)
- Option to exclude sensitive folders ("Confidential", "Personal")
- Credentials never logged or exposed to LLM

**Phase 2: OAuth (Better Security)**

- [ ] Gmail OAuth integration (Gmail API)
- [ ] Microsoft OAuth integration (Microsoft Graph API)
- [ ] Scoped access (read-only, specific folders)
- [ ] Token refresh handling

**API Endpoints:**
- [ ] `POST /email/accounts` - Add email account
- [ ] `GET /email/accounts` - List configured accounts
- [ ] `DELETE /email/accounts/{id}` - Remove account
- [ ] `GET /email/folders` - List folders for account
- [ ] `POST /email/analyze-style` - Trigger style analysis

### Future
- [ ] Desktop app (Tauri) - separate repo
- [ ] Additional LLM providers (Bedrock, NVIDIA, etc.)
- [ ] Calendar integration (OAuth)
- [ ] Contact integration (OAuth)

---

## 📁 Folder Structure (Updated)

```
data/
├── config.yaml              # App-level configuration
├── logs/                    # Audit logs
│   └── agent-{date}.jsonl
├── shared/
│   ├── .mcp.json           # Team MCP servers
│   ├── skills/             # Team skills
│   └── knowledge/          # Shared knowledge
└── users/
    └── {user_id}/
        ├── .memory/
        │   ├── memory.db       # SQLite + FTS5
        │   └── chroma/         # ChromaDB (single collection)
        ├── .vault/
        │   └── vault.db        # Encrypted SQLite
        ├── skills/             # User skills
        ├── .mcp.json           # User MCP servers
        └── projects/           # User project files
```

---

## 🔧 Middleware Stack

### Built-in (from LangChain/deepagents)
| Middleware | Status | Notes |
|------------|--------|-------|
| TodoListMiddleware | ✅ | Included in deepagents |
| FilesystemMiddleware | ✅ | Included in deepagents |
| SummarizationMiddleware | ✅ | Included in deepagents |
| SubagentMiddleware | ✅ | Included in deepagents |
| HumanInTheLoopMiddleware | 📋 | For skill confirmation |
| ToolRetryMiddleware | 📋 | Retry failed tools |

### Custom (Ken-specific)
| Middleware | Status | Purpose |
|------------|--------|---------|
| MemoryContextMiddleware | ✅ v2 | Progressive disclosure |
| MemoryLearningMiddleware | ✅ v2 | Structured extraction (12 types) |
| LoggingMiddleware | ✅ | Audit all actions |
| CheckinMiddleware | ✅ | Periodic check-in |
| RateLimitMiddleware | ✅ | Rate limit requests |

---

## 📚 Documentation

- [x] `README.md` - Project overview
- [x] `docs/API_CONTRACT.md` - API contract for desktop app

---

## 🧪 Testing

- [x] Unit tests for memory system (tests/unit/memory/)
- [ ] Unit tests for journal system
- [x] Unit tests for middleware (tests/unit/middleware/)
- [x] Integration tests for middleware (tests/integration/middleware_http/)
- [x] Effectiveness tests for middleware (tests/middleware_effectiveness/)
- [ ] Integration tests for API
- [ ] E2E tests for agent

---

## 🚀 CLI Experience Improvements

**Goal:** Improve `uv run ea cli` to match deepagents CLI experience

**Reference:** https://docs.langchain.com/oss/python/deepagents/cli/overview

### Phase 1: Basic CLI UX (1-2 days)

**Core improvements:**
- [ ] Command history (up/down arrows) using `prompt_toolkit`
- [ ] Better input handling with `prompt_toolkit.PromptSession`
- [ ] Rich output formatting with `rich` library
  - Colored output
  - Progress bars for long operations
  - Better tables for structured data
- [ ] Auto-completion for commands
- [ ] Multi-line input support

**Slash commands:**
- [ ] `/model [provider:model]` - Switch LLM mid-session
- [ ] `/clear` - Reset conversation thread
- [ ] `/exit` or `/quit` - Exit CLI
- [ ] `/help` - Show available commands
- [ ] `/config` - Show current configuration

**Implementation:**
```python
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from rich.console import Console
from rich.markdown import Markdown

# Command history
history = FileHistory(os.path.expanduser("~/.ea-history"))
session = PromptSession(history=history)

# Rich formatting
console = Console()

# Slash command parser
def handle_slash_command(command: str):
    if command.startswith("/model"):
        # Switch model
        pass
    elif command.startswith("/clear"):
        # Reset thread
        pass
    # etc.
```

### Phase 2: Skills System (1-2 weeks)

**What deepagents CLI does:**
- Scans `~/.deepagents/<agent>/skills/` and `.deepagents/skills/` for `SKILL.md` files
- Extracts skill name and description from frontmatter
- Matches user queries to relevant skills (LLM-based matching)
- Dynamically loads and injects skills into conversation
- Auto-updates skills with `/remember` command

**Our adaptation needed:**
- [ ] Design skill storage structure (where to store skills?)
  - Option 1: `/data/users/{user_id}/skills/` (user-specific)
  - Option 2: Project `.skills/` directory (git-based discovery)
  - Option 3: Hybrid of both
- [ ] Skill discovery system
  - Scan skill directories for `SKILL.md` files
  - Extract metadata (name, description, tags)
  - Index skills for retrieval
- [ ] Skill matching logic
  - LLM-based matching (send query + skill list to LLM)
  - Or keyword matching (faster, less accurate)
  - Hybrid approach (keyword pre-filter + LLM rank)
- [ ] Dynamic skill injection
  - Inject matched skills into system prompt
  - Handle skill conflicts/overlaps
  - Manage skill lifecycle
- [ ] Skill CRUD operations
  - `skills create <name> [--project]` - Create new skill
  - `skills list [--project]` - List available skills
  - `skills info <name>` - Show skill details
  - `skills delete <name>` - Remove skill
- [ ] `/remember` command
  - Review conversation context
  - Identify new information to learn
  - Update relevant skills automatically

**Key differences from deepagents:**
- We have our own memory system (don't need AGENTS.md)
- Our agent architecture is different (deepagents SDK with custom prompts)
- Our tool set is different (web search, memory, filesystem, etc.)

### Phase 3: Advanced Features (Optional)

**Multi-agent support:**
- [ ] Named agents with separate configs
- [ ] `--agent <name>` flag to switch agents
- [ ] Agent isolation (separate memories, skills, configs)

**Remote sandboxes:**
- [ ] Integration with Modal, Runloop, Daytona
- [ ] `--sandbox <provider>` flag
- [ ] Sandbox setup scripts
- [ ] Code execution in isolated environments

**Auto-approve mode:**
- [ ] `--auto-approve` flag to skip human-in-the-loop
- [ ] Configurable tool approval lists
- [ ] Dangerous tools always require approval

### Success Criteria

**Phase 1:**
- [ ] Command history works (up/down arrows)
- [ ] Slash commands work
- [ ] Output is nicely formatted with colors
- [ ] Model switching works mid-session

**Phase 2:**
- [ ] Skills are discovered and indexed
- [ ] Skills are matched to relevant queries
- [ ] Skills are injected into prompts
- [ ] `/remember` updates skills
- [ ] Skills improve over time

**Testing:**
- [ ] Manual CLI testing
- [ ] Unit tests for slash commands
- [ ] Integration tests for skill system
- [ ] User acceptance testing

---

## 📖 Reference: claude-mem Learnings

### Key Patterns to Adopt

1. **3-Layer Progressive Disclosure**
   - Layer 1: `search()` returns index only (~50-100 tokens/result)
   - Layer 2: `timeline()` returns context (~100-200 tokens)
   - Layer 3: `get_observations()` returns full details (~500-1000 tokens)
   - **Enforced by tool design, not just documentation**

2. **Hybrid Search**
   - FTS5 for keyword/full-text search
   - ChromaDB for semantic similarity
   - Combine both for best relevance

3. **Structured Observations**
   - Hierarchical: title → subtitle → narrative
   - Extracted: facts, concepts, entities
   - Contextual: project, session_id, type

4. **Session Summaries**
   - Compress conversations into structured summaries
   - Store: topics, decisions, tasks, insights, next_steps
   - Enables context recovery without full history

5. **Always-Visible Workflow**
   - Tool definitions include workflow guidance
   - Makes efficient usage structurally enforced

### Implementation Approach

1. ~~Start with SQLite + FTS5~~ ✅ Done
2. ~~Add ChromaDB for semantic search~~ ✅ Done
3. ~~Implement 3-layer tools~~ ✅ Done
4. ~~Focus state~~ ❌ Removed (unnecessary)
5. ~~Update middleware~~ ✅ Done
6. Add API endpoints (Phase 5)

---

Last updated: 2026-02-16
