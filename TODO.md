# TODO

## Completed ✅

### Skills System Implementation (2025-01-19)
- [x] Created SkillsRegistry with in-memory caching
- [x] Created load_skills_from_directory() loader
- [x] Created load_skill tool with fuzzy matching
- [x] Created SkillsBuilder for progressive disclosure (renamed from SkillsMiddleware)
- [x] Integrated skills into main.py (auto-load on startup)
- [x] Created 10 skills total:
  - 5 Core Infrastructure: data_management, progress_tracking, record_keeping, synthesis, workflow_patterns
  - 5 Personal Application: task_tracking, information_retrieval, report_generation, planning, organization
- [x] Integration tests: All 10 skills load successfully, fuzzy matching works
- [x] **Phase 3: Tool Description Alignment** - Updated DB and file tool descriptions with Minimalist Format
  - 8 DB tools updated (create, insert, query, list, describe, delete, export, import)
  - 6 file tools updated (read, write, list, glob, grep)
  - Focus: "when to use" (not "how to use") - skills teach workflows
- See: `discussions/subagents-vs-skills-plan-20250119.md` for full design

### Status Update Middleware & Debug Mode (2026-01-19)
- [x] Create `StatusUpdateMiddleware` for real-time progress feedback
- [x] Add `/debug` command to Telegram (verbose mode toggle)
- [x] LLM timing tracking with token usage logging
- [x] Millisecond timestamps in all logs (`src/executive_assistant/logging.py`)
- [x] Thread-local storage for LLM timing across execution contexts
- [x] Status messages: "Thinking..." → tool progress → "Done in X.Xs | LLM: Y calls (Z.Zs)"
- See: `discussions/telegram-debug-command-20250119.md` for full design

### File Upload Path Fix (2026-01-19)
- [x] Fixed file uploads to use group-based routing
- [x] Files stored in `data/groups/{group_id}/files/` matching agent tools
- [x] Set up group context before downloading files in Telegram channel

### Storage Layout Cleanup
- [x] Route thread file paths through `USERS_ROOT` helpers
- [x] Stop eager creation of legacy `./data/db` and `./data/vs` on startup
- [x] **Workspace→Group Refactoring** (2026-01-18)
  - Renamed `workspace_storage.py` → `group_storage.py`
  - Added `GROUPS_ROOT` and `USERS_ROOT` path helpers
  - Added `get_group_*()` and `get_user_*()` methods
  - Updated all imports across codebase
  - 342 tests passing (see `discussions/workspace-to-group-refactoring-plan.md`)

### Reminder Feature
- [x] Install APScheduler dependency
- [x] Create migrations/004_reminders.sql
- [x] Create src/executive_assistant/storage/reminder.py
- [x] Create src/executive_assistant/tools/reminder_tools.py (set, list, cancel, edit)
- [x] Create src/executive_assistant/scheduler.py (APScheduler integration)
- [x] Add /reminders bot command
- [x] Test reminder creation and sending

### Python Code Execution
- [x] Create src/executive_assistant/tools/python_tool.py
- [x] Sandboxed execution with timeout
- [x] Thread-scoped file I/O
- [x] Module whitelist (json, csv, math, datetime, urllib, etc.)
- [x] Unit tests (32 tests)

### File Search
- [x] Add `glob_files` tool for pattern matching
- [x] Add `grep_files` tool for content search
- [x] Unit tests (10 tests)

### Middleware Debug Logging (2026-01-19)
- [x] Create `middleware_debug.py` with detection utilities
- [x] Add summarization detection (token/message before/after)
- [x] Add context editing detection (tool_uses reduction)
- [x] Add retry tracking (LLM and tool call counting)
- [x] Logs: `[SUMMARIZATION] 45→3 msgs (42 removed)`
- [x] Logs: `[CONTEXT_EDIT] Tool uses: 20→5 (15 removed, 75% reduction)`
- [x] Logs: `[LLM_RETRY] Expected 1 call, got 2 (1 retry)`
- [x] Logs: `[TOOL_RETRY] Expected 1 tool call, got 3 (2 retries)`
- See: `discussions/middleware-debug-logging-20250119.md` for full design

## Design (Locked In)

**Scheduler:** APScheduler + DB persistence
- Load pending reminders on startup
- Poll DB every 60s for new reminders
- Exact timing for fired jobs
- DB as source of truth for observability

**Channels:** Telegram, Email (extensible)
- Each channel implements send_notification(user_id, message)

**Reminder Tools:**
- `set_reminder(message, time, recurrence)` - Create new reminder
- `list_reminders()` - Show user's active reminders
- `cancel_reminder(reminder_id)` - Cancel a pending reminder
- `edit_reminder(reminder_id, message, time, recurrence)` - Edit existing reminder

**Database:**
```sql
CREATE TABLE reminders (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    thread_ids TEXT[],
    message TEXT NOT NULL,
    due_time TIMESTAMP NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    recurrence VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    sent_at TIMESTAMP,
    error_message TEXT
);
```

## Fixes / Refactors
- [ ] Standardize tool names to verb-first across file/db/vs/time tools; update registry/docs/tests and keep temporary aliases
- [ ] Decide Firecrawl integration path (direct API vs MCP) and align settings/deps accordingly
- [ ] Implement recurring reminders by creating the next instance after send
- [ ] Validate SQL identifiers (table_name) in db/vs tools to prevent injection
- [ ] Fix memory FTS indexing/query to use DuckDB match_bm25 (avoid falling back to LIKE)
- [x] **ToolRetry & ModelRetry Debug Logging** (2026-01-19)
  - [x] Added retry detection via `RetryTracker` class
  - [x] Logs when LLM or tools retry unexpectedly
  - [x] See: `discussions/middleware-debug-logging-20250119.md`
- [x] **Realistic Response Time Testing** (2026-01-19)
  - [x] Created `scripts/measure_response_time.py` for full-stack timing
  - [x] Created `discussions/realistic-response-time-test-plan-20250119.md`
  - [x] Identified overhead source: LLM is 68-98% of total time, stack overhead is minimal (120-320ms)
  - [x] Compared GPT-5 Mini vs GPT-4o Mini: GPT-4o Mini is 3-5x faster
  - [x] Memory retrieval adds ~300ms cold, ~30ms warm (negligible)
  - [x] Recommendation: Switch to GPT-4o Mini for production
- [ ] Context editing middleware (see `discussions/context-editing-middleware-plan-20260116-1655.md`)
- [ ] **ShellToolMiddleware** (see `discussions/shell-tool-middleware-plan-20260116.md`)
  - [ ] Add settings to `src/executive_assistant/config/settings.py`
  - [ ] Wire up middleware in `src/executive_assistant/agent/langchain_agent.py`
  - [ ] Update `.env.example` with shell settings
  - [ ] Update prompts in `src/executive_assistant/agent/prompts.py`
  - [ ] Add unit tests (enabled/disabled states)

## Ideas / Future Work

### OCR (Optical Character Recognition)

Extract text from images using PaddleOCR (local, free, ~50MB).

**Library:** PaddleOCR - excellent Chinese + English support, CPU-friendly

**Tools:**
```python
ocr_extract_text(image_path, output_format="text")  # Plain text or JSON with bboxes
ocr_extract_structured(image_path, instruction)  # OCR + LLM for structured data
extract_from_image(image_path, instruction, method="auto")  # Auto-select best method
```

**Hybrid Approach:**
- **PaddleOCR** for simple text extraction (fast, free, local)
- **Vision model** (GPT-4o) for structured data, tables, forms

**Dependencies:**
```txt
paddleocr>=2.7.0
paddlepaddle>=2.6.0
```

**Docker Impact:** +150MB image size

**See:** `discussions/ocr-tool-design-20250116.md` for full design

---

### Workflow System

On-the-fly workflow creation and scheduling with executor chains.

**Architecture:**
- Each executor = `create_agent()` with specific tools/prompt
- Prompt injection: previous executor's output → next executor's prompt as JSON
- No explicit control flow: loops embedded in prompt ("run 5 times", "for each item")
- Shared context accumulates all executor outputs

**Tools:**
```python
workflow_create(name, executors, schedule=None)  # Create workflow
workflow_run(workflow_id, input_data)  # Run immediately
workflow_schedule(workflow_id, schedule, input_data)  # Schedule for later
workflow_list()  # List user's workflows
workflow_status(run_id)  # Check workflow run status
```

**Data Model:**
```sql
CREATE TABLE workflows (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    thread_id VARCHAR(255),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    executors JSONB NOT NULL,  -- [{name, tools, prompt, output_schema}]
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE workflow_runs (
    id SERIAL PRIMARY KEY,
    workflow_id INT REFERENCES workflows(id),
    status VARCHAR(20) DEFAULT 'running',  -- running, completed, failed
    input_data JSONB,
    output_data JSONB,
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);

CREATE TABLE workflow_executor_runs (
    id SERIAL PRIMARY KEY,
    workflow_run_id INT REFERENCES workflow_runs(id),
    executor_name VARCHAR(255),
    input_data JSONB,
    output_data JSONB,
    tool_calls JSONB,  -- [{tool, input, output, duration}]
    error_message TEXT,
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);
```

**Example Workflow:**
```python
workflow = workflow_create(
    name="daily_price_check",
    executors=[
        {
            "name": "fetch_prices",
            "tools": ["http_get"],
            "prompt": "Fetch prices from {url}",
            "output_schema": {"prices": "array"}
        },
        {
            "name": "compare_prices",
            "tools": ["python_execute"],
            "prompt": "Compare these prices: {output[from='fetch_prices']}",
            "output_schema": {"deals": "array"}
        },
        {
            "name": "send_alert",
            "tools": ["email_send"],
            "prompt": "Send alert with deals: {output[from='compare_prices']}",
            "output_schema": {"sent": "boolean"}
        }
    ],
    schedule="0 9 * * *"  # Daily at 9am
)
```

**See:** `discussions/workflow-design-20250116.md` for full design

---

### Calendar Integration (External APIs)

Per thread/user calendar integration with OAuth tokens. No local storage - everything in user's external calendar.

**Supported Providers:**
- Google Calendar (via Google Calendar API)
- Microsoft Outlook (via Microsoft Graph API)
- Extensible for others (CalDAV, Apple Calendar)

**Authentication:**
- OAuth 2.0 flow per user/thread
- Tokens stored in database: `user_id`, `provider`, `access_token`, `refresh_token`, `expires_at`
- Thread-scoped: each thread can have its own calendar context

**Tools:**
```python
calendar_list_events(start_date, end_date)  # List events in date range
calendar_create_event(title, start, end, description, attendees, recurrence)
calendar_update_event(event_id, ...)
calendar_delete_event(event_id)
calendar_find_event(query)  # Search by title/description
```

**Data Model:**
```sql
CREATE TABLE user_calendars (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    thread_id VARCHAR(255),  -- NULL for user-level default
    provider VARCHAR(50) NOT NULL,  -- 'google', 'outlook'
    external_calendar_id VARCHAR(255),  -- User's calendar ID on provider
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    token_expires_at TIMESTAMP,
    is_default BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Recurrence:** Use iCal RRULE format (standard, compatible with all providers)

**Implementation Notes:**
- Use `google-api-python-client` for Google Calendar
- Use `msal` for Microsoft Graph authentication
- Token refresh handled automatically before expiry
- All operations proxied through Executive Assistant - no direct API exposure

---

### Email

Two distinct email functionalities:

#### Type 1: Executive Assistant's Email Channel (Communication)
Executive Assistant's own email address (e.g., `hello@executive_assistant.com.au`) for bi-directional user communication.

**Implementation:**
- IMAP for receiving incoming emails
- SMTP for sending replies
- Maps incoming emails to user_id via sender email
- Similar to Telegram channel architecture

**Data Model:**
```sql
CREATE TABLE email_channel_users (
    user_id VARCHAR(255) PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,  -- User's verified email
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Channel Handler:**
```python
# src/executive_assistant/channels/email.py
class EmailChannel(BaseChannel):
    # Poll IMAP for new emails
    # Match sender to user_id via email_channel_users
    # Pass to agent, reply via SMTP
```

---

#### Type 2: User Authenticated Email (Actions)
Users connect their own email (Gmail, iCloud, Outlook) for Executive Assistant to send/read on their behalf.

**Authentication:** OAuth 2.0 per user (similar to calendar)

**Supported Providers:**
- Gmail (via Gmail API)
- Outlook/Microsoft 365 (via Microsoft Graph)
- iCloud (via IMAP + App Specific Password)
- Generic IMAP/SMTP (self-hosted, custom domains)

**Tools:**
```python
# Send email AS the user
email_send(to, subject, body, attachments=None)

# Read/list user's emails
email_list(folder='inbox', query=None, limit=20)
email_read(message_id)

# Manage emails
email_archive(message_id)
email_delete(message_id)
email_mark_read(message_id)
```

**Data Model:**
```sql
CREATE TABLE user_email_accounts (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    provider VARCHAR(50) NOT NULL,  -- 'gmail', 'outlook', 'icloud', 'imap'
    email_address VARCHAR(255) NOT NULL,
    access_token TEXT,
    refresh_token TEXT,
    token_expires_at TIMESTAMP,
    imap_host VARCHAR(255),  -- For IMAP providers
    imap_port INT,
    imap_username VARCHAR(255),
    imap_password TEXT,  -- App-specific password, encrypted
    is_default BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE email_send_queue (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    from_account_id INT REFERENCES user_email_accounts(id),
    to_email VARCHAR(255) NOT NULL,
    subject TEXT NOT NULL,
    body_text TEXT,
    body_html TEXT,
    attachments JSONB,
    status VARCHAR(20) DEFAULT 'pending',
    attempts INT DEFAULT 0,
    last_error TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    sent_at TIMESTAMP
);
```

**Dependencies:**
- Gmail: `google-api-python-client`
- Outlook: `msal`
- Generic IMAP: Built-in `imaplib`

---

### Scheduling Extensions (APScheduler)

With APScheduler integrated, we could add:

1. **Scheduled Queries / Reports**
   - `schedule_report(query, time, recurrence)` - Run DB queries periodically
   - `schedule_summary(thread_id, time)` - Generate conversation summaries
   - Daily/weekly data summaries delivered to user

2. **Scheduled Web Queries**
   - `schedule_web_check(url, condition, time)` - Monitor websites for changes
   - Price tracking, stock updates, RSS feed polling
   - Notify when content changes

3. **Workflow Automation**
   - `schedule_chain(task1, task2, ...)` - Execute tools in sequence
   - Data pipeline: fetch → transform → store
   - Batch operations on databases

4. **Recurring Data Operations**
   - Auto-cleanup old files/messages
   - Database maintenance (vacuum, compact)
   - Backup scheduled data

5. **Time-Based Triggers**
   - "Remind me when market opens" (time-based)
   - "Send me weather at 7am daily"
   - "Summarize my conversations every Sunday"

### Other Ideas

- **MCP Tool Integration** - Add more MCP server integrations
- **BYO MCP (Thread-First)** - Self-serve MCP servers per thread, share after merge
  - Postgres `mcp_servers` table with `thread_id`, `user_id`, `config_version`
  - Self-serve CRUD (UI/API + optional LLM tool) with manifest validation and SSRF guardrails
  - Tool registry rebuild per `(owner_key, max(config_version))`
  - Merge behavior: set `user_id` for thread-owned servers and dedupe by `(server_url, name)`
- **Resource Catalog + Topic Router** - Make Executive Assistant aware of per-thread resources
  - Postgres catalog keyed by `(owner_type, owner_id)` with `resource_type` (file|vs|db|reminder)
  - Tool hooks update catalog on create/update/delete
  - Tools: `list_resources`, `find_resource`, `describe_resource`
  - Prompt routing: ask "files vs VS vs DB vs reminders" when ambiguous
- **Tool Groups + Lazy Disclosure** - Opt-in tools with gradual enablement
  - Define groups: `core`, `vs`, `db`, `search`, `python`, `reminders`, `mcp`
  - Per-channel defaults + per-user overrides
  - Lazy load only enabled groups
  - Incremental disclosure: ask to enable group when needed
- **Conversation Export** - Export conversations to markdown/PDF
- **Analytics Dashboard** - Web UI for viewing statistics
- **Multi-Language Support** - Detect and respond in user's language
- **Framework Agnostic Agent Runtime** - Support multiple agent frameworks (LangChain, Agno, etc.)
  - See: `discussions/framework-agnostic-agent-design-20250119.md` for full analysis
