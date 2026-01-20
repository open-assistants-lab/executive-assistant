# Executive Assistant Tool Inventory - 2025-01-20

## Overview

Executive Assistant has **51 tools** organized into categories. All storage tools (DB, File, VS) now support the unified `scope="context"|"shared"` parameter.

## Storage Tools (26 tools with scope parameter)

### Database Tools (8 tools) - `src/executive_assistant/storage/db_tools.py`

All DB tools support `scope="context"|"shared"`:
- `scope="context"` (default): Uses group_id/thread_id storage at `data/groups/{group_id}/db/` or `data/users/{thread_id}/db/`
- `scope="shared"`: Uses organization-wide storage at `data/shared/db/`

| Tool | Description | Scope Support |
|------|-------------|---------------|
| `create_db_table` | Create a new table for structured data storage | ✅ |
| `insert_db_table` | Add rows to an existing table | ✅ |
| `query_db` | Execute SQL queries to retrieve, analyze, or modify data | ✅ |
| `list_db_tables` | List all tables in the database | ✅ |
| `describe_db_table` | Get table schema (column names and types) | ✅ |
| `delete_db_table` | Delete a table and all its data | ✅ |
| `export_db_table` | Export table data to a CSV file | ✅ |
| `import_db_table` | Import CSV file data into a new table | ✅ |

### File Tools (10 tools) - `src/executive_assistant/storage/file_sandbox.py`

All file tools support `scope="context"|"shared"`:
- `scope="context"` (default): Uses group_id/thread_id storage at `data/groups/{group_id}/files/` or `data/users/{thread_id}/files/`
- `scope="shared"`: Uses organization-wide storage at `data/shared/files/`

| Tool | Description | Scope Support |
|------|-------------|---------------|
| `read_file` | Read file contents as text | ✅ |
| `write_file` | Write content to a file (creates or overwrites) | ✅ |
| `list_files` | Browse directory structure (file/folder names only) | ✅ |
| `create_folder` | Create a new folder in the files directory | ✅ |
| `delete_folder` | Delete a folder and all its contents | ✅ |
| `rename_folder` | Rename or move a folder | ✅ |
| `move_file` | Move or rename a file | ✅ |
| `glob_files` | Find files by name pattern or extension | ✅ |
| `grep_files` | Search INSIDE file contents (like Unix grep) | ✅ |
| `find_files_fuzzy` | Find files by fuzzy matching the filename/path | ✅ |

### Vector Store Tools (8 tools) - `src/executive_assistant/storage/vs_tools.py`

All VS tools support `scope="context"|"shared"`:
- `scope="context"` (default): Uses group_id/thread_id storage at `data/groups/{group_id}/vs/` or `data/users/{thread_id}/vs/`
- `scope="shared"`: Uses organization-wide storage at `data/shared/vs/`

| Tool | Description | Scope Support |
|------|-------------|---------------|
| `create_vs_collection` | Create a VS collection for semantic search | ✅ |
| `search_vs` | Search VS collections for semantically similar documents | ✅ |
| `vs_list` | List all VS collections with document counts | ✅ |
| `describe_vs_collection` | Describe a VS collection and preview sample documents | ✅ |
| `drop_vs_collection` | Drop a VS collection and all its documents | ✅ |
| `add_vs_documents` | Add documents to an existing VS collection | ✅ |
| `delete_vs_documents` | Delete chunks by ID from a collection | ✅ |
| `add_file_to_vs` | Add/insert a file from the files directory to a VS collection | ✅ |

## Memory Tools (9 tools)

Located in: `src/executive_assistant/tools/mem_tools.py`

| Tool | Description |
|------|-------------|
| `create_memory` | Create a new memory with facts and preferences |
| `update_memory` | Update an existing memory with new information |
| `delete_memory` | Delete a memory by ID |
| `list_memories` | List all memories with pagination |
| `search_memories` | Search memories by keyword or semantic query |
| `get_memory` | Get a specific memory by ID |
| `get_memory_by_name` | Get a memory by its name |
| `merge_memories` | Merge multiple memories into one |
| `import_memories` | Import memories from JSON format |

## Time Tools (3 tools)

Located in: `src/executive_assistant/tools/time_tool.py`

| Tool | Description |
|------|-------------|
| `get_current_time` | Get current time in specified timezone |
| `get_current_date` | Get current date in specified timezone |
| `list_timezones` | List all available timezones |

## Reminder Tools (4 tools)

Located in: `src/executive_assistant/tools/reminder_tools.py`

| Tool | Description |
|------|-------------|
| `reminder_set` | Set a new reminder (uses dateparser for flexible dates) |
| `reminder_list` | List all reminders |
| `reminder_cancel` | Cancel a reminder by ID |
| `reminder_edit` | Edit an existing reminder |

## Python Tool (1 tool)

Located in: `src/executive_assistant/tools/python_tool.py`

| Tool | Description |
|------|-------------|
| `execute_python` | Execute Python code for calculations and data processing |

## Web Search Tools (variable)

Located in: `src/executive_assistant/tools/search_tool.py`

| Tool | Description |
|------|-------------|
| `search_web` | Search the web using SearXNG |

## OCR Tools (2 tools)

Located in: `src/executive_assistant/tools/ocr_tool.py`

| Tool | Description |
|------|-------------|
| `ocr_image` | Extract text from images/PDFs using Surya OCR |
| `ocr_image_structured` | Extract structured data from images/PDFs using Surya OCR |

## Firecrawl Tools (2 tools)

Located in: `src/executive_assistant/tools/firecrawl_tool.py`

| Tool | Description |
|------|-------------|
| `firecrawl_scrape` | Scrape content from a single URL |
| `firecrawl_crawl` | Crawl a website and extract content |

## Confirmation Tool (1 tool)

Located in: `src/executive_assistant/tools/confirmation_tool.py`

| Tool | Description |
|------|-------------|
| `confirmation_request` | Request user confirmation for large operations |

## Meta Tools (2 tools)

Located in: `src/executive_assistant/tools/meta_tools.py`

| Tool | Description |
|------|-------------|
| `get_user_info` | Get current user information |
| `get_thread_info` | Get current thread information |

## Skills Tools (1 tool)

Located in: `src/executive_assistant/skills/tool.py`

| Tool | Description |
|------|-------------|
| `load_skill` | Dynamically load a skill by name |

## Standard Tools (variable)

Standard LangChain tools (conditionally loaded):

| Tool | Description |
|------|-------------|
| `tavily_search` | Tavily search results (if TAVILY_API_KEY is set) |

## Deprecated Tools Removed

The following tools have been removed and replaced with the unified scope pattern:

| Removed Tool | Replacement |
|--------------|-------------|
| `calculator` | Use `execute_python` instead |
| `orchestrator_tools` | No longer needed (archived) |
| `sqlite_helper` | Use DB tools instead |
| `task_state_tools` | Use TodoListMiddleware instead |
| `create_shared_db_table` | Use `create_db_table(scope="shared")` |
| `insert_shared_db_table` | Use `insert_db_table(scope="shared")` |
| `query_shared_db` | Use `query_db(scope="shared")` |
| `list_shared_db_tables` | Use `list_db_tables(scope="shared")` |
| `describe_shared_db_table` | Use `describe_db_table(scope="shared")` |
| `delete_shared_db_table` | Use `delete_db_table(scope="shared")` |
| `export_shared_db_table` | Use `export_db_table(scope="shared")` |
| `import_shared_db_table` | Use `import_db_table(scope="shared")` |

## Storage Hierarchy

```
data/
├── shared/              # scope="shared" (organization-wide)
│   ├── files/           # Shared file storage
│   ├── db/              # Shared database
│   └── vs/              # Shared vector store
├── groups/              # scope="context" when group_id is set (team groups)
│   └── {group_id}/
│       ├── files/
│       ├── db/
│       └── vs/
└── users/               # scope="context" when only thread_id (individual threads)
    └── {thread_id}/
        ├── files/
        ├── db/
        └── vs/
```

## Summary

- **Total Tools**: 51
- **Storage Tools with Scope**: 26 (8 DB + 10 File + 8 VS)
- **Memory Tools**: 9
- **Time Tools**: 3
- **Reminder Tools**: 4
- **Python Tool**: 1
- **Web Search**: 1+
- **OCR Tools**: 2
- **Firecrawl Tools**: 2
- **Confirmation Tool**: 1
- **Meta Tools**: 2
- **Skills Tools**: 1

## Benefits of Unified Scope Pattern

**Before (separate tools)**:
```python
# Context-scoped (group or thread)
create_db_table("users", data=[...])

# Shared (different tool)
create_shared_db_table("org_users", data=[...])
```

**After (unified API)**:
```python
# Context-scoped (default - uses group or thread automatically)
create_db_table("users", data=[...], scope="context")

# Organization-wide shared
create_db_table("org_users", data=[...], scope="shared")
```

**Advantages**:
- ✅ Consistent API across all storage tools
- ✅ Fewer tools (removed 9 separate shared_* tools)
- ✅ Easier to remember (one tool with scope parameter)
- ✅ More flexible (can switch scope at runtime)
- ✅ Better discoverability (single tool in documentation)
