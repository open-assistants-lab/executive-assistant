# Data Management

Description: Learn to choose the right storage (TDB, VDB, ADB, Files, Memories) for your task and access it efficiently.

Tags: core, infrastructure, storage, db, vdb, tdb, adb, files, memories

## Overview

This skill teaches you how to choose between storage options: Transactional Database (TDB), Vector Database (VDB), Analytics Database (ADB), Files, and Memories. All are **persisted** storage - the difference is **how you query/access them**.

---

## Storage Decision Framework

### Transactional Database (TDB) - Persisted, SQL-Queryable, Structured

**When to use:**
- Structured data with consistent schema (timesheets, expenses, habits)
- Data that needs SQL queries: filtering, sorting, grouping, aggregation
- Quantitative analysis: counts, sums, averages, comparisons
- Data that grows over time and needs regular updates

**Examples:**
- Timesheets: date, hours, project, description
- Expenses: amount, category, date, vendor
- Habits: habit_name, date, completed, streak
- Customer data: name, email, signup_date, tier

**Characteristics:**
- ✅ SQL queries for exact matching, complex filters, joins
- ✅ Quantitative analysis (COUNT, SUM, AVG, MAX, MIN)
- ✅ Efficient for: "Find all X where Y > Z"
- ✅ Best for structured, tabular data
- ❌ Not good for semantic search or fuzzy matching
- ⚠️ Ignore SQLite system tables like `sqlite_sequence` in user-facing lists

**Tool Pattern:**
```
1. create_tdb_table - Define schema (or infer from data)
2. insert_tdb_table - Add data
3. add_tdb_column - Extend schema when new fields appear
4. drop_tdb_column - Remove unused columns
5. query_tdb - Retrieve with SQL queries
```

**Data Format:**
Both Python lists and JSON strings work:
```python
# Python list (easier)
create_tdb_table("expenses", data=[{"category": "groceries", "amount": 45.50}])

# JSON string (also accepted)
create_tdb_table("expenses", data='[{"category": "groceries", "amount": 45.50}]')
```

**Example Workflow:**
```python
# User: "Track my daily expenses"
create_tdb_table("expenses", data=[{"category": "groceries", "amount": 45.50, "date": "2025-01-19"}])
insert_tdb_table("expenses", data=[{"category": "transport", "amount": 12.00, "date": "2025-01-19"}])
query_tdb("SELECT category, SUM(amount) as total FROM expenses GROUP BY category")
# → Shows spending by category
```

---

### Vector Transactional Database (VDB) - Persisted, Semantic Search, Qualitative

**When to use:**
- Qualitative knowledge: meeting notes, documentation, conversations
- Semantic search (find by meaning, not exact words)
- "Find similar to X" or "What do we know about Y" queries
- Content that doesn't fit into rigid table structure

**Examples:**
- Meeting notes: "We discussed Q1 goals and decided to..."
- Documentation: Knowledge base articles, how-to guides
- Conversations: Chat history with users
- Research: Articles, papers, reference materials

**Characteristics:**
- ✅ Semantic search (finds related concepts, not just keywords)
- ✅ Qualitative content (text, descriptions, concepts)
- ✅ Efficient for: "Find documents similar to X"
- ✅ Automatic chunking of long documents
- ❌ Not good for exact matching or quantitative analysis
- ❌ Can't do SQL-style aggregations

**Tool Pattern:**
```
1. create_vdb_collection - Create collection (optional: add initial content)
2. add_vdb_documents - Add more documents
3. search_vdb - Semantic search by meaning
```

**Example Workflow:**
```python
# User: "Save our meeting notes for later"
create_vdb_collection("meetings", content="Discussed Q1 goals: increase user engagement by 20%")

# Later: "What did we decide about goals?"
search_vdb("goals", "meetings")
# → Finds meeting about Q1 goals even if you search for "objectives" or "targets"
```

---

### Analytics Database (ADB) - Persisted, DuckDB, Complex Analytics

**When to use:**
- Complex aggregations with window functions
- Large dataset analysis (millions of rows)
- Joins across multiple tables
- Analytics queries: CTEs, subqueries, pivoting
- Importing and querying external files (CSV, Parquet)

**Examples:**
- Monthly reports with running totals and comparisons
- Time-series analysis with moving averages
- Data imports from large CSV files
- Complex SQL with multiple CTEs

**Characteristics:**
- ✅ Complex SQL (window functions, CTEs, subqueries)
- ✅ Fast analytics on large datasets (columnar storage)
- ✅ Query external files directly without importing
- ✅ Better performance for read-heavy analytical workloads
- ❌ Not optimized for frequent small updates (use TDB)
- ⚠️ Slightly higher overhead than TDB for simple CRUD

**Tool Pattern:**
```
1. import_adb_csv - Import large CSV files
2. query_adb - Execute DuckDB SQL
3. export_adb_table - Save results to file
```

**Example Workflow:**
```python
# User: "Analyze my yearly spending patterns"

# Import large CSV
import_adb_csv("expenses_2024.csv", table_name="expenses")

# Complex analysis with window functions
query_adb("""
    SELECT 
        strftime('%Y-%m', date) as month,
        category,
        SUM(amount) as total,
        SUM(SUM(amount)) OVER (ORDER BY strftime('%Y-%m', date)) as running_total,
        AVG(SUM(amount)) OVER (ORDER BY strftime('%Y-%m', date) ROWS 2 PRECEDING) as moving_avg
    FROM expenses
    GROUP BY month, category
    ORDER BY month, total DESC
""")
# → Shows monthly spending with running totals and 3-month moving average
```

**TDB vs ADB:**
- Use **TDB** for: Daily tracking, frequent updates, simple queries
- Use **ADB** for: Analytics, complex SQL, large datasets, window functions

---

### Memories - Persisted, Key-Value, User Preferences

**When to use:**
- User preferences and settings
- Important facts about the user
- Conversation context to remember
- Personalized behavior configuration

**Examples:**
- "User prefers Python over JavaScript"
- "User lives in New York timezone"
- "User wants concise responses"

**Characteristics:**
- ✅ Key-based lookup (`get_memory_by_key("timezone")`)
- ✅ Semantic search across memories
- ✅ Confidence scoring
- ✅ Types: profile, preference, fact, constraint, style, context
- ❌ Not for large datasets (use TDB/ADB)
- ❌ No SQL querying

**Tool Pattern:**
```
1. create_memory - Save a preference or fact
2. get_memory_by_key - Retrieve specific memory
3. search_memories - Find related memories
```

**Example Workflow:**
```python
# Save preference
create_memory("User prefers dark mode", "preference", key="theme")

# Retrieve
create_memory("", "preference", key="theme")
# → User prefers dark mode
```

---

### Files - Persisted, Path-Based Access, Not Queryable

**When to use:**
- Generated outputs: reports, summaries, analyses
- Exported data from TDB or VDB queries
- Reference documents: templates, code snippets, config files
- One-off analyses that don't need querying

**Examples:**
- Generated reports: "Weekly Sales Report - 2025-01-19.md"
- Exported data: `export_tdb_table("expenses", "january_expenses.csv")`
- Reference materials: templates, examples
- Code snippets: utility scripts

**Characteristics:**
- ✅ Simple path-based access (read_file, write_file)
- ✅ Human-readable formats (Markdown, CSV, JSON)
- ✅ Best for outputs and reports
- ❌ Not queryable (can't search contents efficiently)
- ❌ No built-in aggregation or filtering

**Tool Pattern:**
```
1. query_tdb or search_vdb - Get data from storage
2. write_file - Save output to file
3. read_file - Load file content later
```

**Scope guidance (important):**
- Default to `scope="context"` for user-owned files.
- Use `scope="shared"` only when the user explicitly asks for shared storage.
- Shared writes require admin privileges; non-admins can read shared files only.

**Example Workflow:**
```python
# User: "Generate a report from my timesheet data"
data = query_tdb("SELECT * FROM timesheets WHERE date >= '2025-01-01'")
report = format_timesheet_report(data)  # Format as markdown
write_file("timesheet_report_january.md", report)
# → File saved, can be read later or shared
```

---

## Decision Tree

```
Task: Store information
│
├─ Is it a user preference or personal fact?
│  └─ YES → Use Memories
│      ✅ "User prefers dark mode", "Timezone: EST"
│      ✅ Key-based lookup with semantic search
│
├─ Is it structured data that needs querying?
│  ├─ YES → Is it complex analytics (window functions, large datasets)?
│  │  ├─ YES → Use ADB (DuckDB analytics)
│  │  │   ✅ Monthly reports, time-series, complex SQL
│  │  │   ✅ Large CSV imports, window functions
│  │  │
│  │  └─ NO → Use TDB (SQLite transactional)
│  │      ✅ Timesheets, expenses, habits, CRM
│  │      ✅ Daily tracking, frequent updates
│  │
│  └─ NO
│     ├─ Is it qualitative knowledge for semantic search?
│     │  ├─ YES → Use VDB (vector semantic search)
│     │  │   ✅ Meeting notes, docs, conversations
│     │  │   ✅ Find by meaning, not exact match
│     │  │
│     │  └─ NO → Use Files (path-based access)
│     │      ✅ Reports, outputs, exports
│     │      ✅ Code, configs, templates
│
Task: Retrieve information
│
├─ Looking for a user preference/fact?
│  └─ YES → Use Memories
│      get_memory_by_key("timezone")
│
├─ Need complex analytics or window functions?
│  └─ YES → Use ADB
│      query_adb("SELECT *, SUM(x) OVER (ORDER BY date) FROM t")
│
├─ Exact match with filtering/aggregation?
│  └─ YES → Use TDB
│      query_tdb("SELECT * FROM expenses WHERE amount > 100")
│
├─ Find by meaning/concept?
│  └─ YES → Use VDB
│      search_vdb("spending patterns", "finances")
│
└─ Know the exact file path?
    └─ YES → Use Files
        read_file("reports/january_summary.md")
```

**Quick Reference:**
| Storage | Best For | Query Method |
|---------|----------|--------------|
| Memories | User preferences, facts | Key lookup, semantic search |
| TDB | Daily tracking, CRUD | SQL (SQLite) |
| ADB | Analytics, complex SQL | SQL (DuckDB) |
| VDB | Documents, semantic search | Vector similarity |
| Files | Reports, exports | Path-based |

---

## Best Practices

### ✅ DO

- **Use Memories for preferences** - User settings, important facts, personalization
- **Use TDB for structured data** - Timesheets, expenses, habits, metrics (daily tracking)
- **Use ADB for analytics** - Complex queries, window functions, large datasets
- **Use VDB for knowledge** - Meeting notes, documentation, conversations (semantic search)
- **Use Files for outputs** - Reports, summaries, exported data
- **Combine storage types** - Query ADB → Export to File, Search VDB → Save to TDB
- **Start with TDB if unsure** - Most flexible for common tasks; migrate to ADB for complex analytics
- **Add metadata to VDB** - Helps with filtering and organization

### ❌ DON'T

- **Don't use Files for data you need to query** - Use TDB or ADB instead
- **Don't use TDB for complex analytics** - Use ADB for window functions, large datasets
- **Don't use ADB for frequent small updates** - Use TDB for daily tracking
- **Don't use TDB/VDB/ADB for user preferences** - Use Memories instead
- **Don't use TDB for semantic search** - Use VDB instead
- **Don't use VDB for exact matching** - Use TDB/ADB instead
- **Don't duplicate storage** - Choose one primary storage per use case
- **Don't forget all storage is persisted** - Nothing is temporary

---

## Workflow Examples

### Example 1: Timesheet Tracking (TDB)

```python
# User: "I want to track my daily work hours"

# Create table with initial data
create_tdb_table(
    "timesheets",
    '[{"date": "2025-01-19", "hours": 4.5, "project": "Executive Assistant", "description": "Skills implementation"}]'
)

# Add more entries
insert_tdb_table(
    "timesheets",
    '[{"date": "2025-01-19", "hours": 3.0, "project": "Executive Assistant", "description": "Documentation"}]'
)

# Query for summary
query_tdb("SELECT project, SUM(hours) as total FROM timesheets GROUP BY project")
# → Executive Assistant: 7.5 hours
```

### Example 2: Meeting Notes (VDB)

```python
# User: "Save notes from today's meeting"

create_vdb_collection(
    "meetings",
    content="Meeting 2025-01-19: Discussed Q1 roadmap. Priorities: 1) Skills system, 2) Tool improvements, 3) Testing. Agreed to implement skills first."
)

# Later: "What did we discuss about priorities?"
search_vdb("priorities", "meetings")
# → Finds meeting, returns discussion about priorities (Skills, Tools, Testing)
```

### Example 3: Report Generation (TDB + Files)

```python
# User: "Generate a weekly expense report"

# Get data from TDB
data = query_tdb("SELECT * FROM expenses WHERE date >= '2025-01-13'")

# Format as report
report = "# Weekly Expense Report\n\n"
report += "| Category | Total |\n|----------|-------|\n"
for row in data:
    report += f"| {row['category']} | ${row['total']} |\n"

# Save to file
write_file("weekly_expense_report.md", report)
```

### Example 4: Knowledge Retrieval (VDB + TDB)

```python
# User: "Find all conversations about testing and save summary"

# Search VDB for relevant conversations
search_vdb("testing quality assurance", "conversations")
# → Returns: conversation_123, conversation_456

# Save summary to TDB
create_tdb_table(
    "testing_notes",
    '[{"date": "2025-01-19", "topic": "Testing", "conversations_found": 2}]'
)

# Export to file for reference
write_file("testing_discussions_summary.md", summary)
```

---

## Common Mistakes

### Mistake 1: Using Files for Queryable Data

❌ **Wrong:**
```python
write_file("expenses.json", '[{"amount": 45.50}, {"amount": 12.00}]')
# Can't easily query: "What's the total?"
```

✅ **Right:**
```python
create_tdb_table("expenses", '[{"amount": 45.50}, {"amount": 12.00}]')
query_tdb("SELECT SUM(amount) FROM expenses")
# → 57.50
```

### Mistake 2: Using TDB for Semantic Search

❌ **Wrong:**
```python
# Trying to find similar meeting notes
query_tdb("SELECT * FROM meetings WHERE notes LIKE '%goals%'")
# → Misses "objectives", "targets", "aims"
```

✅ **Right:**
```python
search_vdb("goals objectives targets", "meetings")
# → Finds all meetings about goals, even if they used different words
```

### Mistake 3: Using VDB for Exact Matching

❌ **Wrong:**
```python
# Trying to find exact expense by ID
search_vdb("expense_12345", "finances")
# → Might return irrelevant results
```

✅ **Right:**
```python
query_tdb("SELECT * FROM expenses WHERE id = 'expense_12345'")
# → Exact match
```

---

## Tool Combinations

### TDB → VDB (Enrichment)

```python
# Get data from TDB
data = query_tdb("SELECT * FROM customers")

# Add to VDB for semantic search
create_vdb_collection("customers", documents=data)
# Now can search: "Find customers interested in AI"
```

### VDB → TDB (Structure)

```python
# Search VDB for relevant info
results = search_vdb("project timeline milestones", "meetings")

# Extract structured data and save to TDB
milestones = extract_milestones(results)
create_tdb_table("milestones", data=milestones)
```

### TDB → Files (Reporting)

```python
# Query TDB for data
data = query_tdb("SELECT * FROM timesheets WHERE date >= '2025-01-01'")

# Generate report
report = generate_report(data)

# Save to file
write_file("monthly_timesheet_report.md", report)
```

---

## Quick Reference

| Task | Use | Tool |
|------|-----|------|
| Track timesheets | TDB | `create_tdb_table` + `insert_tdb_table` |
| Search meeting notes | VDB | `create_vdb_collection` + `search_vdb` |
| Generate report | TDB → Files | `query_tdb` + `write_file` |
| Find similar docs | VDB | `search_vdb` |
| Save conversation | VDB | `create_vdb_collection` |
| Update VDB document | VDB | `update_vdb_document` |
| Export data | TDB → Files | `export_tdb_table` |
| Aggregate metrics | TDB | `query_tdb` with SQL |
| Semantic search | VDB | `search_vdb` |

---

## Summary

**Key Points:**
- All three storage types (TDB, VDB, Files) are **persisted**
- Difference is **how you access/query them**
- TDB: SQL queries for structured data
- VDB: Semantic search for qualitative knowledge
- Files: Path-based access for outputs/reports
- Combine storage types for complex workflows
- Choose based on how you need to **retrieve** the data, not just store it
