---
name: subagent-manager
description: Guide for creating and managing subagents - includes tool usage, available skills, and tool names
---

# Subagent Manager Guide

This guide explains how to use the subagent system to create and manage subagents.

## Available Subagent Tools

### 1. subagent_create
Create a new subagent with specified configuration.

**Required arguments:**
- `name`: Subagent name (alphanumeric, hyphens, underscores only)
- `user_id`: The user ID

**Optional arguments:**
- `model`: Model to use (e.g., "anthropic:claude-sonnet-4-20250514")
- `description`: What this subagent does
- `skills`: List of skill names (see Available Skills below)
- `tools`: List of tool names (see Available Tools below)
- `system_prompt`: Custom system prompt (saved to config.yaml)
- `mcp_config`: MCP servers as JSON string (saved to .mcp.json)

**Example:**
```
Create a subagent named "research-agent" with search_web and files_write tools, skills: planning-with-files, description: Research assistant
```

### 2. subagent_invoke
Invoke a subagent to execute a task.

**Required arguments:**
- `name`: Subagent name
- `task`: Task description
- `user_id`: The user ID

**Example:**
```
Invoke the research-agent subagent to find information about X
```

### 3. subagent_schedule
Schedule a subagent to run once or on a recurring basis.

**Required arguments:**
- `subagent_name`: Name of the subagent to schedule
- `task`: Task description
- `schedule`: "once" for one-time, or cron expression (e.g., "0 9 * * *" for daily 9am)
- `user_id`: The user ID

**Optional arguments:**
- `run_at`: ISO datetime for "once" schedule (e.g., "2026-03-05T14:30:00")

**Example:**
```
Schedule the research-agent to run at 2026-03-05T14:30:00 with task: do X
```

### 4. subagent_list
List all subagents for a user.

**Required arguments:**
- `user_id`: The user ID

### 5. subagent_progress
Get subagent progress from planning files.

**Required arguments:**
- `task_name`: Name of the planning task
- `user_id`: The user ID

### 6. subagent_validate
Validate a subagent configuration.

**Required arguments:**
- `name`: Subagent name
- `user_id`: The user ID

### 7. subagent_batch
Run multiple subagents in parallel.

**Required arguments:**
- `tasks`: JSON array of {name, task} objects
- `user_id`: The user ID

**Example:**
```
[{"name": "agent-a", "task": "do X"}, {"name": "agent-b", "task": "do Y"}]
```

## Available Skills

When creating a subagent, you can assign these skills:

- **planning-with-files** (REQUIRED for multi-step tasks): Creates planning files to track progress
- **deep-research**: For comprehensive research tasks
- **skill-creator**: For creating new skills

Always include `planning-with-files` for tasks with multiple steps.

## Available Tools

When creating a subagent, you can assign these tools:

**File Operations:**
- `files_list`: List files in a directory
- `files_read`: Read file content
- `files_write`: Write content to a file
- `files_edit`: Edit a file
- `files_delete`: Delete a file
- `files_mkdir`: Create a directory
- `files_rename`: Rename a file or directory
- `files_glob_search`: Search files by pattern
- `files_grep_search`: Search file contents
- `files_versions_list`: List file versions
- `files_versions_restore`: Restore file version
- `files_versions_delete`: Delete file version
- `files_versions_clean`: Clean up old versions

**Web:**
- `search_web`: Search the web
- `scrape_url`: Scrape a URL
- `map_url`: Map a website
- `crawl_url`: Crawl URLs

**Email:**
- `email_list`: List emails
- `email_get`: Get email by ID
- `email_search`: Search emails
- `email_send`: Send email
- `email_sync`: Sync emails

**Contacts:**
- `contacts_list`: List contacts
- `contacts_search`: Search contacts
- `contacts_add`: Add contact

**Todos:**
- `todos_list`: List todos
- `todos_add`: Add todo
- `todos_update`: Update todo
- `todos_delete`: Delete todo

**Memory:**
- `memory_get_history`: Get conversation history
- `memory_search`: Search memory

**Time:**
- `time_get`: Get current time

**Other:**
- `shell_execute`: Execute shell commands
- `skills_list`: List available skills
- `mcp_list`: List MCP servers
- `mcp_tools`: Get MCP server tools

## Important Notes

1. **Always include `planning-with-files` skill** for multi-step tasks - this enables progress tracking

2. **Output files location**:
   - **Planning files** (task_plan.md, progress.md, findings.md) → `planning/{task_name}/`
   - **User deliverables** (SPEC.md, code, reports) → `workspace/` (not in planning/)
   - Example: "Save SPEC.md to workspace/SPEC.md" not "planning/"

3. **Use correct tool names** - not `memory_save` (doesn't exist), use `memory_search` or `memory_get_history`

4. **For scheduling**: Use ISO datetime format like "2026-03-05T14:30:00" for specific times

5. **System prompt**: If user provides custom prompt, pass it as `system_prompt` parameter

6. **MCP config**: Pass as JSON string to `mcp_config` parameter (saved as `.mcp.json`)

## Example Workflow

1. Create subagent with tools and skills
2. Invoke immediately OR schedule for later
3. Use planning skill for progress tracking (saves to planning/)
4. Save final deliverables to workspace/ (not planning/)
