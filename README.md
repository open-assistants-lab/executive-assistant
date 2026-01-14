# Cassey

Multi-channel AI agent platform with LangGraph ReAct agent.

## Features

- **ReAct Agent** - Tool-using agent with LangGraph
- **Multi-Channel** - Telegram, HTTP, Email (planned)
- **Thread/User Isolation** - Per-thread file and database storage
- **Merge Operations** - Merge threads into persistent user identity
- **Audit Logging** - Message and conversation tracking
- **Time Tools** - Current time/date in any timezone
- **Reminders** (Planned) - Scheduled notifications with recurrence

## Architecture

### Storage
- `conversations` - Conversation metadata per thread/channel
- `messages` - Full message audit log
- `file_paths` - File ownership tracking per thread
- `db_paths` - Database ownership tracking per thread
- `user_registry` - Operation audit log (merge/split/remove)

### Tools
- **File operations**: `read_file`, `write_file`, `list_files`
- **Database operations**: `create_table`, `query_table`, `insert_table`, `list_tables`, `describe_table`, `drop_table`, `export_table`, `import_table`
- **Time tools**: `get_current_time`, `get_current_date`, `list_timezones`
- **Other**: Calculator, Tavily search (when configured)

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
docker-compose up -d postgres_db

# Run migrations
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

### Key Columns

- `conversations.user_id` - NULL for anonymous, set after merge
- `file_paths.thread_id` - Maps to sanitized directory name
- `db_paths.thread_id` - Maps to .db file name

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

## Database Operations

Each thread gets its own database:

```
data/db/
  telegram_123456789.db
  http_abc123.db
```

Available tools:
- `create_table(name, columns)` - Create table with column definitions
- `create_table_from_data(name, data)` - Create from Python data
- `query_table(sql)` - Execute SQL query
- `insert_table(name, data)` - Insert rows
- `update_table(name, data, condition)` - Update rows
- `delete_table(name, condition)` - Delete rows
- `list_tables()` - Show all tables
- `describe_table(name)` - Show table schema

## Configuration

Environment variables:

```bash
# Required
OPENAI_API_KEY=sk-...
TELEGRAM_BOT_TOKEN=...
POSTGRES_URL=postgresql://...

# Channels
CASSEY_CHANNELS=telegram  # Options: telegram, http (comma-separated)

# Optional
TAVILY_API_KEY=...  # For web search
HTTP_HOST=0.0.0.0   # HTTP server host (default: 0.0.0.0)
HTTP_PORT=8000      # HTTP server port (default: 8000)
FILES_ROOT=./data/files  # Default file storage
DB_ROOT=./data/db        # Default DuckDB database storage
```

## Project Structure

```
cassey/
├── src/cassey/
│   ├── channels/       # Telegram, HTTP
│   ├── storage/        # User registry, file sandbox, database
│   ├── tools/          # LangChain tools (file, database, time, etc.)
│   ├── agent/          # LangGraph agent graph
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
