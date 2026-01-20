# Executive Assistant

Your intelligent assistant that manages tasks, tracks work, stores knowledge, and never forgets a reminder.

## What Executive Assistant Can Do For You

Executive Assistant is a multi-channel AI agent that helps you stay organized and productive. Whether you're tracking timesheets, managing a knowledge base, or automating data analysis, Executive Assistant intelligently selects the right tools for the job.

### Track Your Work
- **Timesheet logging**: Simply tell Executive Assistant what you worked on, and it stores structured data in your private database
- **Time-aware**: Knows the current time in any timezone, perfect for distributed teams
- **Data analysis**: Query your logged work with SQL, export to CSV/JSON, or visualize trends

### Never Forget a Reminder
- **Scheduled notifications**: "Remind me to review PRs at 3pm every weekday"
- **Recurring patterns**: Daily, weekly, or custom schedules with flexible recurrence rules
- **Multi-channel delivery**: Get reminders on Telegram or HTTP webhook

### Build a Knowledge Base
- **Semantic search**: Store documents and find them by meaning, not just keywords
- **Smart retrieval**: Ask "What did we decide about the API pricing?" and get the right answer
- **Group collaboration**: Share knowledge across team conversations while keeping private data isolated

### Automate Data Work
- **Python execution**: Run calculations, data processing, and file operations in a secure sandbox
- **Web search**: Find current information from the web
- **File operations**: Read, write, search, and organize files with natural language commands

### Intelligent Tool Selection
Executive Assistant uses a skills system to choose the right approach:
- **Database tools** for structured data and temporary analysis (timesheets, logs, datasets)
- **Vector Store** for long-term knowledge retrieval (meeting notes, decisions, documentation)
- **File tools** for browsing and exact-text search (codebases, document archives)

You don't need to remember which tool does what—Executive Assistant figures it out from context.

## How Executive Assistant Thinks

Executive Assistant is a **ReAct agent** built on LangGraph. Unlike simple chatbots, it:

1. **Reasons** about your request using an LLM
2. **Acts** by calling tools (file operations, database queries, web search, etc.)
3. **Observes** the results and decides what to do next
4. **Responds** with a clear confirmation of what was done

This cycle continues until your task is complete—with safeguards to prevent infinite loops.

### Real-Time Progress Updates
Executive Assistant keeps you informed while working:
- **Normal mode**: Clean status updates edited in place
- **Debug mode**: Detailed timing information (toggle with `/debug`)
- **Per-message limits**: Prevents runaway execution (20 LLM calls, 30 tool calls per message)

## Multi-Channel Access

Executive Assistant works where you work:

### Telegram
- Chat with Executive Assistant in any Telegram conversation
- Commands: `/start`, `/help`, `/reminders`, `/groups`, `/debug`, `/id`
- Perfect for mobile quick-tasks and reminders on-the-go

### HTTP API
- Integrate Executive Assistant into your applications
- REST endpoints for messaging and conversation history
- SSE streaming for real-time responses
- Ideal for workflows, webhooks, and custom integrations

## Storage That Respects Your Privacy

Executive Assistant takes data isolation seriously with a unified `scope` parameter across all storage tools:

### Context-Scoped Storage (Default)
All storage tools support `scope="context"` (default):
- **In a group**: Uses `data/groups/{group_id}/` for team collaboration
- **Individual threads**: Uses `data/users/{thread_id}/` for private data

```python
# Context-scoped (automatic - uses group or thread)
create_db_table("users", data=[...], scope="context")
write_file("notes.txt", "My notes", scope="context")
create_vs_collection("knowledge", content="Team decisions", scope="context")
```

### Organization-Wide Shared Storage
All storage tools support `scope="shared"` for organization-wide data:
- **Location**: `data/shared/`
- **Accessible by**: All users (read), admins (write)
- **Use cases**: Company-wide knowledge, shared templates, org data

```python
# Organization-wide shared
create_db_table("org_users", data=[...], scope="shared")
write_file("policy.txt", "Company policy", scope="shared")
create_vs_collection("org_knowledge", content="Company processes", scope="shared")
```

### Storage Hierarchy
```
data/
├── shared/              # scope="shared" (organization-wide)
│   ├── files/           # Shared file storage
│   ├── db/              # Shared database
│   └── vs/              # Shared vector store
├── groups/              # scope="context" when group_id is set
│   └── {group_id}/      # Team groups
│       ├── files/
│       ├── db/
│       └── vs/
└── users/               # scope="context" for individual threads
    └── {thread_id}/
        ├── files/
        ├── db/
        └── vs/
```

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
docker compose up -d postgres

# Run migrations (auto-run on first start)
psql $POSTGRES_URL < migrations/001_initial_schema.sql

# Run Executive Assistant (default: Telegram)
uv run executive_assistant

# Run HTTP only
EXECUTIVE_ASSISTANT_CHANNELS=http uv run executive_assistant

# Run both Telegram and HTTP
EXECUTIVE_ASSISTANT_CHANNELS=telegram,http uv run executive_assistant
```

**For local testing**, always use `uv run executive_assistant` instead of Docker. Only build Docker when everything works (see `CLAUDE.md` for testing workflow).

## What Makes Executive Assistant Different

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
Executive Assistant: Created timesheet table and logged entry.

You: How many hours did I work this week?
Executive Assistant: [queries database] You worked 32 hours total:
     - API development: 16h
     - Bug fixes: 12h
     - Meetings: 4h
```

### Knowledge Management
```
You: Save this: API rate limit is 1000 req/min for pro accounts
Executive Assistant: Saved to knowledge base.

You: What's the rate limit for pro accounts?
Executive Assistant: [searches vector store] 1000 requests per minute.
```

### Data Analysis
```
You: Analyze this CSV and find the average
Executive Assistant: [imports CSV, runs Python] The average is 42.7.
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
EXECUTIVE_ASSISTANT_CHANNELS=telegram,http   # Available channels

# Telegram (if using telegram channel)
TELEGRAM_BOT_TOKEN=...

# PostgreSQL (required for state persistence)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=executive_assistant
POSTGRES_PASSWORD=your_password
POSTGRES_DB=executive_assistant_db
```

See `.env.example` for all available options.

## Telegram Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Start conversation / show welcome message |
| `/help` | Show available commands and usage |
| `/reminders` | List active reminders |
| `/groups` | Manage shared groups |
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

When `EXECUTIVE_ASSISTANT_CHANNELS=http`, a FastAPI server starts on port 8000:

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

### Vector Store (per-group/thread)
- **Semantic search**: Find documents by meaning, not just keywords
- **Hybrid search**: Combines full-text + vector similarity
- **Persistent**: Survives thread resets (group/thread-scoped)
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

Executive Assistant uses a **ReAct agent pattern** with LangGraph:

1. **User message** → Channel (Telegram/HTTP)
2. **Channel** → Agent with state (messages, iterations, summary)
3. **Agent** → ReAct loop (Think → Act → Observe)
4. **Tools** → Storage (files, DB, VS), external APIs
5. **Response** → Channel → User

### Storage Hierarchy

```
data/
├── shared/             # Organization-wide (scope="shared")
│   ├── files/          # Shared files
│   ├── db/             # Shared database
│   └── vs/             # Knowledge base
├── groups/             # Group-scoped (scope="context" with group_id)
│   └── {group_id}/
│       ├── files/      # Shared files
│       ├── db/         # Team database
│       └── vs/         # Knowledge base
└── users/              # Thread-scoped (scope="context" without group_id)
    └── {thread_id}/
        ├── files/      # Private files
        ├── db/         # Working database
        ├── vs/         # Thread VS (rarely used)
        └── mem/        # Embedded memories
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
executive_assistant/
├── src/executive_assistant/
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

**Remember**: Always test locally with `uv run executive_assistant` before building Docker. See `CLAUDE.md` for details.
