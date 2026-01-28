# Quick Tool Reference

Description: Concise reference of all available tools organized by category

Tags: core, quickstart, reference, tools

## Storage Tools

| Category | Tools | When to Use |
|----------|-------|-------------|
| **Files** | `read_file`, `write_file`, `list_files`, `glob_files`, `grep_files`, `create_folder`, `delete_folder`, `rename_folder`, `move_file`, `delete_file` | Documents, exports, configs |
| **TDB** | `create_tdb_table`, `insert_tdb_table`, `query_tdb`, `list_tdb_tables`, `describe_tdb_table`, `delete_tdb_table`, `export_tdb_table`, `import_tdb_table`, `add_tdb_column`, `drop_tdb_column` | Daily tracking, transactional data |
| **VDB** | `create_vdb_collection`, `add_vdb_documents`, `search_vdb`, `describe_vdb_collection`, `drop_vdb_collection`, `vdb_list`, `update_vdb_document`, `delete_vdb_documents` | Knowledge base, semantic search |
| **ADB** | `list_adb_tables`, `describe_adb_table`, `show_adb_schema`, `query_adb`, `create_adb_table`, `import_adb_csv`, `export_adb_table`, `drop_adb_table`, `optimize_adb` | Analytics, complex SQL, large datasets |
| **Memory** | `create_memory`, `get_memory_by_key`, `search_memories`, `list_memories`, `update_memory`, `delete_memory`, `forget_memory`, `normalize_or_create_memory` | User preferences, facts |

## Automation Tools

| Category | Tools | When to Use |
|----------|-------|-------------|
<!-- DISABLED: Flow tools - not production-ready yet -->
<!-- | **Flows** | `create_flow`, `list_flows`, `run_flow`, `cancel_flow`, `delete_flow`, `create_flow_project` | Scheduled/multi-step workflows | -->
<!-- DISABLED: Agent tools - not production-ready yet -->
<!-- | **Agents** | `create_agent`, `list_agents`, `run_agent`, `get_agent`, `update_agent`, `delete_agent` | Specialized mini-agents for flows | -->
| **Reminders** | `reminder_set`, `reminder_list`, `reminder_cancel`, `reminder_edit` | Future notifications |

## External Tools

| Category | Tools | When to Use |
|----------|-------|-------------|
| **Web** | `search_web`, `firecrawl_scrape`, `firecrawl_crawl`, `firecrawl_check_status`, `playwright_scrape` | Research, data extraction |
| **OCR** | `ocr_extract_text`, `ocr_extract_structured`, `extract_from_image` | Document/image processing |

## Utility Tools

| Tool | Purpose |
|------|---------|
| `execute_python` | Run Python code in sandbox |
| `get_current_time` | Get time in timezone |
| `get_current_date` | Get date in timezone |
| `list_timezones` | List available timezones |
| `get_meta` | Get system metadata |
| `confirm_request` | Confirm destructive/large actions |
| `load_skill` | Load detailed skill guidance |

## MCP Admin Tools (Admin-only)

| Tool | Purpose |
|------|---------|
| `get_mcp_config` | View MCP configuration |
| `reload_mcp_tools` | Reload MCP tools after config changes |
| `enable_mcp_tools` | Enable MCP tools globally |
| `disable_mcp_tools` | Disable MCP tools globally |
| `add_mcp_server` | Add a custom MCP server |
| `remove_mcp_server` | Remove an MCP server |

## Quick Decision

```
What do you need?
├─ Store user preference? → Memory
├─ Daily tracking (expenses, timesheets)? → TDB
├─ Complex analytics (window functions)? → ADB
├─ Document search by meaning? → VDB
├─ Schedule automation? → Flows
└─ Simple file storage? → Files
```

## Data Format for TDB/ADB

**Both formats are accepted:**

```python
# Python list (easier to write)
create_tdb_table("users", data=[{"name": "Alice", "age": 30}])
insert_tdb_table("users", data=[{"name": "Bob", "age": 25}])
create_adb_table("sales", data=[{"id": 1, "amount": 100}])

# JSON string (also works)
create_tdb_table("users", data='[{"name": "Alice", "age": 30}]')
```

## Load Detailed Skills

For deep dives, say: `load_skill("storage")`, `load_skill("analytics")`<!-- DISABLED: `, `load_skill("flows")` -->
