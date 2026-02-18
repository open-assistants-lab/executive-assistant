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
- [x] System prompts for Executive Assistant

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
- [x] CLI with Typer (`ea message`, `ea cli`, `ea http`)
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

### Phase 7: Daily Checkpoint Rotation + Progressive Disclosure History

**Goal:** Support long-term usage (1+ year) with fast resume times while preserving conversation context across thread boundaries using progressive disclosure.

#### Architecture

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

#### Implementation Tasks

**Part 1: Daily Checkpoint Rotation**
- [ ] Update `src/agent/factory.py` to use date-based thread IDs
  ```python
  async def get_or_create_thread_id(user_id: str, db_uri: str) -> str:
      """Get existing thread for today, or create new one."""
      from datetime import datetime
      import asyncpg

      date_key = datetime.now().strftime("%Y-%m-%d")
      thread_id = f"{user_id}-{date_key}"

      # Check if thread already has checkpoints
      async with asyncpg.connect(db_uri) as conn:
          row = await conn.fetchrow(
              "SELECT 1 FROM checkpoints WHERE thread_id = $1 LIMIT 1",
              thread_id
          )

          if row:
              # Thread exists, reuse it
              return thread_id

      # Thread doesn't exist yet, will be created on first invoke
      return thread_id

  # Usage in agent factory:
  async def create_ea_agent(...):
      thread_id = await get_or_create_thread_id(user_id, settings.database_url)
      config = {"configurable": {"thread_id": thread_id}}
      # ... create agent with config ...
  ```
- [ ] Thread metadata tracking:
  - Store date, message count, title/summary for each thread
  - Table: `thread_metadata (user_id, thread_id, date, message_count, title, created_at, last_updated)`
  - Update metadata after each checkpoint save
  ```python
  async def update_thread_metadata(user_id: str, thread_id: str, messages: list, db_uri: str):
      """Update thread metadata after checkpoint save."""
      import asyncpg

      # Generate title from first user message
      title = "Conversation"
      for msg in messages:
          if msg.type == "human":
              title = msg.content[:50] + ("..." if len(msg.content) > 50 else "")
              break

      async with asyncpg.connect(db_uri) as conn:
          await conn.execute("""
              INSERT INTO thread_metadata (user_id, thread_id, date, message_count, title, created_at, last_updated)
              VALUES ($1, $2, CURRENT_DATE, $3, $4, NOW(), NOW())
              ON CONFLICT (thread_id) DO UPDATE SET
                  message_count = $3,
                  last_updated = NOW()
          """, user_id, thread_id, len(messages), title)
  ```
- [ ] Migrate existing checkpoints to new format:
  - Script: `scripts/migrate_to_daily_threads.py`
  - Archive existing checkpoints by date
  - Generate thread metadata from existing checkpoints
- [ ] Update all interfaces to use date-based thread IDs:
  - Telegram bot: `src/telegram/bot.py`
  - HTTP API: `src/api/routes/chat.py`
  - CLI: `src/cli/main.py`

**Part 2: Progressive Disclosure Tools**
- [ ] Create `src/tools/history.py`:
  ```python
  """Progressive disclosure tools for conversation history."""

  import asyncpg
  from langchain_core.tools import tool
  from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

  # Tool factory that injects dependencies
  def create_history_tools(db_uri: str, get_user_id: callable):
      """Create history tools with database and user_id access."""

      @tool
      async def history_list(days: int = 7) -> str:
          """List available conversation checkpoints by date.

          Returns compact index of recent conversations with titles/topics.
          Use this to see what conversations are available before loading.

          Args:
              days: Number of recent days to list (default: 7)

          Returns:
              Formatted list of dates with conversation topics
          """
          user_id = get_user_id()

          async with asyncpg.connect(db_uri) as conn:
              rows = await conn.fetch("""
                  SELECT thread_id, date, message_count, title
                  FROM thread_metadata
                  WHERE user_id = $1
                    AND date >= CURRENT_DATE - INTERVAL '1 day' * $2
                  ORDER BY date DESC
              """, user_id, days)

              if not rows:
                  return f"No conversations found in the last {days} days."

              lines = [f"Recent conversations (last {days} days):"]
              for r in rows:
                  lines.append(f"  - {r['date']}: {r['title']} ({r['message_count']} messages)")

              return "\n".join(lines)

      @tool
      async def history_load(date: str) -> str:
          """Load full conversation from specific date.

          Use AFTER history_list() to see available dates.
          WARNING: This loads ~50-100 messages (~5,000 tokens).

          Args:
              date: Date in YYYY-MM-DD format (e.g., "2026-02-17")

          Returns:
              Full conversation history from that day's checkpoint
          """
          user_id = get_user_id()
          thread_id = f"{user_id}-{date}"

          async with AsyncPostgresSaver.from_conn_string(db_uri) as checkpointer:
              config = {"configurable": {"thread_id": thread_id}}
              checkpoint_tuple = await checkpointer.aget_tuple(config)

              if not checkpoint_tuple:
                  return f"No conversation found for {date}"

              # Extract messages from checkpoint
              checkpoint = checkpoint_tuple.checkpoint
              channel_values = checkpoint.get("channel_values", {})
              messages = channel_values.get("messages", [])

              # Format messages for agent
              formatted = [f"Conversation from {date}:"]
              for msg in messages:
                  if msg.type == "human":
                      content = msg.content[:100] + ("..." if len(msg.content) > 100 else "")
                      formatted.append(f"  User: {content}")
                  elif msg.type == "ai":
                      if hasattr(msg, "tool_calls") and msg.tool_calls:
                          tools = ", ".join([tc.get("name", "unknown") for tc in msg.tool_calls])
                          formatted.append(f"  Assistant: [Tools: {tools}]")
                      else:
                          content = msg.content[:100] + ("..." if len(msg.content) > 100 else "")
                          formatted.append(f"  Assistant: {content}")

              return "\n".join(formatted)

      @tool
      async def history_search(query: str, days: int = 30) -> str:
          """Search across recent conversations.

          Searches thread metadata titles for matching conversations.

          Args:
              query: Search query (e.g., "auth module")
              days: Search within last N days (default: 30)

          Returns:
              Relevant conversation snippets with dates
          """
          user_id = get_user_id()

          async with asyncpg.connect(db_uri) as conn:
              rows = await conn.fetch("""
                  SELECT thread_id, date, title
                  FROM thread_metadata
                  WHERE user_id = $1
                    AND date >= CURRENT_DATE - INTERVAL '1 day' * $2
                    AND title ILIKE $3
                  ORDER BY date DESC
                  LIMIT 5
              """, user_id, days, f"%{query}%")

              if not rows:
                  return f"No conversations matching '{query}' found in the last {days} days."

              lines = [f"Conversations matching '{query}':"]
              for r in rows:
                  lines.append(f"  - {r['date']}: {r['title']}")

              return "\n".join(lines)

      return [history_list, history_load, history_search]
  ```

- [ ] Update agent factory to register tools:
  ```python
  # In src/agent/factory.py
  from src.tools.history import create_history_tools

  async def create_ea_agent(...):
      # ... existing code ...

      # Create history tools with user_id context
      def get_user_id():
          return user_id

      history_tools = create_history_tools(
          db_uri=settings.database_url,
          get_user_id=get_user_id
      )

      agent_kwargs = {
          "tools": [
              get_current_time,
              web_search,
              # ... existing tools ...
              *history_tools,  # Add history tools
          ],
          # ... other kwargs ...
      }
  ```

**Part 3: Thread Metadata Storage**
- [ ] Add thread metadata table to PostgreSQL:
  ```sql
  CREATE TABLE thread_metadata (
      user_id TEXT NOT NULL,
      thread_id TEXT PRIMARY KEY,
      date TEXT NOT NULL,  -- YYYY-MM-DD
      message_count INTEGER DEFAULT 0,
      title TEXT,  -- Generated from first user message
      created_at TEXT NOT NULL,
      last_updated TEXT NOT NULL
  );

  CREATE INDEX idx_thread_metadata_user_date
    ON thread_metadata(user_id, date DESC);

  CREATE INDEX idx_thread_metadata_user_search
    ON thread_metadata(user_id, title);
  ```
- [ ] Update metadata after each checkpoint save:
  - Implemented in `update_thread_metadata()` above
  - Title generated from first user message (no LLM needed)
  - Message count updated on each checkpoint

**Part 4: System Prompt Integration**
- [ ] Update system prompt in `src/agent/factory.py`:
  ```python
  def _build_system_prompt(agent_name: str) -> str:
      return f"""You are {agent_name}, a deep agent with executive assistant capabilities.

  ## Conversation History
  You have access to past conversations via progressive disclosure:
  - history_list(days) → See available conversations
  - history_load(date) → Load full conversation from specific date
  - history_search(query) → Search across conversations

  Recent context is automatically available. For older conversations,
  use history_list() to see what's available, then history_load() if needed.

  ## Filesystem Structure (CRITICAL - Read This!)
  ...
  """
  ```

**Part 5: Configuration**
- [ ] Add checkpoint rotation config to `src/config/settings.py`:
  ```python
  from pydantic import Field

  class CheckpointConfig(BaseModel):
      """Checkpoint rotation and progressive disclosure configuration."""

      rotation_strategy: Literal["daily", "weekly", "monthly"] = Field(
          default="daily",
          description="Thread rotation strategy: daily, weekly, or monthly"
      )
      enable_progressive_disclosure: bool = Field(
          default=True,
          description="Enable progressive disclosure tools for history access"
      )
      history_retention_days: int = Field(
          default=365,
          description="Keep thread metadata for N days (cleanup after this)"
      )

  class Settings(BaseSettings):
      ...
      checkpoint: CheckpointConfig = Field(default_factory=CheckpointConfig)
  ```
- [ ] Add to `config.yaml`:
  ```yaml
  checkpoint:
    rotation_strategy: daily  # daily | weekly | monthly
    enable_progressive_disclosure: true
    history_retention_days: 365
  ```

**Part 6: Thread Metadata Tracking Middleware**
- [ ] Create `src/middleware/thread_metadata.py`:
  ```python
  """Middleware to track thread metadata after checkpoint saves."""

  import asyncpg
  from langchain.agents.middleware import AgentMiddleware
  from typing import TYPE_CHECKING

  if TYPE_CHECKING:
      from langchain.agents.middleware import AgentState
      from langgraph.runtime import Runtime

  class ThreadMetadataMiddleware(AgentMiddleware):
      """Track thread metadata (message count, title) after checkpoint saves."""

      def __init__(self, db_uri: str, user_id: str):
          super().__init__()
          self.db_uri = db_uri
          self.user_id = user_id

      async def aafter_agent(self, state: AgentState, runtime: Runtime) -> dict | None:
          """Update thread metadata after agent execution."""
          messages = state.get("messages", [])
          if not messages:
              return None

          # Get thread_id from config
          thread_id = runtime.config.get("configurable", {}).get("thread_id")
          if not thread_id:
              return None

          # Generate title from first user message
          title = "Conversation"
          for msg in messages:
              if msg.type == "human":
                  title = msg.content[:50] + ("..." if len(msg.content) > 50 else "")
                  break

          # Update metadata
          async with asyncpg.connect(self.db_uri) as conn:
              await conn.execute("""
                  INSERT INTO thread_metadata (user_id, thread_id, date, message_count, title, created_at, last_updated)
                  VALUES ($1, $2, CURRENT_DATE, $3, $4, NOW(), NOW())
                  ON CONFLICT (thread_id) DO UPDATE SET
                      message_count = $3,
                      last_updated = NOW()
              """, self.user_id, thread_id, len(messages), title)

          return None  # No state updates needed
  ```
- [ ] Integrate middleware into agent factory:
  ```python
  # In src/agent/factory.py
  from src.middleware.thread_metadata import ThreadMetadataMiddleware

  async def create_ea_agent(...):
      # ... existing code ...

      middlewares = create_middleware_from_config(
          config=settings.middleware,
          memory_store=memory_store,
          user_id=user_id,
          summarization_model=summarization_llm,
      )

      # Add thread metadata tracking middleware
      middlewares.append(
          ThreadMetadataMiddleware(
              db_uri=settings.database_url,
              user_id=user_id
          )
      )

      agent_kwargs["middleware"] = middlewares
      # ...
  ```

**Part 6: Testing**
- [ ] Unit tests for thread ID generation:
  - `test_get_thread_id()` → Verify format and consistency
  - `test_thread_id_same_day()` → Same thread ID within same day
  - `test_thread_id_next_day()` → Different thread ID next day
- [ ] Unit tests for progressive disclosure tools:
  - `test_history_list()` → Verify format and ordering
  - `test_history_load()` → Verify checkpoint replay
  - `test_history_search()` → Verify search functionality
- [ ] Integration tests:
  - `test_daily_rotation()` → Send messages across day boundary
  - `test_thread_persistence()` → Verify same thread used within day
  - `test_tool_usage()` → Agent uses history_list() and history_load()
- [ ] Manual testing scenarios:
  - Send messages, wait for day rollover, verify new thread
  - Ask "what did we work on yesterday?" → Agent loads yesterday
  - Ask "search for auth decisions" → Agent searches across threads

**Part 7: Migration**
- [ ] Migration script: `scripts/migrate_to_daily_threads.py`
  ```python
  # For each user:
  # 1. Get existing thread checkpoint
  # 2. Extract messages and metadata
  # 3. Determine date from first message
  # 4. Create new thread_id with date format
  # 5. Copy checkpoint to new thread_id
  # 6. Generate thread title
  # 7. Insert into thread_metadata table
  ```
- [ ] Rollback plan:
  - Backup existing checkpoints before migration
  - Keep old thread_ids as aliases in metadata
  - Script to revert if needed

#### Benefits

| Aspect | Before | After |
|--------|--------|-------|
| **Checkpoint size** | 10,000+ messages (unbounded) | ~50-100 messages (bounded) |
| **Resume time** | 5-10s (grows linearly) | <100ms (constant) |
| **Long-term access** | Slow (replay huge checkpoint) | Progressive (load on demand) |
| **Token efficiency** | ~1,000 (always summarized) | ~50 base + 5,000 on demand |
| **Complexity** | Simple | Simple (no summaries needed) |
| **Context preservation** | ✅ Full history | ✅ Full history (in checkpoints) |

#### Success Criteria

- [ ] Daily rotation works automatically (no manual thread management)
- [ ] Resume time stays <100ms even after 1 year of usage
- [ ] Progressive disclosure tools work correctly
- [ ] Agent can answer "what did we work on yesterday?" by loading checkpoint
- [ ] Thread metadata stored and queryable
- [ ] Memory system captures decisions/tasks (already working)
- [ ] Migration from existing threads is smooth
- [ ] Configuration via YAML works

#### Files to Create

- `src/tools/history.py` - Progressive disclosure tools
- `src/middleware/thread_metadata.py` - Thread metadata tracking middleware
- `scripts/migrate_to_daily_threads.py` - Migration script

#### Files to Modify

- `src/agent/factory.py` - Update thread ID logic, system prompt, add middleware
- `src/telegram/bot.py` - Use date-based thread IDs
- `src/api/routes/chat.py` - Use date-based thread IDs
- `src/cli/main.py` - Use date-based thread IDs
- `src/config/settings.py` - Add checkpoint config
- `src/middleware/factory.py` - Add ThreadMetadataMiddleware to stack (optional)

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

### Custom (Executive Assistant-specific)
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

Last updated: 2026-02-18
