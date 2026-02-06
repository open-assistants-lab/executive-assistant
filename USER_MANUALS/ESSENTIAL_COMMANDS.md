# Essential Commands Reference

This is a quick reference for the most commonly used commands in Ken Executive Assistant.

---

## 🧠 Memory Commands

Store and retrieve important information.

### `/mem list`
**Show all stored memories**
```
You: /mem list
Ken: Found 5 memories:
     1. API key: sk-xxxxx (added 2 days ago)
     2. Project deadline: March 15
     3. Manager: Sarah Johnson
     4. Preferred format: JSON
     5. Database: production_postgres
```

### `/mem add key: "value"`
**Add a new memory**
```
You: /mem add project_alpha: "My secret project"
Ken: ✅ Saved memory: project_alpha
```

### `/mem search "keyword"`
**Search memories by keyword**
```
You: /mem search "project"
Ken: Found 2 memories:
     1. project_alpha: "My secret project"
     2. current_project: "Sales dashboard"
```

### `/mem update key`
**Update an existing memory**
```
You: /mem update project_alpha
Ken: Current value: "My secret project"
     New value: Project Alpha: AI assistant platform
     ✅ Updated
```

### `/mem forget key`
**Delete a memory**
```
You: /mem forget old_api_key
Ken: ✅ Forgotten: old_api_key
```

---

## ⏰ Reminder Commands

Schedule one-time or recurring reminders.

### `/reminder list`
**Show all reminders**
```
You: /reminder list
Ken: Active Reminders:
     1. "Review PRs" - Weekdays at 3:00 PM
     2. "Daily standup" - Daily at 9:00 AM
     3. "Team meeting" - Feb 20 at 2:00 PM
```

### `/reminder set time "message"`
**Set a one-time reminder**
```
You: /reminder set 3pm "Call with vendor"
Ken: ✅ Reminder set: "Call with vendor" at 3:00 PM today
```

### `/reminder set time "message" --daily`
**Set a daily recurring reminder**
```
You: /reminder set 9am "Check emails" --daily
Ken: ✅ Recurring reminder: "Check emails" every day at 9:00 AM
```

### `/reminder set day time "message" --weekly`
**Set a weekly recurring reminder**
```
You: /reminder set monday 9am "Weekly planning" --weekly
Ken: ✅ Recurring reminder: "Weekly planning" every Monday at 9:00 AM
```

### `/reminder set time "message" --weekdays`
**Set weekdays-only reminder**
```
You: /reminder set 5pm "Review daily progress" --weekdays
Ken: ✅ Recurring reminder: Mon-Fri at 5:00 PM
```

### `/reminder edit id "new message"`
**Edit reminder text**
```
You: /reminder edit 1 "Review critical PRs"
Ken: ✅ Reminder #1 updated
```

### `/reminder cancel id`
**Cancel a reminder**
```
You: /reminder cancel 1
Ken: ✅ Cancelled reminder #1
```

---

## 📁 File Commands

Work with files in your personal storage.

### `/file list`
**List all files**
```
You: /file list
Ken: Your files (15 files, 2.3 MB):
     📄 sales_report.csv (245 KB)
     📄 meeting_notes.md (12 KB)
     📁 reports/ (5 files)
```

### `/file read filename`
**Read a file**
```
You: /file read notes.txt
Ken: [File content]
```

### `/file write filename "content"`
**Write a file**
```
You: /file write summary.md "Meeting summary: Discussed Q1 goals..."
Ken: ✅ Created: summary.md
```

### `/file search "pattern" --glob *.py`
**Search in files**
```
You: /file search "TODO" --glob *.py
Ken: Found 3 matches:
     app.py:15: # TODO: Add validation
     utils.py:42: # TODO: Refactor
```

### `/file move old.txt new.txt`
**Rename/move file**
```
You: /file move draft.md final.md
Ken: ✅ Renamed: draft.md → final.md
```

### `/file delete filename`
**Delete a file**
```
You: /file delete old_report.csv
Ken: ✅ Deleted: old_report.csv
```

---

## 💾 Database Commands (TDB)

Work with structured data using SQL.

### `/tdb list`
**Show all tables**
```
You: /tdb list
Ken: Your tables:
     📊 timesheets (127 rows)
     📊 projects (8 rows)
     📊 tasks (45 rows)
```

### `/tdb create tablename`
**Create a new table**
```
You: /tdb create users
Ken: ✅ Created table: users
     Upload CSV/JSON data or add rows manually
```

### `/tdb query tablename "SQL query"`
**Run SQL query**
```
You: /tdb query timesheets "SELECT * FROM timesheets WHERE date >= '2024-01-01'"
Ken: Query results:
     | date       | project    | hours |
     |------------|------------|-------|
     | 2024-01-15 | dashboard  | 4     |
     | 2024-01-16 | api        | 3     |
```

### `/tdb describe tablename`
**Show table schema**
```
You: /tdb describe timesheets
Ken: Table: timesheets (127 rows)
     Columns:
     - id: INTEGER (primary key)
     - date: TEXT
     - project: TEXT
     - hours: REAL
```

### `/tdb export tablename CSV`
**Export table to file**
```
You: /tdb export timesheets CSV
Ken: ✅ Exported: timesheets_export.csv
```

---

## 🔍 Knowledge Base Commands (VDB)

Store and search documents by meaning.

### `/vdb list`
**Show all collections**
```
You: /vdb list
Ken: Your collections:
     📚 docs (23 documents)
     📚 meetings (15 documents)
```

### `/vdb create collection_name`
**Create new collection**
```
You: /vdb create decisions
Ken: ✅ Created collection: decisions
```

### `/vdb add collection "content"`
**Add document to collection**
```
You: /vdb add decisions "We decided to use PostgreSQL for the new project..."
Ken: ✅ Added to collection: decisions (1 document)
```

### `/vdb search collection "query"`
**Semantic search**
```
You: /vdb search decisions "database choice"
Ken: Found 2 relevant documents:

     1. "Database Decision" (Jan 15)
        "We decided to use PostgreSQL for the new project because..."
        Similarity: 0.92

     2. "Architecture Discussion" (Jan 20)
        "Database layer will use PostgreSQL with connection pooling..."
        Similarity: 0.87
```

---

## 📊 Analytics Database Commands (ADB)

For large-scale analytics (100K+ rows).

### Create analytics table
```
You: Create an analytics table from sales.csv
Ken: ✅ Created ADB table: sales_data
     Imported 500,000 rows in 2.3 seconds
```

### Query analytics
```
You: Show me monthly sales totals
Ken: [Runs DuckDB query]
     Monthly Sales:
     Jan: $234,567
     Feb: $245,890
     Mar: $267,123
```

---

## 🎯 Goals Commands

Track objectives and progress.

### `/goals create "Goal name"`
**Create a goal**
```
You: /goals create "Launch sales dashboard"
Ken: ✅ Created goal: "Launch sales dashboard"
     Set target date and priority? (optional)
```

### `/goals progress "Goal name" percentage`
**Update progress**
```
You: /goals progress "Launch sales dashboard" 50
Ken: ✅ Progress updated: 50%
     Last update: 30% (on 2024-01-20)
```

### `/goals list`
**Show all goals**
```
You: /goals list
Ken: Your Goals:
     🎯 Launch sales dashboard - 50% (due: Feb 15)
     🎯 Complete API migration - 75% (due: Mar 1)
     ✅ Setup monitoring - 100% (completed)
```

---

## 🛠️ System Commands

### `/debug on` / `/debug off`
**Toggle verbose mode**
```
You: /debug on
Ken: Debug mode enabled. You'll see detailed progress and timing.

You: [ask a question]
Ken: 🤔 Thinking...
     🛠️ 1: run_select_query
     🛠️ 2: list_tables
     ✅ Done in 12.5s | LLM: 2 calls (11.8s)
```

### `/meta`
**Show storage overview**
```
You: /meta
Ken: Storage Overview:
     Files: 15 files (2.3 MB)
     TDB: 3 tables (180 rows)
     VDB: 2 collections (38 documents)
     Reminders: 5 active
     Memories: 12 stored
```

### `/reset`
**Reset conversation** (clears current chat history, but keeps data)
```
You: /reset
Ken: Conversation reset. Your data and memories are preserved.
```

---

## 🧠 Instincts & Skills Commands

### `list_instincts`
**Show learned behavioral patterns**
```
You: list_instincts
Ken: Learned patterns (confidence):
     • Prefers concise summaries (85%)
     • Uses bullet points (72%)
     • Asks for JSON output (68%)
```

### `evolve_instincts`
**Turn patterns into reusable skills**
```
You: evolve_instincts
Ken: Generated 2 draft skills:
     1. communication_concise (85% confidence)
     2. analytics_workflow (72% confidence)

     Approve with: approve_evolved_skill('draft_id')
```

### `list_skills`
**Show available skills**
```
You: list_skills
Ken: Available skills (18 total):
     • analytics_duckdb - Advanced DuckDB analytics
     • planning - Project planning
     • synthesis - Combine multiple data sources
     ...
```

### `load_skill skill_name`
**Load a skill**
```
You: load_skill analytics_duckdb
Ken: ✅ Loaded skill: analytics_duckdb
     Advanced DuckDB analytics capabilities enabled
```

---

## 🔌 MCP Integration Commands

### `mcp_list_servers`
**Show configured MCP servers**
```
You: mcp_list_servers
Ken: MCP Servers:
     • clickhouse (admin) - 3 tools
     • fetch (user) - 1 tool
```

### `mcp_show_server name`
**Show server details**
```
You: mcp_show_server clickhouse
Ken: Server: clickhouse
     Tools: run_select_query, list_tables, list_databases
```

---

## 💡 Pro Tips

### Natural Language Works Too!
Most commands can be used with natural language:
```
You: Set a reminder for 3pm to call the vendor
You: Show me all my reminders
You: What's in my timesheets table?
You: Search for documents about API decisions
```

### Chain Commands
```
You: Import sales.csv to a table, then show me top 10 products
Ken: ✅ Imported 500 rows to: sales_data
     Query results:
     1. Widget Pro - $45,234
     2. Premium Pack - $38,912
     ...
```

### Get Help
```
You: help
You: what can you do?
You: show all commands
```

---

**Need more?**
- See [GETTING_STARTED.md](GETTING_STARTED.md) for introduction
- See [MEMORY_AND_KNOWLEDGE.md](MEMORY_AND_KNOWLEDGE.md) for memory system details
