# TODO

## Completed ✅

### Reminder Feature
- [x] Install APScheduler dependency
- [x] Create migrations/004_reminders.sql
- [x] Create src/cassey/storage/reminder.py
- [x] Create src/cassey/tools/reminder_tools.py (set, list, cancel, edit)
- [x] Create src/cassey/scheduler.py (APScheduler integration)
- [x] Add /reminders bot command
- [x] Test reminder creation and sending

### Python Code Execution
- [x] Create src/cassey/tools/python_tool.py
- [x] Sandboxed execution with timeout
- [x] Thread-scoped file I/O
- [x] Module whitelist (json, csv, math, datetime, urllib, etc.)
- [x] Unit tests (32 tests)

### File Search
- [x] Add `glob_files` tool for pattern matching
- [x] Add `grep_files` tool for content search
- [x] Unit tests (10 tests)

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

## Ideas / Future Work

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

- **Email Channel** - Extend notification system for email delivery
- **MCP Tool Integration** - Add more MCP server integrations
- **BYO MCP (Thread-First)** - Self-serve MCP servers per thread, share after merge
  - Postgres `mcp_servers` table with `thread_id`, `user_id`, `config_version`
  - Self-serve CRUD (UI/API + optional LLM tool) with manifest validation and SSRF guardrails
  - Tool registry rebuild per `(owner_key, max(config_version))`
  - Merge behavior: set `user_id` for thread-owned servers and dedupe by `(server_url, name)`
- **Conversation Export** - Export conversations to markdown/PDF
- **Analytics Dashboard** - Web UI for viewing statistics
- **Multi-Language Support** - Detect and respond in user's language
