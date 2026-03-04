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
- [x] memory_get_history - get conversation history
- [x] memory_search - hybrid keyword + semantic search

### Email Integration (IMAP/SMTP)
- [x] IMAP client for reading emails
- [x] SMTP client for sending emails
- [x] Email credential storage in accounts DB (no vault)
- [x] Multi-account support with account names
- [x] Auto-backfill sync on connect (newest → earliest)
- [x] Interval sync from config.yaml (5 min default)
- [x] Contacts parsed from email during sync
- [x] Contacts CRUD (add, update, delete, search)
- [x] Email tools: email_connect, email_disconnect, email_accounts, email_list, email_get, email_search, email_send, email_sync
- [x] Reply & Reply All support
- [x] Per-user DB isolation
- [x] Gmail rate limit handling (15 min cooldown)

### Todos System (LLM Extraction)
- [x] Per-user todos DB at data/users/{user_id}/todos/todos.db
- [x] LLM-based todo extraction from emails during sync
- [x] Manual todo creation (without email reference)
- [x] CRUD tools: todos_list, todos_add, todos_update, todos_delete
- [x] todos_extract tool for manual extraction

### Filesystem Tools
- [x] Per-user filesystem at data/users/{user_id}/files/
- [x] list_files, read_file, write_file, edit_file
- [x] delete_file with HITL approval
- [x] Path escape prevention

### File Search Tools
- [x] files_glob_search - file pattern matching
- [x] files_grep_search - regex content search

### Shell Tool
- [x] shell_execute - restricted command execution
- [x] Configurable allowed commands

### Time Tool
- [x] time_get - get current time with timezone support

### Skills System (Agent Skills Compatible)

### Interface
- [x] HTTP server (FastAPI, /message, /message/stream endpoints)
- [x] CLI (rich terminal UI with multi-line input)
- [x] Telegram bot

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
| Level 2: Instructions | On trigger | skills_load tool → returns SKILL.md |
| Level 3: Resources | As needed | Search within skill content |

**Architecture:**

1. **SkillMiddleware** (`before_agent` hook)
   - Loads skill metadata (name + description) from system + user skills
   - Injects into system prompt at runtime
   - Enables live refresh for skill updates

2. **skills_load tool**
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
- [x] Implement `skills_load` tool
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

**Phase 1: IMAP/SMTP (Simpler) - IMPLEMENTED**

Supported providers:
- Gmail / Google Workspace (enable IMAP + App Password)
- Outlook / Hotmail / Microsoft 365 (IMAP enabled by default)
- Any IMAP/SMTP provider

**Simplified Implementation (2026-02-27):**

```
src/tools/email/
├── __init__.py   # exports
├── account.py    # email_connect, email_disconnect, email_accounts
├── sync.py       # backfill sync + interval sync + email_sync tool
├── read.py       # email_list, email_get, email_search
└── send.py       # email_send (new, reply, reply_all)
```

**Tools:**
- [x] `email_connect` - Connect with account_name, auto-backfill on connect
- [x] `email_disconnect` - Remove account
- [x] `email_accounts` - List connected accounts
- [x] `email_list` - List emails (folder, limit)
- [x] `email_get` - Get full email by ID
- [x] `email_search` - Search by subject/sender
- [x] `email_send` - Send new, reply, reply_all
- [x] `email_sync` - Manual sync (new/full modes)
- [x] Auto-backfill on connect (newest → earliest)
- [x] Interval sync from config.yaml

**Config (config.yaml):**
```yaml
email_sync:
  enabled: true
  interval_minutes: 5
  batch_size: 100
  backfill_limit: 1000
```

**Removed:**
- ❌ email_delete (not needed)
- ❌ Vault (credentials stored in accounts DB)
- ❌ HITL for delete (not needed)
- ❌ email_stats (not essential)
- ❌ run_email_sql (not for users)

**Credentials Storage:**
- Stored directly in accounts SQLite DB
- No encryption (simplified - can add later if needed)
- Per-user isolation via user_id

**Contacts Parsing (During Email Sync):**

When syncing emails, parse contacts from:
- From: sender email + name
- To:/CC: recipients
- Reply-To: alternate address

```python
# In sync.py, after fetching email:
def _parse_contacts_from_email(msg) -> list[dict]:
    contacts = []
    
    # From
    if msg.from_:
        contacts.append({
            "email": msg.from_,
            "name": msg.from_values.name if msg.from_values else None,
        })
    
    # To/CC
    for addr in (msg.to or []) + (msg.cc or []):
        contacts.append({"email": str(addr)})
    
    return contacts
```

**Contacts CRUD:**
- [ ] `contacts_list` - List contacts
- [ ] `contacts_get` - Get single contact
- [ ] `contacts_add` - Add manual contact
- [ ] `contacts_update` - Update contact
- [ ] `contacts_delete` - Delete contact
- [ ] `contacts_search` - Search contacts
- [ ] `contacts_merge` - Merge duplicates

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

## Parallel Tool Calling (2026-03-04)

### Problem
Current agent runs tools **sequentially**, one at a time. This is the default behavior of LangChain's `create_agent`.

### Solution: Custom ParallelToolNode

**Complexity: 6/10** (~50-100 lines of code)

Create a custom `ParallelToolNode` that runs independent tool calls in parallel using `asyncio.gather()`.

**Implementation Approach:**

1. **Create `src/agents/parallel_tools.py`:**

```python
import asyncio
from typing import Any
from langchain_core.messages import ToolMessage
from langgraph.prebuilt.tool_node import ToolNode

class ParallelToolNode:
    """Tool node that executes tool calls in parallel."""
    
    def __init__(self, tools: list):
        self.tool_node = ToolNode(tools)
    
    async def invoke(self, state: dict[str, Any]) -> dict[str, Any]:
        messages = state.get("messages", [])
        last_message = messages[-1] if messages else None
        
        tool_calls = getattr(last_message, "tool_calls", []) or []
        
        if not tool_calls:
            return {"messages": []}
        
        # Execute all tools in parallel
        tasks = [
            self.tool_node.atool({"messages": [{"role": "assistant", "tool_calls": [tc]}]})
            for tc in tool_calls
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Collect tool messages, preserving order
        tool_messages = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                tool_messages.append(
                    ToolMessage(
                        content=f"Error: {str(result)}",
                        tool_call_id=tool_calls[i]["id"]
                    )
                )
            else:
                # Extract tool message from result
                result_msgs = result.get("messages", [])
                tool_messages.extend([m for m in result_msgs if isinstance(m, ToolMessage)])
        
        return {"messages": tool_messages}
```

2. **Modify `src/agents/factory.py`:**
   - Replace default `ToolNode` with `ParallelToolNode`
   - Or create a new `create_parallel_agent()` function

3. **Handle Edge Cases:**
   - Tool dependencies (some tools may depend on others)
   - Error aggregation (collect all errors, don't fail fast)
   - Message ordering (preserve tool call order for context)

**Benefits:**
- Faster execution for independent tool calls (e.g., fetching multiple emails)
- Better utilization of I/O-bound operations
- Maintains compatibility with existing agent infrastructure

**Trade-offs:**
- More complex error handling
- May not work well for dependent tool calls
- Need to detect which tools can run in parallel

---

## Subagent System (2026-03-04)

### Requirements

1. Main agent can hand over tasks to one or multiple subagents in parallel
2. Main agent can check subagent status and tool output during execution
3. Main agent can dynamically create subagents (not pre-built)
   - 3a. Dynamic prompt, skill, tools, MCP assignment
   - 3b. Schedule subagent invocation (one-off or recurring)
4. Force subagent to use planning-with-files skill
5. Main agent can track subagent progress via planning files
6. Langfuse tracing for subagents (if available)
7. Validation function for subagent configs
8. MCP via mcp.json per subagent

### Architecture

```
Main Agent
├── SubagentManager
│   ├── create(name, config) → subagent
│   ├── invoke(name, task) → result
│   ├── invoke_parallel(tasks) → results
│   └── get_status(job_id) → status
├── SubagentScheduler (APScheduler)
│   ├── schedule_once(name, task, datetime)
│   ├── schedule_recurring(name, task, cron)
│   └── cancel(schedule_id)
└── Tools
    ├── subagent_create
    ├── subagent_invoke
    ├── subagent_schedule
    ├── subagent_list
    ├── subagent_validate
    └── subagent_progress
```

### Folder Structure

```
data/users/{user_id}/subagents/{subagent_name}/
├── config.yaml         # name, model, description, skills, tools, system_prompt
└── .mcp.json          # MCP server configs for this subagent
```

### config.yaml Schema

```yaml
name: "research-assistant"
model: "anthropic:claude-sonnet-4-20250514"  # Optional, defaults to main agent model
description: "Research specialist for deep dives"

# Skills to assign to this subagent
skills:
  - planning-with-files  # Required, auto-added
  - deep-research

# Tools to assign to this subagent
tools:
  - files_read
  - files_write
  - memory_search
  - web_search
```

### Key Features

#### 1. Forced Planning Skill

Every subagent MUST use `planning-with-files` skill (auto-added):

```python
def create_subagent(user_id: str, config: SubagentConfig) -> CompiledStateGraph:
    # Load planning-with-files skill (REQUIRED)
    registry = SkillRegistry(system_dir="src/skills", user_id=user_id)
    planning_skill = registry.get_skill("planning-with-files")
    
    # Load additional skills from config
    skills_content = ""
    for skill_name in config.skills:
        if skill_name != "planning-with-files":
            skill = registry.get_skill(skill_name)
            if skill:
                skills_content += f"\n\n## {skill_name}\n{skill['content']}"
    
    system_prompt = f"""
{config.system_prompt or DEFAULT_SUBAGENT_PROMPT}

## Planning Skill (REQUIRED)
{planning_skill['content']}

{skills_content}

## Important
You MUST use the planning skill for ANY task that requires multiple steps.
Create a plan in `planning/{{task_name}}/task_plan.md` before executing.
Update `progress.md` after each step.
The main agent will track your progress via these files.
"""
    
    # Create subagent
    subagent = create_agent(
        model=get_model(config.model),
        tools=get_assigned_tools(config.tools),
        system_prompt=system_prompt,
        checkpointer=False,
    )
    
    return subagent
```

#### 2. Progress Tracking

```python
def get_subagent_progress(user_id: str, task_name: str) -> dict:
    """Read planning files to get subagent progress."""
    base = Path(f"data/users/{user_id}/workspace/planning/{task_name}")
    
    progress = {
        "task_plan": None,
        "progress": None,
        "findings": None,
    }
    
    for key in progress:
        file_path = base / f"{key}.md"
        if file_path.exists():
            progress[key] = file_path.read_text()
    
    return progress

def parse_task_status(task_plan_content: str) -> list[dict]:
    """Parse task_plan.md to get status of each phase."""
    # Parse markdown for - [ ] and - [x] items
    pass
```

#### 3. Langfuse Integration

```python
from langfuse import Langfuse

def create_subagent_with_tracing(user_id: str, config: SubagentConfig):
    langfuse = None
    if is_langfuse_available():
        langfuse = Langfuse()
    
    model = get_model(config.model)
    
    if langfuse:
        # Wrap model with langfuse
        model = langfuse.langchain.model_peewee(model)
    
    subagent = create_agent(
        model=model,
        tools=...,
        system_prompt=...,
    )
    
    return subagent
```

#### 4. MCP per Subagent

```python
# mcp.json format
{
    "filesystem": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/data/users/{user_id}/workspace"]
    },
    "brave-search": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-brave-search"],
        "env": {
            "BRAVE_API_KEY": "{env:BRAVE_API_KEY}"
        }
    }
}

def load_subagent_mcp(user_id: str, subagent_name: str) -> list[MCPConfig]:
    """Load MCP config for subagent."""
    mcp_path = Path(f"data/users/{user_id}/subagents/{subagent_name}/mcp.json")
    if not mcp_path.exists():
        return []
    
    mcp_config = json.loads(mcp_path.read_text())
    # Resolve {user_id} and {env:} placeholders
    return resolve_mcp_config(mcp_config)
```

#### 5. Validation (Integrated into Create)

Validation happens during subagent creation - if invalid, return errors so agent can fix and retry:

```python
class SubagentValidationResult(BaseModel):
    valid: bool
    errors: list[str] = []
    warnings: list[str] = []

def create_subagent(user_id: str, config: SubagentConfig) -> tuple[CompiledStateGraph | None, SubagentValidationResult]:
    """Create subagent with validation.
    
    Returns (subagent, validation_result). 
    If validation fails, subagent is None and errors explain what to fix.
    """
    # Validate first
    validation = validate_subagent_config(user_id, config)
    
    if not validation.valid:
        return None, validation
    
    # Build system prompt with skills
    # Create agent
    # ...
    
    return subagent, validation
```

**Validation checks:**
- Subagent name is valid (alphanumeric + hyphen)
- Referenced skills exist (system or user skills)
- Referenced tools exist in available tools
- mcp.json is valid JSON (if exists)
- system_prompt.md exists (warning if missing)

#### 6. APScheduler Integration

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

class SubagentScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.jobs: dict[str, dict] = {}  # job_id → config
    
    def schedule_once(self, user_id: str, subagent_name: str, task: str, run_at: datetime) -> str:
        job_id = f"{user_id}_{subagent_name}_{uuid.uuid4().hex[:8]}"
        
        self.scheduler.add_job(
            self._execute_subagent,
            trigger=DateTrigger(run_date=run_at),
            args=[user_id, subagent_name, task],
            id=job_id,
        )
        
        self.jobs[job_id] = {
            "user_id": user_id,
            "subagent_name": subagent_name,
            "task": task,
            "status": "scheduled",
        }
        
        return job_id
    
    def schedule_recurring(self, user_id: str, subagent_name: str, task: str, cron: str) -> str:
        job_id = f"{user_id}_{subagent_name}_{uuid.uuid4().hex[:8]}"
        
        self.scheduler.add_job(
            self._execute_subagent,
            trigger=CronTrigger.from_crontab(cron),
            args=[user_id, subagent_name, task],
            id=job_id,
        )
        
        self.jobs[job_id] = {
            "user_id": user_id,
            "subagent_name": subagent_name,
            "task": task,
            "schedule": cron,
            "status": "scheduled",
        }
        
        return job_id
    
    async def _execute_subagent(self, user_id: str, subagent_name: str, task: str):
        # 1. Load subagent config
        config = load_subagent_config(user_id, subagent_name)
        
        # 2. Create subagent with planning skill
        subagent = create_subagent(user_id, config)
        
        # 3. Execute task
        result = subagent.invoke({"messages": [{"role": "user", "content": task}]})
        
        # 4. Store result
        save_subagent_result(user_id, subagent_name, result)
        
        # 5. Update job status
        self.jobs[job_id]["status"] = "completed"
        self.jobs[job_id]["result"] = result
```

### Tools for Main Agent

```python
@tool
def subagent_create(name: str, model: str = None, description: str = "") -> str:
    """Create a new subagent."""

@tool
def subagent_invoke(name: str, task: str) -> str:
    """Invoke a subagent to execute a task."""

@tool
def subagent_schedule(name: str, task: str, schedule: str, run_at: str = None) -> str:
    """Schedule subagent: 'now', 'once' (with run_at), or cron expression."""

@tool
def subagent_list() -> str:
    """List all subagents."""

@tool
def subagent_validate(name: str) -> str:
    """Validate subagent configuration."""

@tool
def subagent_progress(task_name: str) -> str:
    """Get subagent progress from planning files."""
```

### Implementation Phases

| Phase | Tasks | Complexity | Status |
|-------|-------|------------|--------|
| **Phase 1** | SubagentManager, create/invoke tools, validation integrated | Medium | ✅ Complete |
| **Phase 2** | Forced planning skill, progress tracking | Medium | ✅ Complete |
| **Phase 3** | MCP per subagent (.mcp.json) | Medium | ✅ Complete |
| **Phase 4** | Langfuse tracing | Low | ✅ Complete |
| **Phase 5** | APScheduler integration (one-off, recurring) | Medium-High | ✅ Complete |
| **Phase 6** | Parallel invocation (multiple subagents) | Medium | ✅ Complete |

### Testing Approach

#### Unit Tests
- `tests/unit/test_subagent_manager.py`
  - Test subagent creation with config
  - Test tool assignment
  - Test skill injection
  
- `tests/unit/test_subagent_validation.py`
  - Test valid config passes
  - Test missing files fail
  - Test invalid YAML/JSON fails
  - Test skill/tool existence validation

- `tests/unit/test_subagent_planning.py`
  - Test planning skill is injected
  - Test progress files created correctly
  - Test main agent can read progress

#### Integration Tests
- `tests/integration/test_subagent_execution.py`
  - Test subagent executes task
  - Test planning files created
  - Test main agent reads progress

- `tests/integration/test_subagent_scheduling.py`
  - Test one-off schedule
  - Test cron schedule
  - Test schedule cancellation

#### Mock Tests
- Mock Langfuse (if not available)
- Mock scheduler execution
- Mock file system operations

---

Last updated: 2026-03-04
