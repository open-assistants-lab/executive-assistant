# Information Retrieval

Description: Learn strategies for finding past conversations, documents, and information using search tools and effective organization.

Tags: personal, retrieval, search, information, finding, organization

## Overview

This skill teaches **how to find information quickly** from your stored data. The challenge isn't storing information - it's finding it later when you need it.

**Key Principle:** Good organization during capture enables fast retrieval later.

---

## Retrieval Strategies

### Strategy 1: Exact Match (TDB)

**When:** You know exactly what you're looking for

```python
# Find specific task
query_tdb("SELECT * FROM tasks WHERE title = 'Fix login bug'")

# Find expenses by amount
query_tdb("SELECT * FROM expenses WHERE amount > 100")

# Find timesheets by date
query_tdb("SELECT * FROM timesheets WHERE date = '2025-01-19'")
```

**Use for:** Structured data with specific values

---

### Strategy 2: Semantic Search (VDB)

**When:** You remember the topic/concept but not exact words

```python
# Find meetings about planning
search_vdb("project planning milestones", "meetings")

# Find documentation about authentication
search_vdb("login security authentication", "docs")

# Find notes with similar meaning
search_vdb("obstacles blockers challenges", "journal")
```

**Use for:** Qualitative knowledge, concepts, meanings

---

### Strategy 3: Browse & Filter (Files)

**When:** You know the location but not exact file

```python
# Browse available files
list_files("reports", recursive=True)

# Find files by pattern
glob_files("*.md", "reports/")

# Search file contents
grep_files("summary", "reports/")
```

**Use for:** Files, reports, outputs

---

## Common Retrieval Scenarios

### Scenario 1: Find Past Decision

**"What did we decide about the architecture?"**

```python
# Search VDB for decisions
search_vdb("architecture decision choice", "meetings")

# Search for keywords
grep_files("architecture", "docs/", output_mode="files")

# Check strategy documents
read_file("docs/architecture_decisions.md")
```

### Scenario 2: Find Related Information

**"Show me everything about project X"**

```python
# TDB data
query_tdb("SELECT * FROM timesheets WHERE project = 'Project X'")
query_tdb("SELECT * FROM tasks WHERE project = 'Project X'")

# VDB knowledge
search_vdb("Project X", "all")  # Search all collections

# Files
list_files("projects/project_x/", recursive=True)
grep_files("Project X", "docs/")
```

### Scenario 3: Find Something from Time Period

**"What happened last week?"**

```python
# Time-based queries
query_tdb("SELECT * FROM timesheets WHERE date >= '2025-01-13' AND date < '2025-01-20'")
query_tdb("SELECT * FROM expenses WHERE date >= '2025-01-13' AND date < '2025-01-20'")

# Find files by date
list_files("reports/weekly/", recursive=False)

# Check journals/notes
search_vdb("week progress update", "journal")

# TEMPORAL MEMORY: Query historical states
# What was their location 3 months ago?
get_memory_at_time("location", "2025-10-01T12:00:00Z")

# Show full history of a fact
get_memory_history("job_title")
```

---

## Search Techniques

### VDB Semantic Search

**Natural language queries work best:**
```python
# Good: Descriptive, conceptual
search_vdb("project timeline milestones", "meetings")
search_vdb("budget spending financial", "meetings")
search_vdb("challenges blockers problems", "journal")

# Bad: Exact words only
search_vdb("meeting", "meetings")  # Too generic
```

**Combine with filters:**
```python
# Search specific collection
search_vdb("architecture", "docs")

# Search across all collections
search_vdb("project planning", "")
```

### TDB SQL Queries

**Use WHERE for filtering:**
```python
# Date range
query_tdb("SELECT * FROM tasks WHERE due_date BETWEEN '2025-01-01' AND '2025-01-31'")

# Multiple conditions
query_tdb("SELECT * FROM tasks WHERE priority = 'high' AND status = 'pending'")

# Pattern matching
query_tdb("SELECT * FROM docs WHERE title LIKE '%project%'")
```

**Use aggregation for summaries:**
```python
# Count by category
query_tdb("SELECT category, COUNT(*) as count FROM expenses GROUP BY category")

# Latest item
query_tdb("SELECT * FROM timesheets ORDER BY date DESC LIMIT 1")
```

### File System Search

**Browse by directory:**
```python
# List directory contents
list_files("reports/")
list_files("docs/", recursive=True)

# Check file existence
glob_files("summary_*.md", "reports/")
```

**Search within files:**
```python
# Find files containing text
grep_files("project roadmap", "docs/")

# Show context around match
grep_files("milestone", "docs/", output_mode="content", context_lines=2)
```

---

## Improving Retrieval

### Organization During Capture

**Add metadata:**
```python
# Good: Rich metadata
insert_tdb_table(
    "notes",
    '[{"title": "Architecture decision", "type": "decision", "project": "Executive Assistant", "tags": "technical,important", "date": "2025-01-19"}]'
)

# Easier to find:
query_tdb("SELECT * FROM notes WHERE type = 'decision' AND project = 'Executive Assistant'")
```

**Use consistent naming:**
```python
# Good: Consistent format
write_file("reports/weekly/2025-01-19_summary.md", content)
write_file("reports/weekly/2025-01-26_summary.md", content)

# Easy to find:
glob_files("2025-01-*_summary.md", "reports/weekly/")
```

**Add tags to VDB:**
```python
# Good: Descriptive metadata in documents JSON
create_vdb_collection(
    "decisions",
    documents='[{"content": "Decision notes...", "metadata": {"type": "decision", "project": "Executive Assistant", "category": "technical", "date": "2025-01-19"}}]'
)

# Easy to search:
search_vdb("technical decisions", "decisions")
```

---

## Search Workflow Examples

### Workflow: Find Past Conversation

**"What did we discuss about the budget?"**

1. Search VDB (semantic):
```python
search_vdb("budget spending financial", "meetings")
```

2. Search files:
```python
grep_files("budget", "meetings/")
```

3. Check TDB records:
```python
query_tdb("SELECT * FROM decisions WHERE category = 'budget'")
```

### Workflow: Find Reference Material

**"Where's the API documentation for X?"**

1. Browse docs:
```python
list_files("docs/api/", recursive=True)
```

2. Search for keywords:
```python
grep_files("authentication", "docs/api/")
```

3. Search VDB:
```python
search_vdb("API authentication login", "docs")
```

### Workflow: Find Previous Work

**"How did I solve this problem before?"**

1. Search journal/notes:
```python
search_vdb("problem solution fix workaround", "journal")
```

2. Check commit history (if in git):
```python
# This would be a separate tool, but you could store commit info in TDB
query_tdb("SELECT * FROM commits WHERE message LIKE '%bug fix%'")
```

3. Search documentation:
```python
grep_files("workaround", "docs/")
```

---

## Best Practices

### ✅ DO

- **Add metadata during capture** - Makes retrieval easier
- **Use consistent naming** - Predictable file/table names
- **Tag comprehensively** - Multiple search angles
- **Organize by topic** - Group related information
- **Use semantic search** - Describe concepts, not keywords
- **Check multiple sources** - TDB + VDB + Files
- **Refine searches** - Start broad, narrow down
- **Save successful searches** - Reuse query patterns

### ❌ DON'T

- **Don't rely on memory** - Search instead
- **Don't use vague names** - "note1.md" is useless
- **Don't skip metadata** - Hard to find without it
- **Don't ignore file structure** - Organize logically
- **Don't search too broadly** - Specific queries work better
- **Don't give up after first try** - Try different search terms
- **Don't forget to browse** - Sometimes listing is faster than searching
- **Don't overlook old data** - Archive, don't delete

---

## Quick Reference

**By What You Know:**

| You Know | Use This |
|----------|-----------|
| Exact value | `query_tdb("WHERE field = 'value'")` |
| Date range | `query_tdb("WHERE date BETWEEN X AND Y")` |
| Topic/concept | `search_vdb("topic words", "collection")` |
| File location | `list_files("path/")` |
| File name pattern | `glob_files("pattern", "path/")` |
| Text in files | `grep_files("text", "path/")` |
| General topic | `search_vdb("topic", "")` |
| **Current fact** | `get_memory_by_key("location")` |
| **Historical fact** | `get_memory_at_time("location", "2025-01-01T12:00:00Z")` |
| **Fact history** | `get_memory_history("job_title")` |

**Search Patterns:**
- **Narrow down:** Start broad, add filters
- **Use synonyms:** Try different words
- **Check multiple places:** TDB + VDB + Files
- **Refine queries:** Add WHERE, LIMIT, specific terms

**Common Queries:**
- Latest: `ORDER BY date DESC LIMIT 1`
- Top N: `ORDER BY amount DESC LIMIT 10`
- Count: `SELECT COUNT(*), category GROUP BY category`
- Range: `WHERE date >= 'X' AND date < 'Y'`
- Pattern: `WHERE title LIKE '%keyword%'`

---

## Summary

**Retrieval Strategies:**
1. **Exact match** (TDB) - When you know specifics
2. **Semantic search** (VDB) - When you know concepts
3. **Browse** (Files) - When you know location

**Key Principles:**
- Good organization enables fast retrieval
- Add metadata during capture
- Use semantic search for concepts
- Use SQL queries for exact matches
- Browse file system when location known
- Check multiple sources

**Improve Retrieval:**
- Consistent naming
- Rich metadata
- Good organization
- Tag comprehensively
- Don't skip documentation

**Search Workflow:**
- Start broad
- Narrow down with filters
- Try different search terms
- Check multiple storage types
- Refine and iterate

Information is only useful if you can find it. Organize well during capture.
