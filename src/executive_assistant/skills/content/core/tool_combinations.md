# Tool Combinations

Description: Learn how to combine tools effectively in multi-step workflows.

Tags: core, infrastructure, workflows, patterns, tool-combination

## Overview

This skill teaches **how to combine tools effectively**. Individual tools are powerful, but the real power comes from combining them in workflows.

**Key Principle:** Workflows = Tool Sequences. Learn patterns, not just individual tools.

---

## Tool Selection Guidance

Use the smallest set of tools that can solve the task. Prefer thread‑scoped data.

- **Files:** `write_file`, `read_file`, `list_files`, `create_folder`, `delete_file`, `delete_folder`, `move_file`, `rename_folder`, `glob_files`, `grep_files`
- **TDB (transactional):** `create_tdb_table`, `insert_tdb_table`, `query_tdb`, `list_tdb_tables`, `describe_tdb_table`, `delete_tdb_table`, `add_tdb_column`, `drop_tdb_column`, `import_tdb_table`, `export_tdb_table`
- **VDB (semantic):** `create_vdb_collection`, `add_vdb_documents`, `add_file_to_vdb`, `search_vdb`, `describe_vdb_collection`, `vdb_list`, `update_vdb_document`, `delete_vdb_documents`, `drop_vdb_collection`
- **ADB (analytics / DuckDB):** `list_adb_tables`, `query_adb`
- **Flows / agents:** `create_agent`, `update_agent`, `create_flow`, `run_flow`, `list_flows`, `cancel_flow`, `delete_flow`, `create_flow_project`
- **Web:** `search_web`, `firecrawl_scrape`, `firecrawl_crawl`, `firecrawl_check_status`, `playwright_scrape`
- **OCR:** `ocr_extract_text`, `ocr_extract_structured`, `extract_from_image`
- **Reminders:** `reminder_set`, `reminder_list`, `reminder_edit`, `reminder_cancel`
- **Memory:** `create_memory`, `list_memories`, `update_memory`, `forget_memory`
- **Meta / inventory:** `get_meta`
- **Confirmations:** `confirm_request`

**Scopes**
- Prefer `scope="context"` for user data.
- If the user explicitly asks for shared access, allow `scope="shared"` for reads.
- Shared writes require admin privileges.

**Python**
- If you suggest Python code, verify it with `execute_python`.

---

## Common Workflow Patterns


## Flow Automation (Executor Chains)

Use flows to run multi-step executor chains now or on a schedule.

**Tools:** `create_flow`, `list_flows`, `run_flow`, `cancel_flow`, `delete_flow`

**When to use:** repetitive multi-step automations or scheduled pipelines.

**Guardrail:** Flow agents may not call flow management tools (create/list/run/cancel/delete).

### Pattern 1: Query → Export → Save

**When:** You need to query data and create a report

```python
# Step 1: Query data from TDB
data = query_tdb("""
    SELECT project, SUM(hours) as total_hours
    FROM timesheets
    WHERE date >= '2025-01-01'
    GROUP BY project
""")

# Step 2: Format as report
report = "# Weekly Hours by Project\\n\\n"
report += "| Project | Hours |\\n|---------|-------|\\n"
for row in data:
    report += f"| {row['project']} | {row['total_hours']} |\\n"

# Step 3: Save to file
write_file("reports/weekly_hours_summary.md", report)
```

**Tools Used:** `query_tdb` → `write_file`

---

### Pattern 2: Search → Save → Index

**When:** You find information and want to save it for later retrieval

```python
# Step 1: Search for information
results = search_web("best practices for timesheet tracking")

# Step 2: Save key findings to file
write_file("research/timesheet_best_practices.md", results)

# Step 3: Index in VDB for semantic search
add_file_to_vdb("knowledge", "research/timesheet_best_practices.md")
```

**Tools Used:** `search_web` → `write_file` → `add_file_to_vdb`

---

### Pattern 3: Create → Insert → Query

**When:** Setting up a new tracking system

```python
# Step 1: Create table with initial data
create_tdb_table(
    "expenses",
    '[{"category": "groceries", "amount": 45.50, "date": "2025-01-19"}]'
)

# Step 2: Add more data
insert_tdb_table(
    "expenses",
    '[{"category": "transport", "amount": 12.00, "date": "2025-01-19"}]'
)

# Step 3: Query to verify
query_tdb("SELECT * FROM expenses")
```

**Tools Used:** `create_tdb_table` → `insert_tdb_table` → `query_tdb`

---

### Pattern 4: List → Search → Read

**When:** Finding specific files or information

```python
# Step 1: Browse available files
files = list_files("reports", recursive=True)

# Step 2: Search for specific file
grep_files("summary", "reports/", output_mode="files")

# Step 3: Read the file
read_file("reports/weekly_summary.md")
```

**Tools Used:** `list_files` → `grep_files` → `read_file`

---

### Pattern 5: Collect → Analyze → Report

**When:** Data analysis and reporting

```python
# Step 1: Collect data from multiple sources
timesheets = query_tdb("SELECT * FROM timesheets WHERE date >= '2025-01-01'")
expenses = query_tdb("SELECT * FROM expenses WHERE date >= '2025-01-01'")

# Step 2: Analyze with Python
analysis = execute_python("""
import pandas as pd
timesheet_df = pd.DataFrame(timesheets)
expense_df = pd.DataFrame(expenses)
# ... analysis code ...
""")

# Step 3: Generate report
write_file("reports/january_analysis.md", analysis)
```

**Python sandbox libraries:** json, csv, pathlib, pypdf, fitz (PyMuPDF), docx (python-docx), pptx (python-pptx), openpyxl, markdown_it, bs4 (BeautifulSoup), lxml, html5lib, PIL (Pillow), reportlab, dateparser, dateutil, urllib.*

**Tools Used:** `query_tdb` → `execute_python` → `write_file`

---

## Multi-Storage Workflows

### Workflow 1: TDB → VDB → File

**Use Case:** Comprehensive reporting with context

```python
# 1. Query structured data from TDB
data = query_tdb("SELECT * FROM projects WHERE status = 'active'")

# 2. Get related documents from VDB
docs = search_vdb("project planning milestones", "project_docs")

# 3. Combine into report
report = f"# Active Projects Report\\n\\n## Projects\\n{data}\\n\\n## Related Documentation\\n{docs}"

# 4. Save report
write_file("reports/active_projects_with_context.md", report)
```

**Why this works:**
- TDB provides structured, queryable data
- VDB provides qualitative context and related info
- File preserves the combined output

---

### Workflow 2: File → TDB → Query

**Use Case:** Importing and analyzing external data

```python
# 1. Read CSV file
csv_data = read_file("data/sales_2025.csv")

# 2. Import into TDB
import_tdb_table("sales", "sales_2025.csv")

# 3. Query and analyze
query_tdb("""
    SELECT
        strftime('%Y-%m', date) as month,
        SUM(amount) as total
    FROM sales
    GROUP BY month
""")
```

**Why this works:**
- File provides import format
- TDB enables querying and aggregation
- Query produces insights

---

### Workflow 3: VDB → TDB → Export

**Use Case:** Extracting structure from unstructured data

```python
# 1. Search VDB for relevant information
meetings = search_vdb("budget planning financial", "meetings")

# 2. Extract structured data and save to TDB
budget_items = extract_from_text(meetings)  # Parse meeting notes
create_tdb_table("budget_items", data=budget_items)

# 3. Query and export
query_tdb("SELECT * FROM budget_items WHERE amount > 1000")
export_tdb_table("budget_items", "budget_over_1000.csv")
```

**Why this works:**
- VDB finds relevant qualitative info
- TDB structures it for analysis
- Export enables sharing

---

## Common Task Workflows

### Workflow: Daily Planning

```python
# 1. Check today's schedule
reminders = reminder_list(status="pending")

# 2. Review previous progress
yesterday = query_tdb("""
    SELECT * FROM daily_log
    WHERE date = '2025-01-18'
""")

# 3. Plan today's tasks
create_tdb_table(
    "today_tasks",
    '[{"task": "Review PR", "priority": "high", "estimated_hours": 1}]'
)

# 4. Set reminders for deadlines
reminder_set("Code review due at 3pm", "today 3pm")
```

**Tools:** `reminder_list` → `query_tdb` → `create_tdb_table` → `reminder_set`

---

### Workflow: Weekly Review

```python
# 1. Get week's timesheets
timesheets = query_tdb("""
    SELECT project, SUM(hours) as total
    FROM timesheets
    WHERE date >= '2025-01-13'
    GROUP BY project
""")

# 2. Get week's expenses
expenses = query_tdb("""
    SELECT category, SUM(amount) as total
    FROM expenses
    WHERE date >= '2025-01-13'
    GROUP BY category
""")

# 3. Find related notes
notes = search_vdb("weekly progress accomplishments", "journal")

# 4. Generate weekly report
report = f"# Weekly Review\\n\\n## Time Distribution\\n{timesheets}\\n\\n## Spending\\n{expenses}\\n\\n## Notes\\n{notes}"
write_file(f"reports/weekly_review_{date.today()}.md", report)
```

**Tools:** `query_tdb` → `search_vdb` → `write_file`

---

### Workflow: Research & Note-Taking

```python
# 1. Search for information
web_results = search_web("LangGraph subgraphs tutorial")
# If the site is heavily JS-rendered or results are thin, fall back to:
# web_results = playwright_scrape("https://example.com/tutorial", wait_for_selector="article")

# 2. Save to file for reference
write_file("research/langgraph_subgraphs.md", web_results)

# 3. Extract key points
key_points = execute_python("""
# Extract main concepts from research
import re
content = open('research/langgraph_subgraphs.md').read()
# ... extract key points ...
""")

# 4. Save to VDB for semantic search
create_vdb_collection(
    "research",
    content=key_points,
    metadata={"topic": "langgraph", "type": "tutorial", "date": "2025-01-19"}
)
```

**Tools:** `search_web` → `write_file` → `execute_python` → `create_vdb_collection`

---

## Error Handling Workflows

### Pattern: Validate → Transform → Load

```python
# 1. Read and validate file
try:
    data = read_file("data/import.csv")
    # Validate format
    if not validate_csv(data):
        return "Error: Invalid CSV format"
except FileNotFoundError:
    return "Error: File not found"

# 2. Transform data if needed
transformed = transform_data(data)

# 3. Load into TDB
try:
    import_tdb_table("imported_data", "data/import.csv")
except Exception as e:
    return f"Error importing: {e}"
```

---

## Optimization Workflows

### Pattern: Batch Operations

```python
# Instead of multiple single inserts:
# insert_tdb_table("tasks", '[{"task": "A"}]')
# insert_tdb_table("tasks", '[{"task": "B"}]')

# Batch insert:
insert_tdb_table("tasks", '[{"task": "A"}, {"task": "B"}, {"task": "C"}]')
```

### Pattern: Query → Cache → Reuse

```python
# 1. Query once and cache
weekly_data = query_tdb("SELECT * FROM metrics WHERE week = '2025-03'")
write_file("cache/week_3_metrics.json", weekly_data)

# 2. Reuse from cache
cached = read_file("cache/week_3_metrics.json")

# 3. Update cache when needed
# Only re-query if data changed
```

---

## Tool Combination Matrix

| Starting Point | Common Next Steps | Purpose |
|----------------|-------------------|---------|
| `create_tdb_table` | `insert_tdb_table` → `query_tdb` | Set up tracking |
| `query_tdb` | `write_file` or `execute_python` | Report/analyze |
| `search_web` | `write_file` → `add_file_to_vdb` | Research/save |
| `search_vdb` | `read_file` or `query_tdb` | Find context |
| `list_files` | `grep_files` → `read_file` | Browse/find/read |
| `create_vdb_collection` | `search_vdb` | Store/search |
| `reminder_set` | `reminder_list` | Schedule/manage |
| `read_file` | `create_vdb_collection` or `create_tdb_table` | Import/index |

---

## Best Practices

### ✅ DO

- **Plan your workflow** - Know all steps before starting
- **Validate early** - Check data quality after each step
- **Use intermediate storage** - Cache results for reuse
- **Handle errors gracefully** - Try/except at each step
- **Document your workflows** - Save successful patterns
- **Test with small data** - Validate before scaling up
- **Optimize bottlenecks** - Profile before optimizing

### ❌ DON'T

- **Don't skip validation** - Check data quality early
- **Don't mix storage types** - Stay consistent per workflow
- **Don't repeat queries** - Cache and reuse results
- **Don't ignore errors** - Handle failures at each step
- **Don't over-optimize** - Simple workflows beat complex ones
- **Don't forget cleanup** - Delete temporary data
- **Don't hardcode paths** - Use relative paths and variables

---

## Quick Reference

**Common Workflows:**
- **Report:** Query → Format → Write File
- **Research:** Search → Save → Index → Search
- **Import:** Read File → Validate → Import TDB → Query
- **Analysis:** Query → Python → Chart → Export
- **Backup:** Export TDB → Write File → Archive
- **Review:** Query Multiple → Combine → Report → Save

**Multi-Storage:**
- **TDB + File:** Query → Export → Share
- **VDB + TDB:** Search → Extract → Structure → Query
- **TDB + VDB:** Query → Find Context → Combine → Report
- **File + VDB:** Read → Index → Search → Retrieve

---

## Summary

**Key Patterns:**
1. **Query → Export → Save** - Reporting workflow
2. **Search → Save → Index** - Research workflow
3. **Create → Insert → Query** - Setup workflow
4. **Collect → Analyze → Report** - Analysis workflow

**Workflow Principles:**
- Plan before executing
- Validate at each step
- Cache intermediate results
- Handle errors gracefully
- Document successful patterns
- Test with small data first

**Tool Combinations:**
- Workflows combine 3-5 tools
- Each tool has a specific role
- Order matters in sequences
- Storage type choice is critical

Learn these patterns and you can accomplish complex tasks efficiently.


## Flows
For scheduled or multi-step execution, use the `flows` skill (see flows.md).
