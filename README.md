# Cassey

Your intelligent assistant that manages tasks, tracks work, stores knowledge, and never forgets a reminder.

## What Cassey Can Do For You

Cassey is a multi-channel AI agent that helps you stay organized and productive. Whether you're tracking timesheets, managing a knowledge base, or automating data analysis, Cassey intelligently selects the right tools for the job.

### Track Your Work
- **Timesheet logging**: Simply tell Cassey what you worked on, and it stores structured data in your private database
- **Time-aware**: Knows the current time in any timezone, perfect for distributed teams
- **Data analysis**: Query your logged work with SQL, export to CSV/JSON, or visualize trends

### Never Forget a Reminder
- **Scheduled notifications**: "Remind me to review PRs at 3pm every weekday"
- **Recurring patterns**: Daily, weekly, or custom schedules with flexible recurrence rules
- **Multi-channel delivery**: Get reminders on Telegram or HTTP webhook

### Build a Knowledge Base
- **Semantic search**: Store documents and find them by meaning, not just keywords
- **Smart retrieval**: Ask "What did we decide about the API pricing?" and get the right answer
- **Workspace collaboration**: Share knowledge across team conversations while keeping private data isolated

### Automate Data Work
- **Python execution**: Run calculations, data processing, and file operations in a secure sandbox
- **Web search**: Find current information from the web
- **File operations**: Read, write, search, and organize files with natural language commands

### Intelligent Tool Selection
Cassey uses a skills system to choose the right approach:
- **Database tools** for structured data and temporary analysis (timesheets, logs, datasets)
- **Vector Store** for long-term knowledge retrieval (meeting notes, decisions, documentation)
- **File tools** for browsing and exact-text search (codebases, document archives)

You don't need to remember which tool does what—Cassey figures it out from context.

## How Cassey Thinks

Cassey is a **ReAct agent** built on LangGraph. Unlike simple chatbots, it:

1. **Reasons** about your request using an LLM
2. **Acts** by calling tools (file operations, database queries, web search, etc.)
3. **Observes** the results and decides what to do next
4. **Responds** with a clear confirmation of what was done

This cycle continues until your task is complete—with safeguards to prevent infinite loops.

### Real-Time Progress Updates
Cassey keeps you informed while working:
- **Normal mode**: Clean status updates edited in place
- **Debug mode**: Detailed timing information (toggle with `/debug`)
- **Per-message limits**: Prevents runaway execution (20 LLM calls, 30 tool calls per message)

## Multi-Channel Access

Cassey works where you work:

### Telegram
- Chat with Cassey in any Telegram conversation
- Commands: `/start`, `/help`, `/reminders`, `/groups`, `/debug`, `/id`
- Perfect for mobile quick-tasks and reminders on-the-go

### HTTP API
- Integrate Cassey into your applications
- REST endpoints for messaging and conversation history
- SSE streaming for real-time responses
- Ideal for workflows, webhooks, and custom integrations

## Storage That Respects Your Privacy

Cassey takes data isolation seriously:

### Thread-Scoped Storage (Private)
Each conversation gets its own isolated workspace:
- **Files**: Private file storage for that conversation
- **Database**: Temporary working data (timesheets, analysis results)
- **Memories**: Embedded user memories for personalization

Files and databases live under `data/users/{thread_id}/`—completely separated from other users.

### Workspace Storage (Shared)
For team collaboration, create shared workspaces under `data/groups/{workspace_id}/`:
- **Vector Store**: Long-term knowledge base accessible to all team members
- **Files**: Shared documents and resources
- **Database**: Team-wide datasets and analysis

### Merge & Identity Management
- Start as anonymous (identified by `thread_id`)
- Merge multiple threads into a persistent `user_id`
- Ownership tracking for all files, databases, and reminders
- Audit log for all operations

## Quick Start

```bash
# Setup environment
cp .env.example .env
# Edit .env with your API keys

# Start PostgreSQL
docker-compose up -d postgres_db

# Run migrations (auto-run on first start)
psql $POSTGRES_URL < migrations/001_initial_schema.sql

# Run Cassey (default: Telegram)
uv run cassey

# Run HTTP only
CASSEY_CHANNELS=http uv run cassey

# Run both Telegram and HTTP
CASSEY_CHANNELS=telegram,http uv run cassey
```

**For local testing**, always use `uv run cassey` instead of Docker. Only build Docker when everything works (see `CLAUDE.md` for testing workflow).

## What Makes Cassey Different

### Unlike Simple Chatbots
- **Tool-using**: Can read files, query databases, search the web, execute Python
- **Persistent**: Remembers context across sessions with PostgreSQL checkpointing
- **Multi-step**: Handles complex tasks that require multiple tool calls
- **Safe**: Sandboxed execution, per-message limits, audit logging

### Unlike Other AI Agents
- **Intelligent storage**: Knows when to use DB (structured) vs VS (semantic) vs files (raw)
- **Skills system**: Progressive disclosure of advanced patterns (load with `load_skill`)
- **Privacy-first**: Thread isolation by design, merge only when you request it
- **Multi-channel**: Same agent works on Telegram, HTTP, and more (planned: Email, Slack)

### Production-Ready Features
- **Middleware stack**: Summarization, retry logic, call limits, todo tracking, context editing
- **High-precision logging**: Millisecond timestamps for performance analysis
- **Debug mode**: Toggle verbose status updates to understand agent behavior
- **Status updates**: Real-time progress feedback during long-running tasks

## Example Workflows

### Timesheet Tracking
```
You: Log 4 hours of API development
Cassey: Created timesheet table and logged entry.

You: How many hours did I work this week?
Cassey: [queries database] You worked 32 hours total:
     - API development: 16h
     - Bug fixes: 12h
     - Meetings: 4h
```

### Knowledge Management
```
You: Save this: API rate limit is 1000 req/min for pro accounts
Cassey: Saved to knowledge base.

You: What's the rate limit for pro accounts?
Cassey: [searches vector store] 1000 requests per minute.
```

### Data Analysis
```
You: Analyze this CSV and find the average
Cassey: [imports CSV, runs Python] The average is 42.7.
     I've created a chart and saved it to analysis.png.
```

## Configuration

Essential environment variables:

```bash
# LLM Provider (choose one)
OPENAI_API_KEY=sk-...           # OpenAI (GPT-4, GPT-4o)
ANTHROPIC_API_KEY=sk-...        # Anthropic (Claude)
ZHIPU_API_KEY=...               # Zhipu (GLM-4)

# Channels
CASSEY_CHANNELS=telegram,http   # Available channels

# Telegram (if using telegram channel)
TELEGRAM_BOT_TOKEN=...

# PostgreSQL (required for state persistence)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=cassey
POSTGRES_PASSWORD=your_password
POSTGRES_DB=cassey_db
```

See `.env.example` for all available options.

## Telegram Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Start conversation / show welcome message |
| `/help` | Show available commands and usage |
| `/reminders` | List active reminders |
| `/groups` | Manage shared workspaces |
| `/debug` | Toggle verbose status mode (see LLM/tool timing) |
| `/id` | Show your user/thread ID for debugging |

### Debug Mode

Toggle detailed progress tracking:

```bash
/debug           # Show current debug status
/debug on        # Enable verbose mode (see all LLM calls and tools)
/debug off       # Disable (clean mode, status edited in place)
/debug toggle    # Toggle debug mode
```

**Normal mode:** Status messages are edited in place (clean UI)
**Verbose mode:** Each update sent as separate message with LLM timing

Example verbose output:
```
🤔 Thinking...
✅ Done in 12.5s | LLM: 2 calls (11.8s)
```

## HTTP API

When `CASSEY_CHANNELS=http`, a FastAPI server starts on port 8000:

```bash
# Send message
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

## Tool Capabilities

### File Operations
- **Read/write**: Create, edit, and organize files
- **Search**: Find files by pattern (`*.py`, `**/*.json`) or search contents with regex
- **Secure**: Thread-scoped paths prevent access to other users' data

### Database (per-thread)
- **Create tables**: From JSON/CSV with automatic schema inference
- **Query**: Full SQL support via DuckDB
- **Import/Export**: CSV, JSON, Parquet formats
- **Use case**: Temporary working data (timesheets, logs, analysis results)

### Vector Store (per-workspace)
- **Semantic search**: Find documents by meaning, not just keywords
- **Hybrid search**: Combines full-text + vector similarity
- **Persistent**: Survives thread resets (workspace-scoped)
- **Use case**: Long-term knowledge base (meeting notes, decisions, docs)

### Python Execution
- **Sandboxed**: 30s timeout, path traversal protection, thread-scoped I/O
- **Modules**: json, csv, math, datetime, random, statistics, urllib, etc.
- **Use case**: Calculations, data processing, file transformations

### Web Search
- **SearXNG integration**: Privacy-focused search aggregator
- **No API key needed**: Self-hosted SearXNG instance

### Time & Reminders
- **Timezone-aware**: Current time/date in any timezone
- **Flexible scheduling**: One-time or recurring reminders
- **Multi-thread**: Trigger reminders across multiple conversations

### OCR (optional, local)
- **Image/PDF text extraction**: PaddleOCR or Tesseract
- **Structured extraction**: OCR + LLM for JSON output
- **Use case**: Extract data from screenshots, scans, receipts

## Architecture Overview

Cassey uses a **ReAct agent pattern** with LangGraph:

1. **User message** → Channel (Telegram/HTTP)
2. **Channel** → Agent with state (messages, iterations, summary)
3. **Agent** → ReAct loop (Think → Act → Observe)
4. **Tools** → Storage (files, DB, VS), external APIs
5. **Response** → Channel → User

### Storage Hierarchy

```
data/
├── users/              # Thread-scoped (private)
│   └── {thread_id}/
│       ├── files/      # Private files
│       ├── db/         # Working database
│       ├── vs/         # Thread VS (rarely used)
│       └── mem/        # Embedded memories
├── groups/             # Workspace-scoped (shared)
│   └── {workspace_id}/
│       ├── files/      # Shared files
│       ├── db/         # Team database
│       └── vs/         # Knowledge base
└── shared/             # Organization-wide
    └── shared.db       # Admin-writable database
```

### PostgreSQL Schema

| Table | Purpose |
|-------|---------|
| `checkpoints` | LangGraph state snapshots (conversation history) |
| `conversations` | Conversation metadata per thread |
| `messages` | Message audit log |
| `file_paths` | File ownership per thread |
| `db_paths` | Database ownership per thread |
| `user_registry` | Operation audit (merge/split/remove) |
| `reminders` | Scheduled reminder notifications |

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

## Project Structure

```
cassey/
├── src/cassey/
│   ├── channels/       # Telegram, HTTP
│   ├── storage/        # User registry, file sandbox, DB, VS, reminders
│   ├── tools/          # LangChain tools (file, DB, time, Python, search, OCR)
│   ├── agent/          # Agent runtimes (custom graph + LangChain)
│   ├── scheduler.py    # APScheduler integration
│   └── config/         # Settings
├── migrations/         # SQL migrations
├── tests/              # Unit tests
├── discussions/        # Design docs and plans
├── scripts/            # Utility scripts
├── pyproject.toml
├── TODO.md
└── README.md
```

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions welcome! Please read `CLAUDE.md` for development workflow and testing guidelines.

**Remember**: Always test locally with `uv run cassey` before building Docker. See `CLAUDE.md` for details.
