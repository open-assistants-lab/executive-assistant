# Plan: Verb-First Tool Renaming (2026-01-16)

## Goal
Standardize all tool names to verb‑first for LLM clarity and consistency.

## Naming Convention
Use `verb_domain_object` for domain-specific tools, `verb_object` for global tools.

**Preferred verbs:** `get`, `set`, `create`, `read`, `write`, `list`, `search`, `delete`, `update`, `add`, `remove`, `execute`, `calculate`, `check`.

## Renaming Map (27 tools)

### Files (2 tools)
| Current | New |
|---------|-----|
| file_read | read_file |
| file_write | write_file |

### Database (8 tools)
| Current | New |
|---------|-----|
| db_create_table | create_db_table |
| db_describe_table | describe_db_table |
| db_drop_table | delete_db_table |
| db_export_table | export_db_table |
| db_import_table | import_db_table |
| db_insert_table | insert_db_table |
| db_list_tables | list_db_tables |
| db_query | query_db |

### Knowledge Base (5 tools)
| Current | New |
|---------|-----|
| kb_add_documents | add_kb_documents |
| kb_delete | delete_kb_entry |
| kb_describe | describe_kb |
| kb_search | search_kb |
| kb_store | store_kb_document |
| kb_list | *(no change, already verb-first)* |

### Memory (8 tools)
| Current | New |
|---------|-----|
| memory_create | create_memory |
| memory_delete | delete_memory |
| memory_forget | forget_memory |
| memory_get_by_key | get_memory_by_key |
| memory_list | list_memories |
| memory_normalize_or_create | normalize_or_create_memory |
| memory_search | search_memories |
| memory_update | update_memory |

### Time (3 tools)
| Current | New |
|---------|-----|
| time_get_current | get_current_time |
| time_get_current_date | get_current_date |
| time_list | list_timezones |

### Other (2 tools)
| Current | New |
|---------|-----|
| orchestrator_delegate | delegate_to_orchestrator |
| python_execute | execute_python |

### Already verb-first (no change)
- calculator, clear_plan, confirmation_request
- create_folder, delete_folder, glob_files, grep_files, list_files, move_file, rename_folder
- init_plan, list_plans, read_plan, update_plan, write_plan
- reminder_cancel, reminder_edit, reminder_list, reminder_set
- search_web
- firecrawl_scrape, firecrawl_crawl, firecrawl_check_status

## Implementation Steps
1. Rename tool functions in source files
2. Update tool registry (`src/cassey/tools/registry.py`)
3. Update storage `__init__.py` exports
4. Update any hardcoded references (management_commands.py, prompts.py)
5. Test and restart

## Files to Modify
- `src/cassey/storage/file_sandbox.py`
- `src/cassey/storage/db_tools.py`
- `src/cassey/storage/kb_tools.py`
- `src/cassey/tools/mem_tools.py`
- `src/cassey/tools/time_tool.py`
- `src/cassey/tools/search_tool.py`
- `src/cassey/tools/python_tool.py`
- `src/cassey/tools/orchestrator_tools.py`
- `src/cassey/tools/registry.py`
- `src/cassey/storage/__init__.py`
- `src/cassey/channels/management_commands.py`
- `src/cassey/channels/base.py`
