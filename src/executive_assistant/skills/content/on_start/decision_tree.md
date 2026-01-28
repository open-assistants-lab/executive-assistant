# Storage Decision Tree

Description: Quick guide to choosing the right storage for your task

Tags: core, storage, decision, guide

## One-Minute Decision Tree

```
What are you storing?
│
├─ User preference or personal fact?
│  └─ → MEMORY
│      Examples: "User prefers dark mode", "Timezone: EST"
│      Tools: create_memory, get_memory_by_key
│
├─ Structured data for daily tracking?
│  ├─ Need complex analytics (window functions, joins)?
│  │  └─ → ADB (Analytics DB)
│  │      Examples: Monthly reports, running totals, time-series
│  │      Tools: list_adb_tables, describe_adb_table, query_adb, import_adb_csv, export_adb_table
│  │
│  └─ Simple CRUD, frequent updates?
│      └─ → TDB (Transactional DB)
│          Examples: Timesheets, expenses, habits
│          Tools: create_tdb_table, query_tdb
│
├─ Documents, notes, knowledge?
│  └─ Need semantic search (find by meaning)?
│      └─ → VDB (Vector DB)
│          Examples: Meeting notes, documentation
│          Tools: create_vdb_collection, search_vdb
│
└─ Reports, exports, files?
   └─ → FILES
       Examples: Generated reports, CSV exports
       Tools: write_file, read_file
```

## Comparison Table

| Storage | Best For | Query Method | Example Use Case |
|---------|----------|--------------|------------------|
| **Memory** | Preferences, facts | Key lookup | "User prefers Python" |
| **TDB** | Daily tracking | SQL (SQLite) | Timesheets, expenses |
| **ADB** | Analytics, complex SQL | SQL (DuckDB) | Monthly reports, aggregations |
| **VDB** | Documents, knowledge | Semantic search | Meeting notes, research |
| **Files** | Reports, exports | Path-based | Generated markdown, CSV |

## Common Patterns

| Task | Storage | Example |
|------|---------|---------|
| Track daily expenses | TDB | `create_tdb_table("expenses", data)` |
| Analyze yearly spending | ADB | `query_adb("SELECT SUM(amount) FROM expenses GROUP BY month")` |
| Save meeting notes | VDB | `create_vdb_collection("meetings", content)` |
| Remember user likes dark mode | Memory | `create_memory("Prefers dark mode", "preference", key="theme")` |
| Generate weekly report | Files | `write_file("weekly_report.md", content)` |

## When to Use Which

### Use TDB when:
- Daily tracking (habits, expenses, timesheets)
- Frequent small updates
- Simple SQL queries (SELECT, INSERT, UPDATE)

### Use ADB when:
- Complex aggregations (window functions, CTEs)
- Large datasets (millions of rows)
- Importing/analyzing CSV files
- Time-series analysis

### Use VDB when:
- Documents, meeting notes
- Semantic search (find by meaning)
- Knowledge base

### Use Memory when:
- User preferences
- Important facts about user
- Personalization settings

### Use Files when:
- Reports, exports
- Configuration files
- Code snippets

## Need Details?

Load detailed guides:
- `load_skill("storage")` - Deep dive into all storage types
- `load_skill("analytics")` - Complex SQL, window functions
- `load_skill("flows")` - Automation with flows and agents
