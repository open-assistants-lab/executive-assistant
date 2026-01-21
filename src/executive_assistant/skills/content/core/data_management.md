# Data Management

Description: Learn to choose the right storage (DB, VS, Files) for your task and access it efficiently.

Tags: core, infrastructure, storage, db, vs, files

## Overview

This skill teaches you how to choose between Database (DB), Vector Store (VS), and Files for storing and retrieving information. All three are **persisted** storage - the difference is **how you query/access them**.

---

## Storage Decision Framework

### Database (DB) - Persisted, SQL-Queryable, Structured

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
1. create_db_table - Define schema (or infer from data)
2. insert_db_table - Add data
3. query_db - Retrieve with SQL queries
```

**Example Workflow:**
```python
# User: "Track my daily expenses"
create_db_table("expenses", '[{"category": "groceries", "amount": 45.50, "date": "2025-01-19"}]')
insert_db_table("expenses", '[{"category": "transport", "amount": 12.00, "date": "2025-01-19"}]')
query_db("SELECT category, SUM(amount) as total FROM expenses GROUP BY category")
# → Shows spending by category
```

---

### Vector Store (VS) - Persisted, Semantic Search, Qualitative

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
1. create_vs_collection - Create collection (optional: add initial content)
2. add_vs_documents - Add more documents
3. search_vs - Semantic search by meaning
```

**Example Workflow:**
```python
# User: "Save our meeting notes for later"
create_vs_collection("meetings", content="Discussed Q1 goals: increase user engagement by 20%")

# Later: "What did we decide about goals?"
search_vs("goals", "meetings")
# → Finds meeting about Q1 goals even if you search for "objectives" or "targets"
```

---

### Files - Persisted, Path-Based Access, Not Queryable

**When to use:**
- Generated outputs: reports, summaries, analyses
- Exported data from DB or VS queries
- Reference documents: templates, code snippets, config files
- One-off analyses that don't need querying

**Examples:**
- Generated reports: "Weekly Sales Report - 2025-01-19.md"
- Exported data: `export_db_table("expenses", "january_expenses.csv")`
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
1. query_db or search_vs - Get data from storage
2. write_file - Save output to file
3. read_file - Load file content later
```

**Example Workflow:**
```python
# User: "Generate a report from my timesheet data"
data = query_db("SELECT * FROM timesheets WHERE date >= '2025-01-01'")
report = format_timesheet_report(data)  # Format as markdown
write_file("timesheet_report_january.md", report)
# → File saved, can be read later or shared
```

---

## Decision Tree

```
Task: Store information
│
├─ Is it structured data that needs querying?
│  ├─ YES → Use DB (persisted, SQL-queryable)
│  │   ✅ Timesheets, expenses, habits, CRM data
│  │   ✅ Need: filter, sort, group, aggregate
│  │
│  └─ NO
│     ├─ Is it qualitative knowledge for semantic search?
│     │  ├─ YES → Use VS (persisted, semantic search)
│     │  │   ✅ Meeting notes, docs, conversations
│     │  │   ✅ Need: find by meaning/concept
│     │  │
│     │  └─ NO → Use Files (persisted, path-based access)
│         ✅ Reports, outputs, exports
│         ✅ Need: save formatted content
│
Task: Retrieve information
│
├─ Exact match with filtering/aggregation?
│  └─ YES → Use DB queries
│      query_db("SELECT * FROM expenses WHERE amount > 100")
│
├─ Find by meaning/concept?
│  └─ YES → Use VS search
│      search_vs("spending patterns", "finances")
│
└─ Know the exact file path?
    └─ YES → Use Files
        read_file("reports/january_summary.md")
```

---

## Best Practices

### ✅ DO

- **Use DB for structured data** - Timesheets, expenses, habits, metrics
- **Use VS for knowledge** - Meeting notes, documentation, conversations
- **Use Files for outputs** - Reports, summaries, exported data
- **Combine storage types** - Query DB → Export to File, Search VS → Save to DB
- **Start with DB if unsure** - Most flexible for common tasks
- **Add metadata to VS** - Helps with filtering and organization

### ❌ DON'T

- **Don't use Files for data you need to query** - Use DB instead
- **Don't use DB for semantic search** - Use VS instead
- **Don't use VS for exact matching** - Use DB instead
- **Don't duplicate storage** - Choose one primary storage per use case
- **Don't forget all storage is persisted** - Nothing is temporary

---

## Workflow Examples

### Example 1: Timesheet Tracking (DB)

```python
# User: "I want to track my daily work hours"

# Create table with initial data
create_db_table(
    "timesheets",
    '[{"date": "2025-01-19", "hours": 4.5, "project": "Executive Assistant", "description": "Skills implementation"}]'
)

# Add more entries
insert_db_table(
    "timesheets",
    '[{"date": "2025-01-19", "hours": 3.0, "project": "Executive Assistant", "description": "Documentation"}]'
)

# Query for summary
query_db("SELECT project, SUM(hours) as total FROM timesheets GROUP BY project")
# → Executive Assistant: 7.5 hours
```

### Example 2: Meeting Notes (VS)

```python
# User: "Save notes from today's meeting"

create_vs_collection(
    "meetings",
    content="Meeting 2025-01-19: Discussed Q1 roadmap. Priorities: 1) Skills system, 2) Tool improvements, 3) Testing. Agreed to implement skills first."
)

# Later: "What did we discuss about priorities?"
search_vs("priorities", "meetings")
# → Finds meeting, returns discussion about priorities (Skills, Tools, Testing)
```

### Example 3: Report Generation (DB + Files)

```python
# User: "Generate a weekly expense report"

# Get data from DB
data = query_db("SELECT * FROM expenses WHERE date >= '2025-01-13'")

# Format as report
report = "# Weekly Expense Report\n\n"
report += "| Category | Total |\n|----------|-------|\n"
for row in data:
    report += f"| {row['category']} | ${row['total']} |\n"

# Save to file
write_file("weekly_expense_report.md", report)
```

### Example 4: Knowledge Retrieval (VS + DB)

```python
# User: "Find all conversations about testing and save summary"

# Search VS for relevant conversations
search_vs("testing quality assurance", "conversations")
# → Returns: conversation_123, conversation_456

# Save summary to DB
create_db_table(
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
create_db_table("expenses", '[{"amount": 45.50}, {"amount": 12.00}]')
query_db("SELECT SUM(amount) FROM expenses")
# → 57.50
```

### Mistake 2: Using DB for Semantic Search

❌ **Wrong:**
```python
# Trying to find similar meeting notes
query_db("SELECT * FROM meetings WHERE notes LIKE '%goals%'")
# → Misses "objectives", "targets", "aims"
```

✅ **Right:**
```python
search_vs("goals objectives targets", "meetings")
# → Finds all meetings about goals, even if they used different words
```

### Mistake 3: Using VS for Exact Matching

❌ **Wrong:**
```python
# Trying to find exact expense by ID
search_vs("expense_12345", "finances")
# → Might return irrelevant results
```

✅ **Right:**
```python
query_db("SELECT * FROM expenses WHERE id = 'expense_12345'")
# → Exact match
```

---

## Tool Combinations

### DB → VS (Enrichment)

```python
# Get data from DB
data = query_db("SELECT * FROM customers")

# Add to VS for semantic search
create_vs_collection("customers", documents=data)
# Now can search: "Find customers interested in AI"
```

### VS → DB (Structure)

```python
# Search VS for relevant info
results = search_vs("project timeline milestones", "meetings")

# Extract structured data and save to DB
milestones = extract_milestones(results)
create_db_table("milestones", data=milestones)
```

### DB → Files (Reporting)

```python
# Query DB for data
data = query_db("SELECT * FROM timesheets WHERE date >= '2025-01-01'")

# Generate report
report = generate_report(data)

# Save to file
write_file("monthly_timesheet_report.md", report)
```

---

## Quick Reference

| Task | Use | Tool |
|------|-----|------|
| Track timesheets | DB | `create_db_table` + `insert_db_table` |
| Search meeting notes | VS | `create_vs_collection` + `search_vs` |
| Generate report | DB → Files | `query_db` + `write_file` |
| Find similar docs | VS | `search_vs` |
| Save conversation | VS | `create_vs_collection` |
| Export data | DB → Files | `export_db_table` |
| Aggregate metrics | DB | `query_db` with SQL |
| Semantic search | VS | `search_vs` |

---

## Summary

**Key Points:**
- All three storage types (DB, VS, Files) are **persisted**
- Difference is **how you access/query them**
- DB: SQL queries for structured data
- VS: Semantic search for qualitative knowledge
- Files: Path-based access for outputs/reports
- Combine storage types for complex workflows
- Choose based on how you need to **retrieve** the data, not just store it
