# Executive Assistant

Your intelligent assistant that manages tasks, tracks work, stores knowledge, and never forgets a reminder.

## What Executive Assistant Can Do For You

Executive Assistant is a multi-channel AI agent that helps you stay organized and productive. Whether you're tracking timesheets, managing a knowledge base, or automating data analysis, Executive Assistant intelligently selects the right tools for the job.

### Track Your Work
- **Timesheet logging**: Simply tell Executive Assistant what you worked on, and it stores structured data in your private transactional database
- **Time-aware**: Knows the current time in any timezone, perfect for distributed teams
- **Data analysis**: Query your logged work with SQL, export to CSV/JSON, or visualize trends

### Never Forget a Reminder
- **Scheduled notifications**: "Remind me to review PRs at 3pm every weekday"
- **Recurring patterns**: Daily, weekly, or custom schedules with flexible recurrence rules
- **Multi-channel delivery**: Get reminders on Telegram or HTTP webhook

### Build a Knowledge Base
- **Semantic search**: Store documents and find them by meaning, not just keywords
- **Smart retrieval**: Ask "What did we decide about the API pricing?" and get the right answer
- **Shared knowledge**: Store documents and retrieve them semantically across threads (with explicit shared scope)

### Automate Data Work
- **Python execution**: Run calculations, data processing, and file operations in a secure sandbox
- **Web search**: Find current information from the web
- **File operations**: Read, write, search, and organize files with natural language commands

### Intelligent Tool Selection
Executive Assistant uses a skills system to choose the right approach:
- **Analytics Database (ADB)** for fast analytics on large datasets (100K+ rows, joins, aggregations)
- **Transactional Database (TDB)** for structured data and quick lookups (timesheets, logs, configs)
- **Vector Database (VDB)** for semantic search and knowledge retrieval (documents, decisions, conversations)
- **File tools** for raw file operations (codebases, archives, document management)
- **Python** for custom logic, data transformations, and calculations
- **MCP Tools** for extensible external integrations via Model Context Protocol
- **Skills** for contextual knowledge on how to use tools effectively

You don't need to remember which tool does what—Executive Assistant figures it out from context.

## Unified Context System: How Executive Assistant Remembers Everything

Executive Assistant uses a **4-pillar unified context system** to build persistent understanding across conversations. Each pillar serves a distinct purpose, working together to create comprehensive memory.

### The 4 Pillars

**1. Memory (Semantic) - "Who you are"**
- **What it stores**: Decisions, context, knowledge, preferences
- **How it works**: Meaning-based semantic search with automatic retrieval
- **Retrieval**: Surfaces based on conversation context automatically
- **Use cases**: Meeting notes, project decisions, API keys, user preferences
- **Scope**: Thread-isolated (private) or organization-wide (shared)

**2. Journal (Episodic) - "What you did"**
- **What it stores**: Time-series activity log with automatic hierarchical rollups
- **How it works**: Tracks every action with timestamps, rolls up hourly → weekly → monthly → yearly
- **Retention**: Configurable (default: 7 years for yearly rollups)
- **Search**: FTS5 keyword search combined with time-range filtering
- **Use cases**: Activity history, work patterns, progress tracking, "what did I work on last Tuesday?"

**3. Instincts (Procedural) - "How you behave"**
- **What it stores**: Learned behavioral patterns and personality profiles
- **How it works**: Detects patterns from corrections, repetitions, and preferences
- **Evolution**: Patterns can cluster into reusable skills
- **Application**: Probabilistic based on confidence scoring
- **Use cases**: Communication style (concise vs detailed), format preferences, response patterns

**4. Goals (Intentions) - "Why/Where"**
- **What it stores**: Objectives with progress tracking and version history
- **How it works**: Change detection (5 mechanisms), progress history, audit trail
- **Monitoring**: Detects stagnation, stalled progress, approaching deadlines
- **Integration**: Informed by journal activities and memory facts
- **Use cases**: Project goals, personal objectives, OKRs, deadline tracking

### How the Pillars Work Together

```
User: "I want to launch the sales dashboard by end of month"
         ↓
    [Memory] Stores: "User's priority: sales dashboard, deadline: EOM"
         ↓
    [Goals] Creates: Goal "Launch sales dashboard" with target_date
         ↓
    [Journal] Tracks: "Created dashboard schema", "Built charts", "Deployed to staging"
         ↓
    [Goals] Updates: Progress 0% → 30% → 75% → 100%
         ↓
    [Instincts] Learns: "User prefers visual progress updates"
```

**Unified Context Benefits:**
- **No repetition**: Never repeat your preferences or context
- **Progress continuity**: Goals track across sessions via journal
- **Adaptive behavior**: Instincts personalize interactions automatically
- **Historical intelligence**: Find past work by semantic meaning OR time OR keyword

### Adaptive Behavior with Instincts

Executive Assistant learns your communication style and preferences automatically:

- **Pattern Detection**: Automatically learns from corrections, repetitions, and preferences
- **Profile Presets**: Quick personality configuration (Concise Professional, Detailed Explainer, Friendly Assistant, Technical Expert)
- **Confidence Scoring**: Behaviors are applied probabilistically based on confidence
- **Evolution to Skills**: Learned patterns can cluster into reusable skills
- **Part of 4-Pillar System**: Instincts store "how you behave" within the unified context system

**Example:**
```
You: Be concise
[Assistant learns: user prefers brief responses]

You: Use bullet points
[Assistant learns: user prefers list format]

You: Actually, use JSON for data
[Assistant adjusts: reinforces format preference]

→ Pattern evolves into: "Use concise, bulleted, or JSON format based on content type"
```

**Profile Presets:**
```
You: list_profiles
Assistant: Available profiles:
  • Concise Professional - Brief, direct, business-focused
  • Detailed Explainer - Comprehensive, educational, thorough
  • Friendly Assistant - Warm, conversational, approachable
  • Technical Expert - Precise, code-focused, architectural

You: apply_profile "Concise Professional"
[Assistant applies personality preset and adapts responses]
```

> **Inspired by** [Everything with Claude Code](https://github.com/affaan-m/everything-claude-code)'s continuous learning system, instincts provide adaptive behavior that evolves with your usage patterns.

### Persistent Memory System

Executive Assistant never forgets important information across conversations:

**Semantic Memory (VDB)**
- **Meaning-based storage**: Remember decisions, context, and knowledge by semantic meaning
- **Automatic retrieval**: Relevant memories surface based on conversation context
- **Thread isolation**: Private memory per conversation (or shared via `scope="shared"`)
- **Use cases**: Meeting notes, decisions, project context, preferences

**Structured Memory (TDB)**
- **Tabular storage**: Queryable facts, configurations, reference data
- **SQL access**: Query memories with SQLite-compatible SQL
- **Thread-scoped or shared**: Private tables or organization-wide knowledge
- **Use cases**: API keys, contact lists, configurations, reference data

**Key-Value Memory**
- **Fast lookups**: Store and retrieve by key for quick access
- **Time-aware**: Get memory as it was at a specific point in time
- **Version tracking**: See how memories changed over time
- **Use cases**: User preferences, settings, quick facts

**Memory Commands:**
```bash
# Store a memory
/remember add project_alpha: "My secret project"

# Search memories
/mem search "project"

# Update a memory
/mem update project_alpha "Project Alpha: AI assistant platform"

# Forget a memory
/mem forget project_alpha

# List all memories
/mem list
```

## Onboarding

Executive Assistant automatically detects new users and guides them through profile creation:

**Automatic Detection:**
- Triggers on first interaction (empty user data folder)
- Detects vague requests ("hi", "help", "what can you do")
- Checks for existing data (TDB, VDB, files) before showing onboarding

**Guided Flow:**
```
[New user detected]
Assistant: Welcome! I'd like to learn about you to serve you better.

1. What's your name?
2. What's your role? (Developer, Manager, Analyst, etc.)
3. What are your main goals? (Track work, analyze data, automate tasks)
4. Any preferences? (concise responses, detailed explanations)

[Profile created with 4 structured memories: name, role, responsibilities, communication_style]
[Onboarding marked complete - won't trigger again]
```

**Vague Request Handling:**
```
You: "hi"
Assistant: [Detects vague + new user]
        Hi! 👋 I'm your Executive Assistant.

        I can help you:
        • Track work and timesheets
        • Analyze data with SQL/Python
        • Store and retrieve knowledge
        • Set reminders and manage goals

        What would you like help with?
```

**Structured Profile Creation:**
- Uses `create_user_profile()` tool (not fragmented memories)
- Creates 4 normalized memories with proper keys
- Prevents onboarding re-trigger with marker file
- Stores completion marker in memory

**Onboarding Tools:**
```bash
create_user_profile(
    name="Ken",
    role="CIO at Gong Cha Australia",
    responsibilities="IT, escalation, franchise relations, legal, HR",
    communication_preference="professional"
)
mark_onboarding_complete()
```

## How Executive Assistant Thinks

Executive Assistant is a **ReAct agent** built on LangGraph. Unlike simple chatbots, it:

1. **Reasons** about your request using an LLM
2. **Acts** by calling tools (file operations, transactional database queries, web search, etc.)
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
- Commands: `/start`, `/reset`, `/remember`, `/debug`, `/mem`, `/reminder`, `/vdb`, `/tdb`, `/file`, `/meta`, `/user`
- Perfect for mobile quick-tasks and reminders on-the-go

### HTTP API
- Integrate Executive Assistant into your applications
- REST endpoints for messaging and conversation history
- SSE streaming for real-time responses
- **Open access** (authentication handled by your frontend)
- Ideal for workflows, webhooks, and custom integrations

### Google Workspace Integration (Optional)

Connect your Gmail, Calendar, and Contacts to enable powerful productivity workflows:

**Features:**
- **Gmail**: Read, send, and manage emails with natural language
- **Calendar**: Schedule meetings, check availability, manage events
- **Contacts**: Search and manage contacts
- **Thread-scoped authentication**: Each user connects their own Google account
- **Encrypted token storage**: OAuth tokens encrypted at rest with Fernet
- **Automatic token refresh**: Seamless authentication with 1-hour token expiry

**Setup:**
```bash
# Run the interactive setup script
./setup_google_oauth.sh

# Or manually configure:
# 1. Create Google Cloud project: https://console.cloud.google.com/projectcreate
# 2. Enable APIs: Gmail, Calendar, People
# 3. Configure OAuth consent screen with scopes:
#    - https://www.googleapis.com/auth/gmail.readonly
#    - https://www.googleapis.com/auth/gmail.send
#    - https://www.googleapis.com/auth/gmail.modify
#    - https://www.googleapis.com/auth/calendar
#    - https://www.googleapis.com/auth/contacts
# 4. Create OAuth client ID with redirect URI
# 5. Add credentials to docker/.env:
#    GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
#    GOOGLE_CLIENT_SECRET=your-client-secret
#    GOOGLE_REDIRECT_URI=http://localhost:8000/auth/callback/google
#    EMAIL_ENCRYPTION_KEY=your-fernet-key
```

**Connect in Telegram:**
```
/connect_gmail
```

**Connect via HTTP:**
```
GET /auth/google/start?user_id=your_user_id
```

See `features/GOOGLE_OAUTH_LOCAL_SETUP.md` for detailed setup instructions.

## Storage That Respects Your Privacy

Executive Assistant takes data isolation seriously with a unified `scope` parameter across all storage tools:

### Context-Scoped Storage (Default)
All storage tools support `scope="context"` (default):
- **Thread-only context**: Uses `data/users/{thread_id}/` for private data

```python
# Context-scoped (automatic - uses thread)
create_tdb_table("users", data=[...], scope="context")
write_file("notes.txt", "My notes", scope="context")
create_vdb_collection("knowledge", content="Decisions", scope="context")
```

### Organization-Wide Shared Storage
All storage tools support `scope="shared"` for organization-wide data:
- **Location**: `data/shared/`
- **Accessible by**: All users (read), admins (write)
- **Use cases**: Company-wide knowledge, shared templates, org data

```python
# Organization-wide shared
create_tdb_table("org_users", data=[...], scope="shared")
write_file("policy.txt", "Company policy", scope="shared")
create_vdb_collection("org_knowledge", content="Company processes", scope="shared")
```

### Storage Hierarchy
```
data/
├── shared/              # scope="shared" (organization-wide)
│   ├── files/           # Shared file storage
│   ├── tdb/             # Shared transactional database
│   └── vdb/             # Shared vector database
└── users/               # scope="context" for individual threads
    └── {thread_id}/
        ├── files/
        ├── tdb/
        ├── vdb/
        ├── mem/         # Embedded memories
        └── instincts/   # Learned behavioral patterns
            ├── instincts.jsonl         # Append-only event log
            └── instincts.snapshot.json  # Compacted state
```

### Thread-Scoped Ownership
- Data is stored under `data/users/{thread_id}/`
- Ownership tracking for files, TDB, VDB, and reminders
- Audit log for operations

## Quick Start

```bash
# Setup environment
cp docker/.env.example docker/.env
# Edit docker/.env with your API keys

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
- **Intelligent storage**: Knows when to use TDB (structured) vs VDB (semantic) vs files (raw)
- **Skills system**: Progressive disclosure of advanced patterns (load with `load_skill`)
- **Instincts system**: Automatically learns behavioral patterns from interactions
- **Privacy-first**: Thread isolation by design, merge only when you request it
- **Multi-channel**: Same agent works on Telegram, HTTP, and more (planned: Email, Slack)
- **All tools available**: All 87 tools available in every conversation
- **Robust error handling**: Comprehensive error logging with full tracebacks at DEBUG level
- **Frontend auth**: HTTP channel delegates authentication to your application layer

### Production-Ready Features
- **Admin customization**: BYO prompt/skills/MCP via `data/admins/` + user allowlist (Telegram only)
- **Middleware stack**: Summarization, retry logic, call limits, todo tracking, context editing, thread context propagation
- **High-precision logging**: Millisecond timestamps for performance analysis
- **Debug mode**: Toggle verbose status updates to understand agent behavior
- **Status updates**: Real-time progress feedback during long-running tasks
- **Thread context middleware**: Ensures thread isolation across async boundaries
- **Enhanced error logging**: All tool errors logged with full traceback at DEBUG level

## Example Workflows

### 🚀 Build a Mini Analytics Dashboard in Seconds
```
You: I have sales.csv with 500K rows. Build me a dashboard showing:
     - Top 10 products by revenue
     - Monthly trend line
     - Category breakdown pie chart
     - Save everything to reports/

Executive Assistant: [Loads ADB for analytics]
     Importing 500K rows to Analytics Database...
     Running queries...
     Generating visualizations...

     ✅ Created 4 reports:
        - top_products.csv (10 rows)
        - monthly_trend.csv (24 rows)
        - category_breakdown.csv (8 rows)
        - sales_dashboard.png (interactive chart)

     💡 Top product: "Widget Pro" - $127,450 revenue
```

### 📊 Ad-Hoc Analytics on Hundreds of MB Data
```
You: Query all logs from 2024, group by endpoint, calculate:
     - Total requests
     - Avg response time
     - P95 response time
     - Error rate
     Export to performance_report.csv

Executive Assistant: [Uses Analytics Database (DuckDB)]
     Scanning logs/2024/*.log (847MB across 12 files)...

     ✅ Analytics complete:
        - 12.4M requests analyzed in 3.2 seconds
        - 2,847 unique endpoints
        - Avg response time: 45ms
        - P95: 180ms
        - Error rate: 0.12%

     💾 Saved to: performance_report.csv
```

### 🧠 Intelligent Knowledge Retrieval
```
You: What did we decide about API rate limits for enterprise customers?
     Also, what was the reasoning behind the GraphQL caching strategy?

Executive Assistant: [Searches Vector Database semantically]
     Found 3 relevant documents:

     1. API Pricing Decision (Jan 15):
        "Enterprise tier: 10,000 req/min, burstable to 50,000"
        Reasoning: "Enterprise customers need burst capacity for...

     2. GraphQL Architecture Discussion (Feb 3):
        "Caching strategy: 5-minute TTL on queries, 1-hour on...
        Reasoning: "Balance freshness vs performance - analytics...

     3. Rate Limit Implementation (Mar 8):
        "Token bucket algorithm with per-IP limits"
        Reasoning: "Prevent abuse while allowing legitimate burst..."
```

### 🔌 Quick Python Data Pipeline
```
You: Download https://api.github.com/repos/langchain-ai/langchain/releases,
     parse the JSON, extract version numbers and publish dates,
     plot a timeline of releases, save to github_releases.png

Executive Assistant: [Uses Python + File tools]
     Fetching releases from GitHub API...
     Parsing 127 releases...
     Generating timeline visualization...

     ✅ Done! Created github_releases.png
     📊 Timeline shows 2.3 releases/week average
     📈 Trend: Increasing release cadence over past 6 months
```

### 🏗️ Build a Multi-Step Workflow App
```
You: Create a daily report that:
     1. Fetches yesterday's sales from PostgreSQL
     2. Enriches with customer data from CRM API
     3. Calculates churn risk using Python
     4. Saves high-risk customers to VDB for follow-up
     5. Emails the summary

Executive Assistant: [Orchestrates TDB + Python + VDB + Web tools]
     Building workflow...

     Step 1: [TDB Query] Retrieved 1,247 transactions
     Step 2: [Web Fetch] Enriched 847 customer profiles
     Step 3: [Python Analysis] Calculated churn scores
              → 73 high-risk (score > 0.7)
              → 231 medium-risk (score > 0.4)
     Step 4: [VDB Store] Indexed high-risk customers for semantic search
     Step 5: [Email Draft] Report generated at reports/daily_churn_2024-01-15.md

     💡 Saved as scheduled flow: "daily_churn_report"
     🕓 Runs daily at 9:00 AM
```

### 🎯 Cross-Reference Multiple Data Sources
```
You: I have:
     - customer_tickets.csv (50K support tickets)
     - product_catalog.json (2K products)
     - usage_logs.parquet (2GB usage data)

     Find me: Products with high churn (>30%) but low usage (<10min/day)
     from customers who filed >5 tickets in the last 30 days

Executive Assistant: [Uses ADB for joins across large datasets]
     Importing datasets to Analytics Database...
     Running complex join query...

     🎯 Found 12 products matching criteria:

        Product           | Churn | Avg Usage | Ticket Count
        ------------------+-------+-----------+-------------
        Legacy Widget     | 47%   | 4min/day  | 8.2 avg
        Enterprise Plan   | 38%   | 7min/day  | 6.1 avg
        Mobile App Basic  | 34%   | 8min/day  | 5.7 avg

     💡 Pattern: All legacy products with poor UX
        → Recommendation: Prioritize UX refresh or deprecation

     💾 Full report: chrun_analysis_report.csv
        Visualization: churn_vs_usage_scatter.png
```

### 📝 Automate Document Analysis
```
You: Read all PDFs in contracts/, extract:
     - Contract value
     - Expiration date
     - Auto-renewal clause
     Store in TDB for querying

Executive Assistant: [Uses OCR + File tools + TDB]
     Processing 47 contracts...

     ✅ Extracted and stored:
        - Total value: $4.2M
        - 15 expiring in next 90 days
        - 32 have auto-renewal
        - 8 require manual renewal (no auto clause)

     💾 Created table: contracts_summary
        Query: SELECT * FROM contracts_summary WHERE days_to_expire < 90
```

### 🔄 Data Migration & Transformation
```
You: Migrate data from MongoDB export (JSON lines) to PostgreSQL:
     - Flatten nested structures
     - Convert timestamps to UTC
     - Deduplicate by email
     - Validate phone numbers
     Report any records that fail validation

Executive Assistant: [Uses Python + TDB tools]
     Reading export.jsonl (1.2GB, 2.8M records)...

     Migration progress:
     ✅ Flattened nested documents: 2.8M → 47 fields
     ✅ Converted timestamps: 2.8M → UTC
     ✅ Deduplicated: 2.8M → 2.34M unique emails
     ⚠️ Validation failures: 12,847 records

     Issues found:
        - Invalid phone: 8,234 (malformed format)
        - Missing email: 3,112 (required field)
        - Future DOB: 1,501 (data entry error)

     💾 Valid records in PostgreSQL: users_import table
        Invalid records saved to: validation_errors.csv
```

## Configuration

Essential environment variables:

```bash
# LLM Provider (choose one)
OPENAI_API_KEY=sk-...           # OpenAI (GPT-4, GPT-4o)
ANTHROPIC_API_KEY=sk-...        # Anthropic (Claude)
ZHIPUAI_API_KEY=...             # Zhipu (GLM-4)

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

See `docker/.env.example` for all available options.

## Slash Commands & Tools

### Telegram Bot Commands

| Command | Description | Usage |
|---------|-------------|-------|
| `/start` | Start conversation or show welcome message | `/start` |
| `/reset` | Reset the current thread context (clears conversation history) | `/reset` |
| `/remember` | Save a memory from a single message | `/remember The API key is sk-xxx` |
| `/debug` | Toggle verbose status mode (see LLM/tool timing) | `/debug on`, `/debug off`, `/debug toggle` |
| `/mem` | Memory management: list, add, update, forget memories | `/mem list`, `/mem add budget: $1000` |
| `/reminder` | Reminder management: list, set, edit, cancel | `/reminder list`, `/reminder set 9am "daily standup"` |
| `/vdb` | Vector database commands: collections, search | `/vdb list`, `/vdb create docs` |
| `/tdb` | Transactional database commands: tables, queries | `/tdb list`, `/tdb create users` |
| `/file` | File operations: list, read, write, search | `/file list`, `/file read notes.txt` |
| `/meta` | Show storage summary (files/VDB/TDB/reminders count) | `/meta` |
| `/user` | Admin allowlist management (Telegram only) | `/user add @username`, `/user list` |
| `/journal` | Journal commands: add entry, search, list by time range | `/journal add "Worked on dashboard"`, `/journal search "sales"`, `/journal list --days 7` |
| `/goals` | Goals commands: create, update progress, list, detect issues | `/goals create "Launch dashboard"`, `/goals progress "Launch dashboard" 50`, `/goals list --status planned` |
| `/onboarding` | Onboarding: start, complete, check status | `/onboarding start`, `/onboarding complete`, `/onboarding status` |

### Memory Commands (`/mem`)

Manage conversational memories that persist across sessions:

```bash
/mem list                           # List all memories
/mem add project_alpha: "My secret project"  # Add a memory
/mem update project_alpha            # Update an existing memory
/mem forget project_alpha            # Delete a memory
/mem search "project"                # Search memories
```

**Use cases**: Remember preferences, project context, API keys, recurring tasks

### Reminder Commands (`/reminder`)

Schedule one-time or recurring reminders:

```bash
/reminder list                       # List all reminders
/reminder set 3pm "review PRs"       # Set one-time reminder
/reminder set 9am "daily standup" --daily  # Recurring daily
/reminder set monday 9am "weekly planning" --weekly  # Recurring weekly
/reminder edit 1 "new text"          # Edit reminder by ID
/reminder cancel 1                   # Cancel reminder by ID
```

**Recurring patterns**: `--daily`, `--weekly`, `--weekdays`, `--cron "0 9 * * 1-5"`

### Vector Database Commands (`/vdb`)

Semantic knowledge base for document retrieval:

```bash
/vdb list                           # List all collections
/vdb create docs                    # Create new collection
/vdb add docs "Meeting notes..."    # Add document to collection
/vdb search docs "API decisions"    # Semantic search
/vdb describe docs                  # Show collection stats
/vdb drop docs                      # Delete collection
```

**Use cases**: Meeting notes, documentation, decisions, conversation history

### Transactional Database Commands (`/tdb`)

Structured data storage with SQL queries:

```bash
/tdb list                           # List all tables
/tdb create users                   # Create new table
/tdb insert users '{"name": "Alice"}'  # Insert row(s)
/tdb query users "SELECT * FROM users WHERE name = 'Alice'"  # SQL query
/tdb describe users                 # Show table schema
/tdb drop users                     # Delete table
/tdb export users CSV               # Export table to CSV/JSON/Parquet
/tdb import users data.csv          # Import from CSV/JSON/Parquet
```

**Use cases**: Timesheets, task tracking, logs, structured data, lookups

### File Commands (`/file`)

File operations within thread-scoped directories:

```bash
/file list                          # List files (supports *.txt, **/*.json patterns)
/file read notes.txt                # Read file content
/file write output.txt "data"       # Write file
/file search "TODO" --glob *.py     # Search in files
/file move old.txt new.txt          # Move/rename file
/file delete old.txt                # Delete file
/file create_folder subdir          # Create directory
```

**Use cases**: Code management, document processing, data exports, templates

### Meta Commands (`/meta`)

Show storage summary and thread context:

```bash
/meta                              # Show all storage counts
/meta files                        # Show file count and total size
/meta tdb                          # Show table count and row counts
/meta vdb                          # Show collection count and document counts
/meta reminders                    # Show active and scheduled reminders
```

### User Management (`/user`) - Admin Only

Manage Telegram allowlist (only available to admins):

```bash
/user list                         # List all allowed users
/user add @username                # Add user to allowlist
/user remove @username             # Remove user from allowlist
/user check @username              # Check if user is allowed
```

### Instinct Tools (In-Conversation Tools)

Learn behavioral patterns and personality profiles:

```bash
list_profiles                       # Browse available personality profiles
apply_profile "Concise Professional"  # Apply a profile preset
list_instincts                      # Show learned behavioral patterns
get_applicable_instincts            # Show applicable instincts for current context
create_instinct "Be concise"        # Manually create a behavioral pattern
adjust_instinct_confidence "Be concise" 0.9  # Adjust pattern strength
disable_instinct "Be concise"       # Disable a specific pattern
enable_instinct "Be concise"        # Re-enable a disabled pattern
evolve_instincts                    # Cluster patterns into reusable skills
export_instincts                    # Export learned patterns for sharing
import_instincts                    # Import patterns from teammates
```

### MCP Tools (Model Context Protocol) - In-Conversation Tools

Add and manage external MCP server integrations:

```bash
mcp_list_servers                   # List all configured MCP servers (admin + user)
mcp_add_server fetch "uvx" ["mcp-server-fetch"]  # Add local (stdio) MCP server
mcp_add_remote_server "github" "https://..."  # Add remote HTTP/SSE server
mcp_remove_server fetch            # Remove an MCP server by name
mcp_show_server clickhouse         # Show detailed server info (tools, config)
mcp_reload                         # Reload MCP tools from config (hot-reload)
mcp_export_config                  # Export config as JSON (for backup/sharing)
mcp_import_config config.json      # Import config from JSON
mcp_list_backups                   # List automatic configuration backups
mcp_show_backup 3                  # Show specific backup details
```

**MCP Skill Management** (approve/reject skills from MCP servers):
```bash
mcp_list_pending_skills            # List skills awaiting approval
mcp_show_skill web_scraping        # Show skill content and metadata
mcp_approve_skill web_scraping     # Approve and load skill
mcp_reject_skill web_scraping      # Reject skill proposal
mcp_edit_skill web_scraping        # Edit skill content before approving
```

### Skills System Tools

Load and manage reusable workflow skills:

```bash
load_skill gong_cha_analyst        # Load a skill by name
list_skills                        # List all available skills
create_user_skill                  # Create a personal skill from conversation
show_skill gong_cha_analyst        # Show skill content and metadata
```

### Debug Mode

Toggle detailed progress tracking to understand agent behavior:

```bash
/debug                              # Show current debug status
/debug on                           # Enable verbose mode
/debug off                          # Disable (clean mode)
/debug toggle                       # Toggle debug mode
```

**Normal mode:** Status messages are edited in place (clean UI)
**Verbose mode:** Each update sent as separate message with LLM timing

Example verbose output:
```
🤔 Thinking...
🛠️ 1: run_select_query
🛠️ 2: list_tables
✅ Done in 12.5s | LLM: 2 calls (11.8s)
```

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
# Send message (streaming)
curl -X POST http://localhost:8000/message \
  -H "Content-Type: application/json" \
  -d '{"content": "hello", "user_id": "user123", "conversation_id": "myconv", "stream": true}'

# Send message (non-streaming)
curl -X POST http://localhost:8000/message \
  -H "Content-Type: application/json" \
  -d '{"content": "hello", "user_id": "user123", "conversation_id": "myconv", "stream": false}'

# Get conversation history
curl http://localhost:8000/conversations/myconv

# Health check
curl http://localhost:8000/health
```

**Endpoints:**
- `POST /message` - Send message (supports SSE streaming with `stream: true`)
- `GET /conversations/{id}` - Get conversation history
- `GET /health` - Health check

**Authentication:**
- HTTP channel has **open access** - your frontend handles authentication
- Provide any `user_id` and `conversation_id` to identify the session
- Data isolation is enforced per-thread via unique conversation IDs
- Telegram channel uses allowlist (managed via `/user` command)

## Tool Capabilities

### Analytics Database (ADB) - DuckDB Powerhouse
**For serious analytics on medium-to-large datasets (100K to 100M+ rows)**

- **Blazing fast**: Columnar storage, vectorized execution, parallel queries
- **Direct file queries**: Query CSV/Parquet/JSON without importing
- **Complex analytics**: Window functions, CTEs, nested aggregations
- **Multi-way joins**: Combine datasets effortlessly
- **Scalable**: Handles hundreds of MB to GB of data efficiently
- **Use cases**:
  - Sales analytics and reporting
  - Log analysis and aggregation
  - Time-series data processing
  - Data science and ML prep work
  - Business intelligence queries

| Operation | TDB | ADB |
|-----------|-----|-----|
| CRUD operations | ✅ Excellent | ⚠️ Limited |
| Complex queries | ❌ Slow | ✅ Blazing fast |
| Large joins | ❌ Timeout | ✅ Optimized |
| 100M+ rows | ❌ Struggles | ✅ Handles well |
| Frequent updates | ✅ Good | ⚠️ Append-better |

### Transactional Database (TDB) - SQLite Powerhouse
**For structured data and transactional workloads**

- **Instant startup**: No import needed, works immediately
- **ACID compliant**: Reliable transactions and rollbacks
- **SQLite compatible**: Familiar SQL syntax
- **Thread-scoped**: Each conversation gets isolated database
- **Import/Export**: CSV, JSON, Parquet support
- **Use cases**:
  - Timesheets and task tracking
  - Configuration storage
  - Quick data lookups
  - Temporary working data
  - Small-to-medium datasets (<100K rows)

### Vector Database (VDB) - Semantic Search
**For knowledge retrieval and semantic understanding**

- **Meaning-based search**: Find documents by intent, not keywords
- **Hybrid search**: Combines vector similarity with full-text search
- **Persistent**: Survives thread resets
- **Thread-scoped**: Private knowledge per conversation
- **Use cases**:
  - Meeting notes and decisions
  - Documentation lookup
  - Conversational memory
  - Knowledge base management

### Journal System - Activity Tracking & Time-Series Memory
**For tracking what you did and when you did it**

- **Automatic logging**: Every tool call and action logged with timestamp
- **Hierarchical rollups**: Raw entries → Hourly → Weekly → Monthly → Yearly summaries
- **Keyword search**: FTS5 full-text search through all activities
- **Time-range queries**: Find what you worked on last Tuesday, or last month
- **Configurable retention**: Keep hourly for 30 days, weekly for 1 year, yearly for 7 years (default)
- **Semantic search**: Find activities by meaning, not just keywords
- **Integration**: Feeds goals progress, informs instinct patterns

**Use cases:**
- Activity tracking and timesheet generation
- Progress tracking for goals and projects
- Pattern detection (e.g., "User works on sales every Monday")
- Historical queries ("What did I work on last week?")
- Work analysis and productivity insights

**Journal Commands:**
```bash
# Add journal entry
/add_journal_entry "Created sales dashboard schema"

# Search by keyword
/search_journal "dashboard"

# Search by time range
/list_journal --start "2024-01-01" --end "2024-01-31"

# Get rollup hierarchy
/get_journal_rollup "2024-01"  # Monthly rollup with weekly breakdowns
```

**Data Retention (configurable in docker/config.yaml):**
- Raw entries: 30 days
- Hourly rollups: 30 days
- Weekly rollups: 52 weeks (1 year)
- Monthly rollups: 84 months (7 years)
- Yearly rollups: 7 years

### Goals System - Objective Tracking & Progress Management
**For setting goals, tracking progress, and detecting what needs attention**

- **Goal creation**: Set objectives with target dates, priorities, and importance scores
- **Progress tracking**: Manual updates or automatic from journal activities
- **Change detection (5 mechanisms)**:
  1. Explicit modifications (user edits goal)
  2. Journal stagnation (no activity for 2+ weeks)
  3. Progress stall (no progress updates for 1+ week)
  4. Approaching deadlines (low progress within 5 days of deadline)
  5. Goal completion (100% progress achieved)
- **Version history**: Full audit trail with snapshots and change reasons
- **Restore capability**: Revert to any previous version
- **Categories**: Short-term (< 1 month), Medium-term (1-6 months), Long-term (> 6 months)
- **Priority matrix**: Eisenhower matrix (priority × importance)

**Use cases:**
- Project goals and OKRs
- Personal objectives and habit tracking
- Deadline management with proactive alerts
- Progress visualization and reporting
- Goal dependency management (sub-goals, related projects)

**Goals Commands:**
```bash
# Create goal
/create_goal "Launch sales dashboard" --category "medium_term" --target_date "2024-02-01" --priority 8 --importance 9

# Update progress
/update_goal_progress "Launch sales dashboard" --progress 35 --notes "Completed backend API"

# List goals by status
/list_goals --status "planned"  # Active goals
/list_goals --status "completed"  # Completed goals

# Detect issues
/detect_stagnant_goals --weeks 2  # No activity for 2+ weeks
/detect_stalled_progress --weeks 1  # No progress for 1+ week
/detect_urgent_goals --days 5 --progress_threshold 30  # Deadline soon, low progress

# Version history
/get_goal_versions "Launch sales dashboard"
/restore_goal_version "Launch sales dashboard" --version 1

# Progress history
/get_goal_progress "Launch sales dashboard"
```

### Browser Automation (Playwright)
**For JavaScript-heavy pages that need real browser rendering**

- **Full browser rendering**: Handles React, Vue, Angular, and any JS framework
- **Interactive elements**: Waits for dynamic content to load
- **Screenshot capture**: Export page as image
- **PDF export**: Save page as PDF document
- **Custom selectors**: Wait for specific elements before extracting
- **Fallback for web search**: Automatically used when web scraping fails
- **Use cases**:
  - Single-page applications (SPAs)
  - Infinite scroll pages
  - Authentication-required pages
  - Dynamic dashboards and charts
  - Pages with heavy client-side rendering

**Playwright Commands:**
```bash
# Scrape JS-rendered page
/playwright_scrape "https://example.com/dashboard"

# Wait for specific element
/playwright_scrape "https://example.com" --wait_for_selector ".data-loaded"

# Set timeout and character limit
/playwright_scrape "https://example.com" --timeout_ms 60000 --max_chars 25000
```

**Example:**
```
You: Scrape the sales dashboard at https://internal.example.com/dashboard
Assistant: [Detects JS-heavy page]
     Using Playwright for full browser rendering...

     ✅ Scraped successfully:
        • Total Revenue: $1,234,567
        • Active Users: 8,432
        • Top Product: Widget Pro ($45,678)

     📊 Saved to: dashboard_sales_2024-01-15.json
```

**Installation (if needed):**
```bash
uv add playwright
playwright install  # Download browser binaries
```

### Python Execution - Custom Logic Engine
**For calculations, transformations, and automation**

- **Sandboxed**: 30s timeout, path traversal protection
- **Rich libraries**: pandas, numpy, json, csv, datetime, statistics
- **File I/O**: Read/write within thread-scoped directories
- **Data viz**: matplotlib for charts and graphs
- **Use cases**:
  - Data transformations
  - Calculations and simulations
  - API integrations
  - File format conversions
  - Custom business logic

### MCP Integration (Model Context Protocol)
Executive Assistant supports extensible tool integration via MCP servers:
- **User-Managed Servers**: Add your own MCP servers per conversation
- **Auto-Detection**: Automatically suggests relevant skills when adding servers
- **Human-in-the-Loop**: Review and approve skills before loading
- **Hot-Reload**: Add/remove servers without restarting
- **Tiered Loading**: User tools override admin tools for customization
- **Backup/Restore**: Automatic backups with manual restore options

**Example Workflow:**
```bash
# Add fetch MCP server
You: Add the fetch MCP server from GitHub
Assistant: ✅ Added 'fetch' server with 1 tool
        📚 Auto-loaded 2 helper skills:
          • web_scraping
          • fetch_content

# Review and approve skills
You: Show pending skills
You: Approve web_scraping
You: Reload

# Now agent knows how to use fetch effectively!
You: Fetch https://example.com and extract the main heading
Assistant: [Uses web_scraping skill + fetch tool]
        Successfully fetched and extracted heading...
```

**Supported MCP Servers:**
- **Fetch**: Web content extraction (`uvx mcp-server-fetch`)
- **GitHub**: Repository operations and code search (`npx @modelcontextprotocol/server-github`)
- **ClickHouse**: Analytics database queries (`uv run --with mcp-clickhouse`)
- **Filesystem**: File operations (requires paths argument)
- **Brave Search**: Web search integration
- **Puppeteer**: Browser automation
- **And more**: Any MCP server can be added!

---

## Admin Configuration: MCP, Skills & Prompts

Administrators can pre-configure MCP servers, custom prompts, and skills that apply to **all users** (Telegram allowlist) or **all HTTP conversations**. This is powerful for:

- **Organization-wide integrations**: Pre-connect databases, APIs, external services
- **Standardized behavior**: Enforce specific query patterns or safety rules
- **Domain expertise**: Load organization-specific knowledge (sales analytics, internal tools)
- **Compliance**: Add mandatory prompts for data handling, privacy, etc.

### Directory Structure

```
data/admins/
├── mcp.json                  # Admin MCP server configuration
├── prompts/
│   └── prompt.md            # Admin system prompt (layered on base prompt)
└── skills/
    ├── on_start/            # Skills loaded at startup (for ALL users)
    │   └── gong_cha_analyst.md
    └── on_demand/           # Skills loaded manually by users
        └── advanced_analytics.md
```

### 1. Admin MCP Servers (`data/admins/mcp.json`)

Pre-configure MCP servers that **all users** can access without manual setup.

**Example: ClickHouse Analytics Database**
```json
{
  "mcpEnabled": true,
  "mcpServers": {
    "clickhouse": {
      "command": "uvx",
      "args": [
        "mcp-clickhouse",
        "--host=172.105.163.229",
        "--port=8123",
        "--user=libre_chat",
        "--password=your_password",
        "--database=gong_cha_redcat_db"
      ],
      "env": {
        "CLICKHOUSE_HOST": "172.105.163.229"
      }
    },
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github", "--personal-access-token", "${GITHUB_TOKEN}"]
    }
  }
}
```

**Key Features:**
- **Stdio servers**: Use `"command"` and `"args"` for local/process servers
- **HTTP/SSE servers**: Use `"url"` for remote servers
- **Environment variables**: Use `"env"` for configuration (supports `${VAR}` expansion)
- **Priority**: User MCP servers override admin servers with the same name

**Loading Behavior:**
- Admin MCP servers are loaded **before** user servers
- Tools from admin servers are available in **all conversations**
- Users can override admin servers by adding their own with the same name

### 2. Admin Prompts (`data/admins/prompts/prompt.md`)

Add system-level instructions that apply to **all conversations**. This is layered **on top of** the base system prompt.

**Example: Gong Cha Data Analyst**
```markdown
# GONG CHA DATA ANALYST - MANDATORY RULES

## DATABASE - USE THIS EXACTLY
- Database: `gong_cha_redcat_db` - NO OTHER DATABASE
- For sales: use `d_txnlines` table
- For stores: use `r_stores` table

## WHEN USER ASKS ABOUT SALES
1. RUN THIS QUERY IMMEDIATELY - DO NOT ASK QUESTIONS:
```sql
SELECT sum(net_amount) as total_sales
FROM gong_cha_redcat_db.d_txnlines
WHERE itemdate = today() - INTERVAL 1 DAY
```

2. Show ONLY the result to user - DO NOT show SQL

## TRIGGER WORDS
If user says: "sales", "sell", "revenue", "yesterday", "how much"
→ RUN THE QUERY ABOVE - NO QUESTIONS

## YOUR TOOLS
- `run_select_query` - use with `gong_cha_redcat_db` database
- `list_databases` - can see databases but ONLY use `gong_cha_redcat_db`
- `list_tables` - can see tables but ONLY use `d_txnlines` for sales

## DO NOT
- DO NOT ask clarifying questions - RUN THE QUERY
- DO NOT use `gong_cha_aupos_db` - WRONG DATABASE
- DO NOT show SQL to users - show only results
- DO NOT suggest other data sources
```

**Prompt Layering Order:**
1. **Base system prompt** (built-in, defines agent capabilities)
2. **Admin prompt** (`data/admins/prompts/prompt.md`) ← **You are here**
3. **Admin skills** (on_start skills)
4. **System skills** (built-in skills from `data/skills/`)
5. **Channel prompts** (Telegram/HTTP-specific prompts)

**Best Practices:**
- **Be directive**: Use "DO NOT", "MUST", "ALWAYS" for critical rules
- **Provide examples**: Show exact queries or patterns to follow
- **List trigger words**: Help LLM recognize when to apply rules
- **Think in tool terms**: Reference specific MCP tools the agent should use

### 3. Admin Skills (`data/admins/skills/`)

Skills provide **contextual knowledge** on how to use tools effectively. There are two types:

#### `on_start/` Skills
Loaded **automatically at startup** for **all users**. Use for:
- Domain-specific patterns (sales analytics, internal tools)
- Mandatory workflows (compliance checks, data handling)
- Organization-specific knowledge

**Example: Gong Cha Analyst (`data/admins/skills/on_start/gong_cha_analyst.md`)**
```markdown
# Gong Cha Data Analyst - STRICT INSTRUCTIONS

## MANDATORY DATABASE
You MUST use `gong_cha_redcat_db` for ALL sales queries. No other database.

## MANDATORY TABLES
- `d_txnlines` - Sales data
- `r_stores` - Store data
- `tbl_plufile` - Product data

## SALES QUERIES - EXACT PATTERNS

For "yesterday's sales":
```sql
SELECT sum(net_amount) as total_sales
FROM gong_cha_redcat_db.d_txnlines
WHERE itemdate = today() - INTERVAL 1 DAY
```

For "best selling products":
```sql
SELECT itemname, sum(net_amount) as sales
FROM gong_cha_redcat_db.d_txnlines
WHERE itemdate >= today() - INTERVAL 7 DAY
GROUP BY itemname
ORDER BY sales DESC
LIMIT 5
```

## TRIGGER WORDS
If user mentions: "sell", "sales", "revenue", "yesterday", "products", "store"
→ RUN THE QUERY. Do not ask questions.
```

#### `on_demand/` Skills
Loaded **manually by users** via the `load_skill` tool. Use for:
- Advanced patterns (not needed for all users)
- Experimental features
- User-specific workflows

**User loads on-demand skills:**
```bash
You: load_skill gong_cha_advanced
Assistant: ✅ Loaded skill: gong_cha_advanced (2.1KB)
        This skill adds advanced ClickHouse analytics capabilities...
```

### 4. Putting It All Together: Complete Example

**Scenario**: You want all agents to query ClickHouse for sales data without asking clarifying questions.

#### Step 1: Configure MCP Server (`data/admins/mcp.json`)
```json
{
  "mcpEnabled": true,
  "mcpServers": {
    "clickhouse": {
      "command": "uvx",
      "args": [
        "mcp-clickhouse",
        "--host=172.105.163.229",
        "--port=8123",
        "--user=libre_chat",
        "--password=your_password",
        "--database=gong_cha_redcat_db"
      ]
    }
  }
}
```

#### Step 2: Add Admin Prompt (`data/admins/prompts/prompt.md`)
```markdown
# GONG CHA DATA ANALYST - MANDATORY RULES

## WHEN USER ASKS ABOUT SALES
RUN THIS QUERY IMMEDIATELY - DO NOT ASK QUESTIONS:
```sql
SELECT sum(net_amount) as total_sales
FROM gong_cha_redcat_db.d_txnlines
WHERE itemdate = today() - INTERVAL 1 DAY
```

## TRIGGER WORDS
"sales", "sell", "revenue", "yesterday" → RUN THE QUERY
```

#### Step 3: Add Admin Skill (`data/admins/skills/on_start/gong_cha_analyst.md`)
```markdown
# Gong Cha Data Analyst

You are the **Gong Cha Data Analyst** with access to Gong Cha's ClickHouse sales database.

## Your ClickHouse Tools
1. `list_databases` - Show all databases
2. `list_tables` - Show tables in a database
3. `run_select_query` - Run SQL SELECT queries

## Key Tables
- `d_txnlines` - Transaction line items (sales, amounts, dates)
- `r_stores` - Store locations

## Query Patterns
**Yesterday's sales**:
```sql
SELECT sum(net_amount) as total_sales
FROM gong_cha_redcat_db.d_txnlines
WHERE itemdate = today() - INTERVAL 1 DAY
```
```

#### Step 4: Restart Service
```bash
pkill -f executive_assistant
rm -rf .cache  # Clear cached tools
EXECUTIVE_ASSISTANT_CHANNELS=http uv run executive_assistant
```

#### Step 5: Test
```bash
curl -X POST http://localhost:8000/message \
  -H 'Content-Type: application/json' \
  -d '{"content": "how much did we sell yesterday", "user_id": "test"}'

# Response: $221,586.02 (instant query, no clarifying questions)
```

### 5. Troubleshooting Admin Configuration

| Issue | Cause | Fix |
|-------|-------|-----|
| Tools not loaded | MCP server not starting | Check `mcp.json` syntax, test command manually |
| Agent ignoring instructions | Admin prompt not found | Ensure path is `data/admins/prompts/prompt.md` |
| Skills not loading | File format incorrect | Skills must start with `# Title` heading |
| User can override admin | This is by design | Users can override admin MCP with same name |

**Check what's loaded:**
```bash
# List MCP servers
You: mcp_list_servers

# Show admin prompt
$ cat data/admins/prompts/prompt.md

# Verify skills are loaded
$ grep "Loaded.*admin skills" /tmp/ken.log
```

### 6. Security Considerations

- **Admin MCP servers**: Available to **all users** (or allowlist in Telegram)
- **Admin prompts**: Cannot be overridden by users
- **Admin skills**: Loaded for all users, make them generic
- **Credentials**: Use environment variables in `.env`, never hardcode in `mcp.json`
- **Permissions**: Admin MCP tools respect existing file/DB permissions

### File Operations
- **Read/write**: Create, edit, and organize files
- **Search**: Find files by pattern (`*.py`, `**/*.json`) or search contents with regex
- **Secure**: Thread-scoped paths prevent access to other users' data

### Transactional Database (TDB, per-thread)
- **Create tables**: From JSON/CSV with automatic schema inference
- **Query**: SQLite-compatible SQL (thread/shared scoped)
- **Import/Export**: CSV, JSON, Parquet formats
- **Use case**: Temporary working data (timesheets, logs, analysis results)

### Vector Database (VDB, per-thread)
- **Semantic search**: Find documents by meaning, not just keywords
- **Hybrid search**: Combines full-text + vector similarity
- **Persistent**: Survives thread resets (thread-scoped)
- **Use case**: Long-term knowledge base (meeting notes, decisions, docs)

### Python Execution
- **Sandboxed**: 30s timeout, path traversal protection, thread-scoped I/O
- **Modules**: json, csv, math, datetime, random, statistics, urllib, etc.
- **Use case**: Calculations, data processing, file transformations

### Web Search
- **Firecrawl integration**: Premium web search API with high-quality results
- **Content extraction**: Optional full content scraping from search results
- **Advanced filters**: Location, time-based, categories (web, news, images)
- **Playwright fallback**: JS-heavy pages can be scraped with the browser tool

### Time & Reminders
- **Timezone-aware**: Current time/date in any timezone
- **Flexible scheduling**: One-time or recurring reminders
- **Multi-thread**: Trigger reminders across multiple conversations

### OCR (optional, local)
- **Image/PDF text extraction**: PaddleOCR or Tesseract
- **Structured extraction**: OCR + LLM for JSON output
- **Use case**: Extract data from screenshots, scans, receipts

## Token Usage & Cost Monitoring

Executive Assistant tracks token usage automatically when using supported LLM providers (OpenAI, Anthropic):

```
CH=http CONV=http_user123 TYPE=token_usage | message tokens=7581+19=7600
```

**Note**: Token tracking depends on LLM provider support:
- **OpenAI/Anthropic**: ✅ Full tracking (input + output + total)
- **Ollama**: ❌ No metadata provided (usage not tracked)

**Token Breakdown** (typical conversation):
- System prompt + 87 tools: ~8,100 tokens (fixed overhead)
- Conversation messages: Grows with each turn
- Total input = overhead + messages (e.g., 8,600 tokens by turn 5)

## Architecture Overview

Executive Assistant uses a **LangChain agent** with middleware stack:

1. **User message** → Channel (Telegram/HTTP)
2. **Channel** → LangChain agent with middleware stack
3. **Middleware** → Status updates, summarization, retry logic, call limits
4. **Agent** → ReAct loop (Think → Act → Observe)
5. **Tools** → Storage (files, TDB, VDB), external APIs
6. **Response** → Channel → User

### Storage Hierarchy

```
data/
├── shared/             # Organization-wide (scope="shared")
│   ├── files/          # Shared files
│   ├── tdb/            # Shared transactional database
│   ├── adb/            # Shared analytics database (DuckDB)
│   └── vdb/            # Shared vector database
└── users/              # Thread-scoped (scope="context")
    └── {thread_id}/
        ├── files/      # Private files
        ├── tdb/        # Working transactional database
        ├── adb/        # Thread analytics database (auto-created)
        ├── vdb/        # Thread vector database
        └── mem/        # Embedded memories
```

### PostgreSQL Schema

| Table | Purpose |
|-------|---------|
| `checkpoints` | LangGraph state snapshots (conversation history) |
| `conversations` | Conversation metadata per thread |
| `messages` | Message audit log |
| `file_paths` | File ownership per thread |
| `tdb_paths` | Transactional Database ownership per thread |
| `vdb_paths` | Vector database ownership per thread |
| `adb_paths` | Analytics DB ownership per thread |
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
│   ├── storage/        # File sandbox, TDB, VDB, reminders
│   ├── tools/          # LangChain tools (file, TDB, time, Python, search, OCR)
│   ├── agent/          # LangChain agent runtime + middleware
│   ├── scheduler.py    # APScheduler integration
│   └── config/         # Settings
├── migrations/         # SQL migrations
├── tests/              # Unit tests
├── features/           # Feature tests
├── scripts/            # Utility scripts
├── pyproject.toml
├── TODO.md
└── README.md
```

## License

Apache License 2.0 - see LICENSE file for details.

**Why Apache 2.0?**
- ✅ Explicit patent grant (protects users from patent litigation)
- ✅ Patent termination clause (license ends if you sue over patents)
- ✅ Corporate-friendly (preferred by large companies)
- ✅ Requires stating changes (better provenance tracking)

## Contributing

Contributions welcome! Please read `CLAUDE.md` for development workflow and testing guidelines.

**Remember**: Always test locally with `uv run executive_assistant` before building Docker. See `CLAUDE.md` for details.

## Tech Stack

Executive Assistant is built on modern, production-ready technologies:

### Core Framework
- **LangGraph** - Agent orchestration and state management
- **LangChain** - LLM abstraction and tool integration
- **Python 3.13** - Core runtime with async/await

### LLM Providers
- **OpenAI** - GPT-4, GPT-4o (recommended for instruction following)
- **Anthropic** - Claude models (Sonnet, Opus, Haiku)
- **Ollama** - Local and cloud LLM hosting
- **Zhipu AI** - GLM-4 models
- **OpenAI-compatible** - Any provider using OpenAI API format

### Databases & Storage
- **PostgreSQL** (via asyncpg) - Conversation state, checkpoints, audit logs
- **SQLite** - Transactional Database (TDB) for structured data
- **DuckDB** - Analytics Database (ADB) for large-scale analytics
- **LanceDB** - Vector Database (VDB) for semantic search

### Channels
- **python-telegram-bot** - Telegram Bot API integration
- **FastAPI** - HTTP channel with SSE streaming
- **Uvicorn** - ASGI server for HTTP channel

### External Integrations
- **Firecrawl** - Web scraping and search API
- **Playwright** - Browser automation for JS-heavy pages
- **MCP (Model Context Protocol)** - Extensible tool integration
- **PaddleOCR** - OCR for image/PDF text extraction

### Scheduling & Async
- **APScheduler** - Reminder and scheduled flow execution
- **asyncio** - Async I/O and concurrent operations
- **asyncpg** - Async PostgreSQL driver

### Utilities
- **pandas** - Data manipulation and analysis
- **matplotlib** - Data visualization
- **Pydantic** - Data validation and settings
- **python-dotenv** - Environment configuration
- **loguru** - Structured logging
- **pytest** - Testing framework with VCR cassettes

### Development Tools
- **uv** - Fast Python package installer and resolver
- **Docker Compose** - PostgreSQL containerization
- **VCR.py** - HTTP request recording for tests
