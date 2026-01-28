# Record Keeping

Description: Learn the information lifecycle: how to capture information effectively, organize it for retrieval, and maintain it over time.

Tags: core, infrastructure, information, lifecycle, organization

## Overview

This skill teaches you the **information lifecycle**: Record → Organize → Retrieve. Most people are good at recording information but struggle with organizing and retrieving it effectively. This skill ensures information remains accessible and useful.

---

## The Information Lifecycle

```
┌─────────────────────────────────────────────────────────────┐
│                    Information Lifecycle                      │
│                                                               │
│  ┌─────────┐    ┌────────────┐    ┌──────────────┐         │
│  │ Record  │───▶│  Organize  │───▶│   Retrieve    │         │
│  └─────────┘    └────────────┘    └──────────────┘         │
│       │              │                  │                  │
│       ▼              ▼                  ▼                  │
│  Capture       Structure        Search & Find              │
│  Store         Tag/Metadata     Access & Use               │
│  Validate      Relationship     Update & Refresh            │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

**Key Principle:** Information that can't be found doesn't exist. Invest time in organization during capture.

---

## Phase 1: Record (Capture)

**When Recording Information:**
1. **Be comprehensive** - Capture all relevant details
2. **Be structured** - Use consistent format from the start
3. **Add metadata** - Tag, categorize, timestamp during capture
4. **Choose right storage** - TDB (structured), VDB (searchable), Files (outputs)

### Recording Patterns

**Structured Data (Use TDB):**
```python
# User: "Track my daily work"
create_tdb_table(
    "daily_log",
    columns="date,project,hours,description,tags"
)
insert_tdb_table(
    "daily_log",
    '[{"date": "2025-01-19", "project": "Executive Assistant", "hours": 4, "description": "Skills system", "tags": "development"}]'
)
```

**Qualitative Notes (Use VDB):**
```python
# User: "Save notes from today's meeting"
create_vdb_collection(
    "meetings",
    content="Meeting 2025-01-19 with engineering team. Discussed Q1 roadmap. Key decisions: 1) Prioritize skills system, 2) Defer email channel, 3) Focus on testing."
)
```

**Reference Material (Use Files):**
```python
# User: "Save this project plan"
write_file("project_plan_q1.md", plan_content)
```

### Metadata Strategies

**Always Capture:**
- **When:** Date/time, timestamp
- **What:** Category, type, tags
- **Who:** Author, owner, related parties
- **Why:** Purpose, context, keywords

**Example Metadata:**
```python
# TDB with metadata
create_tdb_table(
    "tasks",
    '[{"title": "Fix bug", "priority": "high", "tags": "bug,urgent", "created": "2025-01-19"}]'
)

# VDB with metadata
create_vdb_collection(
    "docs",
    documents='[{"content": "...", "metadata": {"type": "meeting", "date": "2025-01-19", "attendees": ["team"]}}]'
)
```

---

## Phase 2: Organize (Structure)

**Organization Principles:**
1. **Group related items** - Collections, categories, tags
2. **Create hierarchies** - Parent/child relationships
3. **Add connections** - Cross-references, links
4. **Maintain consistency** - Use same structure over time

### Organization by Storage Type

**TDB Organization:**
- Use separate tables for different entities
- Add indexes on frequently queried columns
- Use consistent column naming (created_at, updated_at)
- Add foreign key relationships

```python
# Good: Organized with metadata
create_tdb_table(
    "tasks",
    columns="id,title,status,priority,created_at,updated_at,tags"
)

# Query by status
query_tdb("SELECT * FROM tasks WHERE status = 'pending' ORDER BY priority DESC")
```

**VDB Organization:**
- Use separate collections for different topics
- Add descriptive metadata to documents
- Use consistent tagging schemes
- Consider chunk size for long documents

```python
# Good: Organized by topic with metadata in documents JSON
create_vdb_collection(
    "meetings", 
    documents='[{"content": "Meeting notes...", "metadata": {"type": "meeting", "date": "2025-01-19"}}]'
)
create_vdb_collection(
    "docs",
    documents='[{"content": "API documentation...", "metadata": {"category": "technical"}}]'
)

# Search by topic
search_vdb("project planning", "meetings")
```

**Files Organization:**
- Use clear directory structure
- Consistent naming conventions
- Separate outputs from inputs
- Version control for important documents

```python
# Good: Organized structure
write_file("reports/weekly/2025-01-19_summary.md", content)
write_file("exports/data/expenses_january.csv", data)
write_file("docs/reference/api_guide.md", guide)
```

### Tagging Strategies

**Hierarchical Tags:**
```
work/
  ├── project/
  │   ├── executive_assistant
  │   └── website
  └── task/
      ├── development
      └── review

personal/
  ├── finance/
  └── health/
```

**Flat Tags with Search:**
```
#project-executive_assistant
#task-development
#priority-high
#week-3
```

---

## Phase 3: Retrieve (Find & Use)

**Retrieval Strategies:**
1. **Know what you're looking for** - Structured query (TDB)
2. **Explore by meaning** - Semantic search (VDB)
3. **Browse by location** - File system navigation (Files)

### Retrieval Patterns

**Exact Match Retrieval (TDB):**
```python
# User: "What did I work on last week?"
query_tdb("""
    SELECT project, SUM(hours) as total
    FROM daily_log
    WHERE date >= '2025-01-13'
    GROUP BY project
""")

# User: "Show high-priority tasks"
query_tdb("SELECT * FROM tasks WHERE priority = 'high' AND status = 'pending'")
```

**Semantic Retrieval (VDB):**
```python
# User: "What did we decide about the roadmap?"
search_vdb("roadmap decisions priorities", "meetings")
# → Finds meetings about roadmap, even if they used "objectives" or "plans"

# User: "Find documentation about authentication"
search_vdb("authentication login security", "docs")
```

**File Retrieval (Files):**
```python
# User: "Show last week's report"
read_file("reports/weekly/2025-01-13_summary.md")

# Browse available reports
list_files("reports/weekly", recursive=False)
```

---

## Best Practices

### ✅ DO

- **Add metadata during capture** - Don't retroactively organize
- **Choose storage based on retrieval needs** - How will you find this later?
- **Use consistent naming** - Same format every time
- **Tag comprehensively** - Better to over-tag than under-tag
- **Create hierarchies** - Group related items
- **Archive old data** - Move to separate storage, don't delete
- **Backup important data** - Export TDB tables regularly
- **Review and clean up** - Monthly audit of outdated information

### ❌ DON'T

- **Don't delay organization** - Organize during capture, not later
- **Don't mix storage types** - Keep TDB for structured, VDB for semantic
- **Don't create too many collections** - 5-10 is better than 50+
- **Don't use vague tags** - Use specific, searchable terms
- **Don't duplicate storage** - One source of truth per item
- **Don't ignore old data** - Archive or migrate, don't abandon
- **Don't skip validation** - Check data quality during capture
- **Don't forget relationships** - Link related items together

---

## Workflow Examples

### Example 1: Daily Journaling

**Record:**
```python
# Create daily log table
create_tdb_table(
    "daily_log",
    columns="date,mood,productivity,highlights,challenges,gratitude"
)

# Add entry
insert_tdb_table(
    "daily_log",
    '[{"date": "2025-01-19", "mood": "good", "productivity": 8, "highlights": "Finished skills", "challenges": "Testing", "gratitude": "Team support"}]'
)
```

**Organize:**
```python
# Query by mood
query_tdb("SELECT AVG(productivity) as avg_productivity FROM daily_log WHERE mood = 'good'")

# Find patterns
query_tdb("SELECT date, highlights FROM daily_log WHERE productivity >= 8")
```

**Retrieve:**
```python
# Review last week
query_tdb("SELECT * FROM daily_log WHERE date >= '2025-01-13' ORDER BY date DESC")
```

### Example 2: Meeting Notes

**Record:**
```python
# Save to VDB for semantic search
create_vdb_collection(
    "meetings",
    content="Weekly sync 2025-01-19: Progress update on skills system. Completed infrastructure. Next: Create remaining skills. Blocker: Need to test with Executive Assistant.",
    metadata={"type": "weekly", "date": "2025-01-19", "attendees": 5}
)
```

**Organize:**
```python
# Search by topic
search_vdb("progress blockers", "meetings")

# List all meetings
vdb_list()
```

**Retrieve:**
```python
# Find weekly syncs
describe_vdb_collection("meetings")
```

### Example 3: Project Documentation

**Record:**
```python
# Save architecture decisions (Files)
write_file(
    "docs/architecture/skills_system.md",
    "# Skills System Architecture\n\n## Components\n- SkillsRegistry\n- load_skill tool\n..."
)
```

**Organize:**
```python
# Create index
write_file(
    "docs/index.md",
    "# Documentation Index\n\n- [Architecture](architecture/skills_system.md)\n- [API Reference](api/README.md)"
)
```

**Retrieve:**
```python
# Browse docs
list_files("docs", recursive=True)
```

---

## Common Mistakes

### Mistake 1: Recording Without Organization

❌ **Wrong:**
```python
# Just dump data
insert_tdb_table("notes", '[{"content": "Meeting notes..."}, {"content": "Random thought..."}]')
# Can't find anything later
```

✅ **Right:**
```python
# Structure with metadata
insert_tdb_table(
    "notes",
    '[{"type": "meeting", "date": "2025-01-19", "content": "...", "tags": "work,project"}]'
)
query_tdb("SELECT * FROM notes WHERE type = 'meeting'")
```

### Mistake 2: Using Wrong Storage Type

❌ **Wrong:**
```python
# Storing structured data in files
write_file("tasks.json", '[{"task": "fix bug"}, {"task": "write docs"}]')
# Can't query efficiently
```

✅ **Right:**
```python
# Use TDB for structured data
create_tdb_table("tasks", columns="title,status,priority")
query_tdb("SELECT * FROM tasks WHERE status = 'pending'")
```

### Mistake 3: No Metadata Strategy

❌ **Wrong:**
```python
# Minimal capture
create_vdb_collection("notes", content="Discussed project")
# Hard to find later
```

✅ **Right:**
```python
# Rich metadata
create_vdb_collection(
    "notes",
    content="Discussed project roadmap and milestones",
    metadata={"type": "meeting", "project": "executive_assistant", "date": "2025-01-19"}
)
search_vdb("roadmap", "notes")
```

---

## Maintenance & Hygiene

**Weekly Tasks:**
- Review new information from past week
- Organize into proper structure
- Add missing metadata
- Archive completed items

**Monthly Tasks:**
- Audit all storage locations
- Clean up outdated data
- Reorganize if structure changed
- Export backups of important data

**Quarterly Tasks:**
- Review entire information architecture
- Merge duplicate collections
- Update tagging scheme
- Archive old data to separate storage

---

## Quick Reference

| Information Type | Storage | Organize By | Retrieve With |
|------------------|---------|-------------|---------------|
| Timesheets | TDB | Date, Project | query_tdb (filter/thread) |
| Meeting notes | VDB | Topic, Date | search_vdb (semantic) |
| Tasks | TDB | Status, Priority | query_tdb (WHERE/ORDER) |
| Documentation | VDB/Files | Category, Type | search_vdb / list_files |
| Reports | Files | Date, Type | list_files / read_file |
| References | VDB | Topic, Keywords | search_vdb (semantic) |
| Contacts | TDB | Name, Company | query_tdb (LIKE) |
| Ideas | VDB | Topic, Tags | search_vdb (concepts) |

---

## Summary

**Key Principles:**
1. **Record** with metadata and structure from the start
2. **Organize** during capture, not retroactively
3. **Retrieve** using the right tool for your need
4. **Maintain** with regular hygiene and cleanup

**The Lifecycle:**
- Record comprehensively with metadata
- Organize by relationships and hierarchies
- Retrieve using TDB (exact), VDB (semantic), or Files (browse)
- Maintain through regular cleanup and archival

**Storage Selection:**
- **TDB** for structured, queryable data
- **VDB** for qualitative, searchable knowledge
- **Files** for outputs and references

Information that can't be retrieved doesn't exist. Invest in organization during capture.
