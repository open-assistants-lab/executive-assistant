# Executive Assistant - Implementation TODO

Tracking implementation progress for the Executive Assistant agent.

---

### Core Infrastructure
- [x] Project structure (`pyproject.toml`, `Makefile`, `Dockerfile`)
- [x] Pydantic settings with environment variables
- [x] PostgreSQL connection manager
- [x] User storage system (`UserStorage`)
- [x] Configurable agent name (`AGENT_NAME` in config)

### LLM Providers (23/23)
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
- [x] AWS Bedrock
- [x] NVIDIA NIM
- [x] Databricks
- [x] IBM Watsonx
- [x] Llama.cpp

### Observability
- [x] Langfuse integration

### Agents Integration
- [x] Agent factory with Postgres checkpoints
- [x] User-isolated storage (`/user/`, `/shared/`)
- [x] System prompts for Executive Assistant
- [x] Per-user agent pool for concurrent request handling

### Web Tools
- [x] Firecrawl scrape (custom URL support)
- [x] Firecrawl crawl
- [x] Firecrawl map
- [x] Firecrawl search

### Memory System (SQLite + FTS5 + ChromaDB)
- [x] Custom MemoryStore with SQLite + FTS5 + ChromaDB
- [x] Hybrid search (FTS5 keyword + ChromaDB semantic)
- [x] Memory tools: search_conversation_hybrid, get_conversation_history

### Email Integration (IMAP/SMTP)
- [x] IMAP client for reading emails
- [x] SMTP client for sending emails
- [x] Email credential storage in encrypted vault
- [x] Multi-account support
- [x] Email tools: email_list, email_get, email_search, email_send

### Skills System (Agent Skills Compatible)

**Reference:**
- https://docs.langchain.com/oss/python/langchain/multi-agent/skills-sql-assistant
- https://agentskills.io/specification
- https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview

**Purpose & Benefit:**

Skills enable progressive disclosure - loading specialized information on-demand rather than upfront. Based on Agent Skills spec.

**Directory Structure:**

```
src/skills/{skill_name}/           # System skills
└── SKILL.md                       # YAML frontmatter + markdown body

data/users/{user_id}/skills/{skill_name}/  # User skills
└── SKILL.md
```

**SKILL.md Format:**

```yaml
---
name: pdf-processing
description: Extract text and tables from PDF files, fill forms, merge documents.
---

# Instructions
[Full skill content here]
```

**Progressive Disclosure (3 Levels):**

| Level | When | Our Implementation |
|-------|------|-------------------|
| Level 1: Metadata (~100 tokens) | Startup | SkillMiddleware → system prompt |
| Level 2: Instructions | On trigger | load_skill tool → returns SKILL.md |
| Level 3: Resources | As needed | Search within skill content |

**Architecture:**

1. **SkillMiddleware** (`before_agent` hook)
   - Loads skill metadata (name + description) from system + user skills
   - Injects into system prompt at runtime
   - Enables live refresh for skill updates

2. **load_skill tool**
   - Returns full SKILL.md content when triggered
   - Progressive disclosure: description in prompt, content via tool
   - Optional: track loaded skills in custom state

3. **Constrained tools** (mandatory)
   - Tools that require specific skill to be loaded first
   - Check `runtime.state.get("skills_loaded", [])`
   - Return error if skill not loaded, guide agent to load it

**Skill Validation:**

- Use [skills-ref](https://github.com/agentskills/agentskills/tree/main/skills-ref) for validation
- Future: Add `validate_skill` CLI command for troubleshooting

**User Management:**

- File-based: Create/edit SKILL.md in user skills directory
- CLI: `ea skill list`, `ea skill add`, `ea skill remove`
- API: `GET/POST/PUT/DELETE /skills`

**Implementation Steps:**

- [x] Create skill schema (SKILL.md parser with YAML frontmatter)
- [x] Implement skill storage layer (file-based, directory scanning)
- [x] Implement skill registry (combine system + user skills)
- [x] Create SkillMiddleware with `before_agent` hook
- [x] Implement `load_skill` tool
- [x] Implement custom state for tracking loaded skills
- [x] Implement skill-gated tool pattern
- [x] Add CLI commands for skill management
- [x] Add API endpoints for skill management
- [ ] Add `validate_skill` command (future)
- [x] Create sample system skills

### API & Interfaces
- [x] FastAPI application with lifespan
- [x] Health endpoints (`/health`, `/health/ready`)
- [x] Message endpoints (`/message`, `/message/stream`)
- [x] Telegram bot
- [ ] ACP server for IDE integration

### Configuration
- [x] `.env.example` with keys & URLs
- [x] 'config.yaml' with all configurations
- [x] Ollama cloud API key support

### Custom Middleware
- [x] MemoryContextMiddleware (progressive disclosure, MemoryStore)
- [ ] MemoryLearningMiddleware (12 memory types, rule + LLM extraction)
- [x] LoggingMiddleware
- [ ] CheckinMiddleware
- [ ] RateLimitMiddleware

### Time System
- [x] Time tools with DST support (`src/tools/time.py`)
- [x] `get_current_time` tool
- [x] `get_time_context` for system prompt injection

### Memory System (Custom - SQLite + FTS5 + ChromaDB)
**Note:** Replaces LangGraph store - we use our own custom memory for better control.

- [x] Custom MemoryStore with SQLite + FTS5 + ChromaDB
- [ ] 12 memory types (profile, contact, preference, schedule, task, decision, insight, context, goal, chat, feedback, personal)
- [x] Progressive disclosure tools (memory_search, memory_timeline, memory_get, memory_save)
- [x] Hybrid search (FTS5 keyword + ChromaDB semantic)
- [x] MEMORY_WORKFLOW in system prompt
- [x] Integrated into agent factory as tools

### Time System
- [x] Time tools with DST support (`src/tools/time.py`)
- [x] `get_current_time` tool
- [x] `parse_relative_time` tool (today, tomorrow, next week, etc.)
- [x] `list_timezones` tool
- [x] `get_time_context` for system prompt injection


### Daily Checkpoint Rotation + Progressive Disclosure History

**Goal:** Support long-term usage (1+ year) with fast resume times while preserving conversation context across thread boundaries using progressive disclosure.

**Constraint:** Single-thread per user (thread_id = user_id)

#### Architecture

**Short-term Memory (Checkpoint - LangGraph):**
- Full conversation persisted via PostgresSaver
- thread_id = user_id (single thread per user)
- Enables: resume, time travel, fault tolerance

**Long-term Memory (Store - LangGraph):**
- User profiles, preferences, learned facts
- Cross-session: accessible from any thread
- Use PostgresStore for production

**Summarization (Built-in):**
- Use `SummarizationMiddleware` from LangChain
- Trigger at ~4000 tokens, keep recent 20 messages
- Summary replaces old messages permanently

**Progressive Disclosure (3 Layers):**

```
Layer 1: Compact index (~50 tokens)
  └─ history_list() → Show available dates with brief titles

Layer 2: Load specific checkpoint on demand (~5,000 tokens)
  └─ history_load(date) → Full conversation from that date

Layer 3: Full replay (same as Layer 2)
  └─ Checkpoint already loaded, agent processes full context
```

**Example Usage:**

```
User: "What did we work on yesterday?"
→ Agent: history_list() → ["2026-02-17: Auth debugging", "2026-02-16: Planning"]
→ Agent: history_load("2026-02-17") → Gets full conversation
→ Agent: Answers with exact details from yesterday

User: "What did we decide about the tech stack?"
→ Agent: Searches memory (already has decision: "Chose React")
→ Agent: Answers from memory (no checkpoint load needed)
```

### SQLite Tool (No-Code Tool)

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

### SQLite + FTS5 + ChromaDB (Knowledge Base Tool)

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

### DuckDB / chDB (Analytics Tool) - FUTURE

Consider for analytics capabilities (not yet proven needed):

- [ ] Evaluate need for DuckDB / chDB
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
- [x] IMAP client for reading emails (`src/email/imap_client.py`)
- [x] SMTP client for sending emails (`src/email/smtp_client.py`)
- [x] Email credential storage in encrypted vault (`src/email/credentials.py`)
- [x] Multi-account support (personal + work)

**Tools:**
- [x] `email_list` - List emails from folder (with filters)
- [x] `email_get` - Get full email content by ID
- [x] `email_search` - Search emails (subject, body, sender, date range)
- [x] `email_send` - Send new email
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
├── logs/                    # Audit logs
│   └── {date}.jsonl
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

### Built-in (from LangChain)
| Middleware | Purpose |
|------------|---------|
| TodoListMiddleware | Manage task lists |
| HumanInTheLoopMiddleware | Human approval for tools |
| ShellToolMiddleware | Execute shell commands |
| SubAgentMiddleware | Create sub-agents |
| FilesystemFileSearchMiddleware | Search files |
| ContextEditingMiddleware | Edit context |
| FilesystemMiddleware | File operations |
| SummarizationMiddleware | Summarize conversations |
| ToolRetryMiddleware | Retry failed tools |

### Custom (Executive Assistant-specific)
| Middleware | Status | Purpose |
|------------|--------|---------|
| MemoryContextMiddleware | ⏳ | Progressive disclosure |
| MemoryLearningMiddleware | ⏳ | Structured extraction (12 types) |
| LoggingMiddleware | ⏳ | Audit all actions |
| CheckinMiddleware | ⏳ | Periodic check-in |
| RateLimitMiddleware | ⏳ | Rate limit requests |

---

## 📚 Documentation

- [ ] `README.md` - Project overview
- [ ] `docs/API_CONTRACT.md` - API contract for desktop app

---

## 🧪 Testing

- [ ] Unit tests for memory system (tests/unit/memory/)
- [ ] Unit tests for journal system
- [ ] Unit tests for middleware (tests/unit/middleware/)
- [ ] Integration tests for middleware (tests/integration/middleware_http/)
- [ ] Effectiveness tests for middleware (tests/middleware_effectiveness/)
- [ ] Integration tests for API
- [ ] E2E tests for agent

---

## 🚀 CLI Experience

**Goal:** Improve CLI to have rich UX

### Phase 1: Basic CLI UX

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

### Phase 2: Skills System

**Skill storage:**
- `/data/users/{user_id}/skills/` (user-specific)
- Project `.skills/` directory

**Features:**
- [ ] Skill discovery system (scan for `SKILL.md` files)
- [ ] Skill matching logic (LLM-based)
- [ ] Dynamic skill injection
- [ ] Skill CRUD operations
- [ ] `/remember` command

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

---

## ⚠️ Architecture Constraints

- **Single-threaded per user**: Each user has one active conversation thread
- All checkpoint/state management must account for this
- Memory access patterns should be optimized for single-user workloads

---

## Agent Concurrency Research (2026-02-24)

### Problem
- Concurrent requests for the same user cause race conditions (empty responses)
- Root cause: LangGraph's checkpointer uses `thread_id` for isolation
- Same `thread_id` = concurrent access to same state = race conditions

### Research Findings
1. **LangGraph thread isolation**: Different `thread_id` = safe. Same = NOT safe
2. **Each user should have unique thread_id** - but this is per conversation, not per request
3. **Solution**: Per-user agent pool with locking OR fresh agent per request

### Options for 10-100 users
1. **Fresh agent per request** - Works but inefficient (slow, high memory)
2. **Per-user agent pool** - 2-3 agents per user, acquire/release
3. **Queue-based** - For 100+ users, use task queue (Redis + workers)

### Decision: Agent Pool
- Balanced approach: efficiency + correctness
- Implement in HTTP server

---

Last updated: 2026-02-24
