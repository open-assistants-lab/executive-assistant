# Cassey

Multi-channel AI agent platform with LangGraph ReAct agent.

## Features

- **ReAct Agent** - Tool-using agent with LangGraph
- **Multi-Channel** - Telegram, HTTP, Email (planned)
- **Thread/User Isolation** - Per-thread file and database storage
- **Merge Operations** - Merge threads into persistent user identity
- **Audit Logging** - Message and conversation tracking
- **Time Tools** - Current time/date in any timezone
- **Reminders** - Scheduled notifications with recurrence
- **Web Search** - SearXNG integration
- **Python Execution** - Sandboxed code execution for calculations and data processing
- **File Search** - Glob patterns and grep content search

## Architecture

### Storage
- `conversations` - Conversation metadata per thread/channel
- `messages` - Full message audit log
- `file_paths` - File ownership tracking per thread
- `db_paths` - Database ownership tracking per thread
- `user_registry` - Operation audit log (merge/split/remove)
- `reminders` - Scheduled reminder notifications

### Thread-Scoped Storage Layout
All per-thread data lives under `data/users/{thread_id}/`:

```
data/users/{thread_id}/
  files/   # user files
  db/      # DuckDB workspace database
  kb/      # Knowledge base (SeekDB: seekdb.db + WAL + SHM)
  mem/     # embedded memory
```

### Tools
Note: Tool naming is being standardized to verb-first. Some tools may still be exposed under legacy names until the migration is complete.

**File Operations:**
- `file_read` - Read file contents (planned rename: `read_file`)
- `write_file` - Write files
- `list_files` - Browse directory contents
- `create_folder` / `delete_folder` / `rename_folder` - Folder management
- `move_file` - Move/rename files
- `glob_files` - Find files by pattern (`*.py`, `**/*.json`)
- `grep_files` - Search file contents with regex

**Workspace Database (per-thread, temporary):**
- `db_create_table` - Create table from JSON data
- `db_query` - Execute SQL queries
- `db_insert_table` - Insert rows into existing table
- `db_list_tables` - Show all tables in workspace
- `db_describe_table` - Show table schema
- `db_drop_table` - Delete a table
- `db_export_table` / `db_import_table` - Data export/import

**Knowledge Base (per-thread, vector + full-text search):**
- `create_kb_collection` - Create a KB collection with vector and FTS indexing
- `kb_search` - Hybrid search (vector + full-text with RRF rank fusion)
- `add_kb_documents` - Add documents to existing collection
- `kb_list` - List all KB collections with document counts
- `describe_kb_collection` - Show collection schema and samples
- `delete_kb_documents` - Delete documents from collection
- `drop_kb_collection` - Delete a KB collection

**Time & Reminders:**
- `time_get_current` - Current time in any timezone (planned rename: `get_current_time`)
- `time_get_current_date` - Current date (planned rename: `get_current_date`)
- `time_list` - Available timezones (planned rename: `list_timezones`)
- `set_reminder` - Create reminders with recurrence
- `list_reminders` - Show active reminders
- `cancel_reminder` - Cancel pending reminders
- `edit_reminder` - Modify existing reminders

**Code Execution:**
- `execute_python` - Sandboxed Python for calculations, data processing, file I/O
  - Thread-scoped file access
  - Allowed modules: json, csv, math, datetime, random, statistics, urllib, etc.
  - 30s timeout, path traversal protection

**Web Search:**
- `web_search` - Search via SearXNG

**OCR (optional, local):**
- `ocr_extract_text` - Extract text from images/PDFs (local OCR)
- `ocr_extract_structured` - OCR + LLM to produce structured JSON
- `extract_from_image` - Auto-select extraction method

**Other:**
- Calculator tool

### Thread vs User Isolation

- **Anonymous users**: Identified by `thread_id` (e.g., `telegram:123456789`)
- **Merged users**: Have persistent `user_id` with ownership across threads
- **Files & Database**: Each stored in sanitized thread-specific directories
- **Merge**: Updates ownership records only (no checkpoint migration)

## Quick Start

```bash
# Setup environment
cp .env.example .env
# Edit .env with your API keys

# Start PostgreSQL
docker-compose up -d

# Run migrations (auto-run on first start)
psql $POSTGRES_URL < migrations/001_initial_schema.sql

# Run bot (default: Telegram)
uv run cassey

# Run HTTP only
CASSEY_CHANNELS=http uv run cassey

# Run both Telegram and HTTP
CASSEY_CHANNELS=telegram,http uv run cassey
```

## HTTP API

When `CASSEY_CHANNELS=http`, a FastAPI server starts on port 8000:

```bash
# Send message (streamed by default)
curl -X POST http://localhost:8000/message \
  -H "Content-Type: application/json" \
  -d '{"content": "hello", "user_id": "user123", "stream": false}'

# Get conversation history
curl http://localhost:8000/conversations/http_user123

# Health check
curl http://localhost:8000/health
```

**Endpoints:**
- `POST /message` - Send message (supports SSE streaming)
- `GET /conversations/{id}` - Get conversation history
- `GET /health` - Health check

## Database Schema

### Core Tables

| Table | Purpose |
|-------|---------|
| checkpoints | LangGraph state snapshots |
| conversations | Conversation metadata per thread |
| messages | Message audit log |
| file_paths | File ownership per thread |
| db_paths | Database ownership per thread |
| user_registry | Operation audit (merge/split/remove) |
| reminders | Scheduled reminder notifications |

### Key Columns

- `conversations.user_id` - NULL for anonymous, set after merge
- `file_paths.thread_id` - Maps to sanitized directory name
- `db_paths.thread_id` - Maps to .db file name
- `reminders.user_id` - Owner of the reminder
- `reminders.thread_ids` - Threads that can trigger the reminder

## Merge Operations

Merge threads into a persistent user identity:

```python
from cassey.storage.user_registry import UserRegistry

registry = UserRegistry()
result = await registry.merge_threads(
    source_thread_ids=["telegram:123456", "http:abc123"],
    target_user_id="user@example.com"
)
# Returns: {conversations_updated, file_paths_updated, db_paths_updated}
```

**Important**: This updates ownership records only. LangGraph checkpoints remain separate.

## File Operations

Files are stored in per-thread directories:

```
data/files/
  telegram_123456789/
    notes.txt
    data.csv
  http_abc123/
    report.md
```

Sanitized thread_id used as directory name (replaces `:`, `/`, `@`, `\` with `_`).

### File Search

```python
# Find files by pattern
glob_files("*.py")           # All Python files
glob_files("**/*.json")       # Recursive JSON search
glob_files("test_*")          # Files starting with test_

# Search file contents
grep_files("TODO", output_mode="files")     # Which files contain TODO
grep_files("API_KEY", output_mode="content") # Show matching lines
grep_files("error", output_mode="count")     # Count matches
```

## Workspace Database (DB)

Each thread gets its own workspace database for temporary working data:

```
data/db/
  telegram_123456789.db
  http_abc123.db
```

Available tools:
- `db_create_table(table_name, data, columns)` - Create table from JSON
- `db_query(sql)` - Execute SQL query
- `db_insert_table(table_name, data)` - Insert rows
- `db_list_tables()` - Show all tables
- `db_describe_table(table_name)` - Show table schema
- `db_drop_table(table_name)` - Delete a table
- `db_export_table(table_name, filename, format)` - Export to CSV/JSON/Parquet
- `db_import_table(table_name, filename)` - Import from CSV

## Knowledge Base (KB)

The KB is per-thread (like workspace DB) and persists across sessions. Each conversation has its own KB stored under `data/users/{thread_id}/kb/`.

**Current Status:** Migration from DuckDB FTS to SeekDB (AI-native hybrid search) is in progress. See `discussions/seekdb-kb-remove-duckdb-plan-*.md` for details.

### SeekDB (New)

SeekDB provides vector + full-text hybrid search with RRF (Reciprocal Rank Fusion):

```
data/users/{thread_id}/kb/
  seekdb.db       # Main database (SQLite-based)
  seekdb.db-wal   # Write-Ahead Log
  seekdb.db-shm   # Shared memory
```

**SeekDB vs DuckDB KB:**
- **Vector search** - Semantic similarity with embeddings (384-dim ONNX, no API key)
- **Hybrid search** - Full-text + vector with RRF rank fusion
- **Collections** - Schema-flexible storage (not "tables")
- **Better RAG** - Purpose-built for AI/ML workloads

KB vs Workspace DB:
- **Workspace DB** (`db_*` tools): Temporary working data during analysis
- **Knowledge Base** (`kb_*` / `*_kb_*` tools): Longer-term reference data for retrieval

Available tools (SeekDB):
- `create_kb_collection(collection_name, documents)` - Create collection with vector + FTS
- `kb_search(query, collection_name, limit)` - Hybrid search (vector + full-text)
- `add_kb_documents(collection_name, documents)` - Add documents to collection
- `kb_list()` - List all collections with document counts
- `describe_kb_collection(collection_name)` - Show collection schema and samples
- `delete_kb_documents(collection_name, document_ids)` - Delete specific documents
- `drop_kb_collection(collection_name)` - Delete entire collection

**Example usage:**
```python
# Create collection with documents
create_kb_collection("notes", '[{"content": "Meeting: Q1 revenue was $1.2M", "metadata": "finance"}]')

# Hybrid search (semantic + full-text)
kb_search("revenue Q1", "notes")
# Returns ranked results with distances

# Add more documents
add_kb_documents("notes", '[{"content": "Q2 revenue projection: $1.5M"}]')

# List all collections
kb_list()
# Returns: Knowledge Base collections:
# - notes: 2 documents (vector + FTS indexed)
```

## Python Code Execution

The `execute_python` tool allows sandboxed Python execution:

```python
# Math calculations
execute_python("print(2 + 2)")
# "4"

# Data processing
execute_python("""
import csv, json
with open('data.csv') as f:
    data = list(csv.DictReader(f))
print(json.dumps(data))
""")

# File I/O (thread-scoped)
execute_python("""
with open('output.json', 'w') as f:
    json.dump({'result': 42}, f)
""")
```

**Security:**
- 30 second timeout
- Path traversal protection
- File extension whitelist
- Max file size: 10MB
- Thread-scoped directories

## Configuration

Environment variables:

```bash
# Required
OPENAI_API_KEY=sk-...
TELEGRAM_BOT_TOKEN=...
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=cassey
POSTGRES_PASSWORD=cassey_password
POSTGRES_DB=cassey_db

# Channels
CASSEY_CHANNELS=telegram  # Options: telegram, http (comma-separated)

# Optional
DEFAULT_LLM_PROVIDER=openai  # Options: openai, anthropic, zhipu
SEARXNG_HOST=https://searxng.example.com  # Web search
HTTP_HOST=0.0.0.0   # HTTP server host (default: 0.0.0.0)
HTTP_PORT=8000      # HTTP server port (default: 8000)
USERS_ROOT=./data/users  # Thread-scoped storage root
SHARED_DB_PATH=./data/shared/shared.db  # Shared organization-wide DB file
ADMIN_USER_IDS=  # Comma-separated admin user IDs for shared DB writes
ADMIN_THREAD_IDS=  # Comma-separated admin thread IDs for shared DB writes

# Agent runtime
AGENT_RUNTIME=langchain  # Options: langchain, custom
AGENT_RUNTIME_FALLBACK=  # Optional fallback runtime (e.g., custom)

# LangChain middleware
MW_SUMMARIZATION_ENABLED=true
MW_SUMMARIZATION_MAX_TOKENS=10000
MW_SUMMARIZATION_TARGET_TOKENS=2000
MW_MODEL_CALL_LIMIT=50
MW_TOOL_CALL_LIMIT=100
MW_TOOL_RETRY_ENABLED=true
MW_MODEL_RETRY_ENABLED=true
MW_HITL_ENABLED=false
MW_TODO_LIST_ENABLED=true              # TodoListMiddleware for multi-step task tracking
MW_CONTEXT_EDITING_ENABLED=false       # ContextEditingMiddleware (safety net, disabled by default)
MW_CONTEXT_EDITING_TRIGGER_TOKENS=100000  # Trigger token count for context trimming
MW_CONTEXT_EDITING_KEEP_TOOL_USES=10   # Number of recent tool uses to keep
```

Legacy storage paths (`FILES_ROOT`, `DB_ROOT`, `KB_ROOT`) are deprecated and only used for fallback reads.

Notes:
- `AGENT_RUNTIME=langchain` uses `MW_*` settings for middleware behavior.
- `AGENT_RUNTIME=custom` uses `ENABLE_SUMMARIZATION`, `SUMMARY_THRESHOLD`, and `MAX_ITERATIONS`.

## Project Structure

```
cassey/
├── src/cassey/
│   ├── channels/       # Telegram, HTTP
│   ├── storage/        # User registry, file sandbox, database, reminders
│   ├── tools/          # LangChain tools (file, database, time, python, search, etc.)
│   ├── agent/          # Agent runtimes (custom graph + LangChain)
│   ├── scheduler.py    # APScheduler integration
│   └── config/         # Settings
├── migrations/         # SQL migrations
├── tests/              # Unit tests
├── pyproject.toml
├── TODO.md
└── README.md
```

## Testing

```bash
# Run all tests
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/test_http.py -v
```

Integration tests (live LLM + VCR cassettes):

```bash
# Record live cassettes (requires API key + RUN_LIVE_LLM_TESTS=1)
RUN_LIVE_LLM_TESTS=1 uv run pytest -m "langchain_integration and vcr" --record-mode=once -v

# Or use the helper script
./scripts/pytest_record_cassettes.sh
```

Notes:
- Cassettes are stored in `tests/cassettes/`.
- If prompts/tools change, delete the cassette file and re-run to record a new baseline.
