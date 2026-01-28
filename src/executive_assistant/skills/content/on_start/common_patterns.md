# Common Workflow Patterns

Description: Essential patterns for combining tools effectively

Tags: core, patterns, workflows, examples

## Pattern 1: Query → Analyze → Report

```python
# 1. Get data
data = query_tdb("SELECT * FROM expenses WHERE date >= '2025-01-01'")

# 2. Analyze with Python
analysis = execute_python("""
import pandas as pd
df = pd.DataFrame(expenses)
print(f"Total: ${df['amount'].sum():.2f}")
print(f"Average: ${df['amount'].mean():.2f}")
""")

# 3. Save report
write_file("expense_report.md", "# Expense Report\n\n" + analysis)
```

## Pattern 2: Search → Save → Index

```python
# 1. Search web
results = search_web("best practices for API design")

# 2. Save to file
write_file("research/api_design.md", results)

# 3. Index in VDB for later retrieval
add_file_to_vdb("knowledge", "research/api_design.md")
```

## Pattern 3: Import → Transform → Export

```python
# 1. Import CSV to ADB
import_adb_csv("raw_data.csv", table_name="data")

# 2. Transform with SQL
query_adb("""
    CREATE TABLE clean_data AS
    SELECT 
        date,
        TRIM(category) as category,
        CAST(amount as DECIMAL) as amount
    FROM data
    WHERE amount > 0
""")

# 3. Export results
export_adb_table("clean_data", "clean_data.csv")
```

## Pattern 4: Schedule with Flows

```python
# 1. Create specialized agent
create_agent(
    agent_id="reporter",
    name="Daily Reporter",
    description="Generate daily summary",
    tools=["query_tdb", "write_file"],
    system_prompt="Query timesheets and write summary to file"
)

# 2. Create recurring flow
create_flow(
    name="daily_report",
    description="Generate daily report at 9am",
    agent_ids=["reporter"],
    schedule_type="recurring",
    cron_expression="0 9 * * *",
    flow_input={"date": "today"}
)
```

## Pattern 5: Remember User Preferences

```python
# Store preference
create_memory("User prefers concise responses", "preference", key="style")

# Later, retrieve it
get_memory_by_key("style")
# → User prefers concise responses
```

## Quick Tool Combinations

| Goal | Tools |
|------|-------|
| Track & analyze | `create_tdb_table` → `insert_tdb_table` → `query_tdb` |
| Research & save | `search_web` → `write_file` → `add_vdb_documents` |
| Report generation | `query_tdb`/`query_adb` → `execute_python` → `write_file` |
| Data pipeline | `import_adb_csv` → `query_adb` → `export_adb_table` |
| Automation | `create_agent` → `create_flow` → `run_flow` |

## Data Format Notes

**For `create_tdb_table`, `insert_tdb_table`, `create_adb_table`:**
- Use **Python list** (easier): `[{"name": "Alice", "age": 30}]`
- Or **JSON string**: `'[{"name": "Alice", "age": 30}]'`
- Both work! Example:
  ```python
  create_tdb_table("users", data=[{"name": "Alice", "age": 30}])
  insert_tdb_table("users", data=[{"name": "Bob", "age": 25}])
  create_adb_table("sales", data=[{"id": 1, "amount": 100}])
  ```

## Anti-Patterns (Avoid)

❌ **Don't**: Store queryable data in Files
```python
# Wrong
write_file("expenses.json", '[{"amount": 50}]')  # Can't query this

# Right
create_tdb_table("expenses", '[{"amount": 50}]')  # Can query with SQL
```

❌ **Don't**: Use TDB for semantic search
```python
# Wrong
query_tdb("SELECT * FROM notes WHERE content LIKE '%goals%'")  # Misses context

# Right
search_vdb("Q1 goals and objectives", "meetings")  # Finds by meaning
```

❌ **Don't**: Store preferences in TDB/VDB
```python
# Wrong
create_tdb_table("preferences", '[{"key": "theme", "value": "dark"}]')

# Right
create_memory("Prefers dark mode", "preference", key="theme")
```

## Load More Patterns

For detailed workflows: `load_skill("workflows")` or `load_skill("tool_combinations")`
