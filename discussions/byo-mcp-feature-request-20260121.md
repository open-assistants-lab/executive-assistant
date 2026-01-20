# BYO MCP (Bring Your Own MCP) Feature Implementation Plan

**Date:** January 21, 2026
**Status:** Planning Phase
**Priority:** High

---

## Executive Summary

**User Request:** Enable each user to BYO (Bring Your Own) their own MCP servers to leverage Executive Assistant, while ensuring proper integration with existing skills system and system prompts.

**Current Problem:**
- MCP tools exist (`get_mcp_tools()`) but are **not loaded by default**
- `.mcp.json` is central (shared across all users)
- System prompt doesn't mention MCP tools
- No guidance on when to use MCP vs built-in tools vs skills
- Users can't discover or use MCP tools effectively

**Goal:** Provide per-user MCP server configuration with both independent configs (per-user + shared), ensuring both are self-contained and can coexist. Update system prompts to guide MCP usage.

---

## Current State Analysis

### 1. MCP Infrastructure

**`.mcp.json` Configuration:**
```json
{
  "mcpServers": {
    "firecrawl": {
      "command": "npx",
      "args": ["-y", "firecrawl-mcp"],
      "env": {
        "FIRECRAWL_API_URL": "https://...",
        "FIRECRAWL_API_KEY": "fc-your-api-key-if-required"
      }
    },
    "chrome-devtools": {...},
    "meilisearch": {...}
  }
}
```

**Characteristics:**
- Centralized configuration (shared across all users)
- Only 3 servers configured
- No per-user override capability

### 2. MCP Tool Loading

**File:** `src/executive_assistant/tools/registry.py:138-176`

```python
async def get_mcp_tools() -> list[BaseTool]:
    """
    Get tools from MCP servers configured in .mcp.json.

    This connects to the configured MCP servers (Firecrawl, Chrome DevTools,
    Meilisearch) and converts their tools to LangChain-compatible format.

    Returns:
        List of LangChain tools from MCP servers.
    """
    tools = []
    try:
        from langchain_mcp_adapters import MCPClient
        # ... connect to each server and get tools
    except ImportError:
        print("Warning: langchain-mcp-adapters not installed. MCP tools unavailable.")
    return tools
```

**Usage in `get_all_tools()`:**
```python
# Line 268: NOTE - MCP tools are NOT loaded by default
# Lines 217-218: "MCP tools are available via get_mcp_tools() but not loaded by default."
# Line 74: MCP tools are NOT loaded by default - use get_mcp_tools() manually if needed
```

**Problem:** MCP tools exist but are **invisible** to agent and users.

### 3. Skills System

**File:** `src/executive_assistant/skills/tool.py` (~100 lines)

```python
@tool
def load_skill(skill_name: str) -> str:
    """
    Load a skill definition from the skills directory.

    Returns:
        Full content of the skill file (up to 8000 chars).
    Used for:
        - Loading specialized workflows
        - Getting detailed guidance on complex tasks
        - Progressive disclosure (load only when needed)
    """
```

**Characteristics:**
- Loads from local `.md` files
- Returns full content (~8000 chars per skill)
- Fuzzy matching on skill names
- 10 core skills exist (data_management, progress_tracking, etc.)

### 4. System Prompt (Current)

**File:** `src/executive_assistant/agent/prompts.py`

**Sections:**
- Tool selection guidance (DB vs VS vs Files)
- When to load skills
- Data management workflows
- Personal applications (timesheets, information retrieval, etc.)

**Missing:**
- No mention of MCP tools
- No guidance on when to use MCP vs built-in tools
- No guidance on per-user MCP configuration

---

## Proposed Architecture

### User-Level MCP Configuration

**New File Structure:**
```
data/
├── users/
│   └── {user_id}/
│       ├── mcp.json                    # Per-user MCP servers
│       ├── db/
│       ├── files/
│       ├── vs/
│       └── mem/
└── shared/
    └── mcp.json                    # Organization-wide MCP servers
```

**Configuration Model:**
Both per-user and shared MCP configs are **independent** and can coexist. Each provides its own set of MCP servers without priority or fallback relationships.

**Characteristics:**
- Each config is self-contained (per-user or organization-wide)
- No cascading or fallback logic between configs
- Both can be loaded simultaneously when needed
- Configuration format is identical (no structural differences)

**Configuration Sources:**
1. Per-user MCP: `data/users/{user_id}/mcp.json` (user-specific servers)
2. Shared MCP: `data/shared/mcp.json` (organization-wide servers)
3. No MCP: If neither exists for a context, no MCP tools available

---

## Required Changes

### Change 1: Create MCP Configuration Loader

**File:** `src/executive_assistant/storage/mcp_storage.py` (NEW)

**Purpose:** Load per-user + shared MCP configuration (independent configs).

```python
"""MCP server configuration storage and loader."""

import json
from pathlib import Path
from typing import Any

from executive_assistant.config import settings


def get_user_mcp_config_path(user_id: str) -> Path:
    """Get per-user MCP config path."""
    return settings.get_user_root(user_id) / "mcp.json"


def get_shared_mcp_config_path() -> Path:
    """Get shared MCP config path."""
    return settings.SHARED_ROOT / "shared_mcp.json"


def load_mcp_config(user_id: str | None = None) -> dict[str, Any]:
    """
    Load MCP configuration for a user (both per-user and shared independently).

    Priority:
    1. User MCP config (data/users/{user_id}/mcp.json) - user-specific servers
    2. Shared MCP config (data/shared/mcp.json) - organization-wide servers

    Both configs are loaded independently and merged. No priority or fallback logic.

    Args:
        user_id: User ID. If None, loads from current thread context.
        If user_id is None (for shared access only), returns only shared config.

    Returns:
        MCP configuration dict with 'mcpServers', 'mcpEnabled', and 'loadMcpTools'.
    """
    # 1. Try user-specific config
    user_config = None
    if user_id:
        user_config_path = get_user_mcp_config_path(user_id)
        if user_config_path.exists():
            with open(user_config_path) as f:
                user_config = json.load(f)

    # 2. Load shared config (always loaded for completeness, independent from user config)
    shared_config_path = get_shared_mcp_config_path()
    shared_config = {}
    if shared_config_path.exists():
        with open(shared_config_path) as f:
            shared_config = json.load(f)

    # 3. Merge configs (both are independent, no override - they coexist)
    mcp_servers = {}
    mcp_enabled = False
    load_mcp_tools_mode = "default"  # Options: "default"|"manual"|"disabled"

    # User config takes precedence (adds servers, overrides enabled mode)
    if user_config:
        mcp_servers.update(user_config.get("mcpServers", {}))
        mcp_enabled = user_config.get("mcpEnabled", True)
        load_mcp_tools_mode = user_config.get("loadMcpTools", "default")

    # Shared config is loaded independently (independent from user config)
    if shared_config:
        mcp_servers.update(shared_config.get("mcpServers", {}))
        mcp_enabled = shared_config.get("mcpEnabled", False)
        load_mcp_tools_mode = shared_config.get("loadMcpTools", "default")

    return {
        "mcpServers": mcp_servers,
        "mcpEnabled": mcp_enabled,
        "loadMcpTools": load_mcp_tools_mode,
    }


def save_user_mcp_config(user_id: str, config: dict) -> None:
    """Save per-user MCP configuration."""
    config_path = get_user_mcp_config_path(user_id)
    config_path.parent.mkdir(parents=True, exist_ok=True)

    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)


def delete_user_mcp_config(user_id: str) -> None:
    """Delete per-user MCP configuration (removes config file)."""
    config_path = get_user_mcp_config_path(user_id)
    if config_path.exists():
        config_path.unlink()


def save_shared_mcp_config(config: dict) -> None:
    """Save shared MCP configuration."""
    shared_config_path = settings.SHARED_ROOT / "shared_mcp.json"
    shared_config_path.parent.mkdir(parents=True, exist_ok=True)

    with open(shared_config_path, "w") as f:
        json.dump(config, f, indent=2)
```

---

### Change 2: Create MCP Configuration Tools

**File:** `src/executive_assistant/tools/mcp_tools.py` (NEW)

**Purpose:** Tools for managing per-user MCP configuration.

```python
"""MCP configuration management tools."""

from pathlib import Path
from typing import Literal

from langchain_core.tools import tool
from executive_assistant.storage.mcp_storage import (
    load_mcp_config,
    save_user_mcp_config,
    delete_user_mcp_config,
)
from executive_assistant.storage.file_sandbox import get_thread_id
from executive_assistant.storage.helpers import sanitize_thread_id_to_user_id


def _get_current_user_id() -> str:
    """Get user_id from current thread context."""
    thread_id = get_thread_id()
    if thread_id:
        return sanitize_thread_id_to_user_id(thread_id)
    raise ValueError("No thread_id context available")


@tool
def get_mcp_config() -> str:
    """
    Get current MCP configuration for current user.

    Shows available MCP servers, enabled status, and load mode.

    Returns:
        Formatted MCP configuration.
    """
    user_id = _get_current_user_id()
    config = load_mcp_config(user_id)

    mcp_enabled = config.get("mcpEnabled", False)
    mcp_servers = config.get("mcpServers", {})
    load_mcp_tools_mode = config.get("loadMcpTools", "default")

    if not mcp_servers:
        return """
# MCP Configuration

**Status:** Disabled

No MCP servers configured.

To enable MCP tools:
1. Create `data/users/{user_id}/mcp.json` file
2. Add MCP server configuration
3. Use `reload_mcp_tools` tool to refresh

Example configuration (data/users/{user_id}/mcp.json):
```json
{
  "mcpServers": {
    "firecrawl": {
      "command": "npx",
      "args": ["-y", "firecrawl-mcp"],
      "env": {
        "FIRECRAWL_API_URL": "https://...",
        "FIRECRAWL_API_KEY": "your-key"
      }
    }
  },
  "mcpEnabled": true
}
```
"""

    lines = [
        f"# MCP Configuration",
        f"",
        f"**Status:** {'Enabled' if mcp_enabled else 'Disabled'}",
        f"",
        f"**Load Mode:** {config.get('loadMcpTools', 'default')}",
        f"",
        f"**Available Servers ({len(mcp_servers)}):**",
    ]

    if mcp_servers:
        for server_name, server_config in mcp_servers.items():
            command = server_config.get("command", "N/A")
            lines.append(f"- {server_name}")
            lines.append(f"  Command: {command}")
            if "env" in server_config:
                env_vars = list(server_config["env"].keys())
                lines.append(f"  Environment: {', '.join(env_vars)}")

    lines.append("")
    lines.append("**Configuration Files:**")
    lines.append(f"  User: data/users/{user_id}/mcp.json")
    lines.append(f"  Shared: data/shared/mcp.json (independent config)")

    return "\n".join(lines)


@tool
def reload_mcp_tools() -> str:
    """
    Reload MCP tools for current user.

    Reloads MCP configuration and clears tool cache.
    Call this after modifying `mcp.json` to apply changes.

    Returns:
        Confirmation message.
    """
    user_id = _get_current_user_id()

    # Clear MCP client cache (in registry.py)
    from executive_assistant.tools.registry import clear_mcp_cache
    clear_mcp_cache()

    return f"MCP tools reloaded for user {user_id}. Configuration loaded from data/users/{user_id}/mcp.json."


@tool
def enable_mcp_tools(
    mode: Literal["default", "manual"] = "default",
    user_id: str | None = None,
) -> str:
    """
    Enable MCP tools for current user.

    Args:
        mode: "default" (auto-load with agent tools) OR
              "manual" (load only when explicitly requested).

    Returns:
        Confirmation message.
    """
    if user_id is None:
        user_id = _get_current_user_id()

    # Load current config
    config = load_mcp_config(user_id)

    # Update configuration
    config["mcpEnabled"] = True
    config["loadMcpTools"] = mode

    save_user_mcp_config(user_id, config)

    mode_desc = "auto-load with agent tools" if mode == "default" else "manual load only"

    return f"MCP tools enabled for user {user_id} ({mode_desc})."


@tool
def disable_mcp_tools(user_id: str | None = None) -> str:
    """
    Disable MCP tools for current user.

    Clears per-user MCP config file, reverting to shared config.

    Args:
        user_id: User ID. If None, uses current thread context.

    Returns:
        Confirmation message.
    """
    if user_id is None:
        user_id = _get_current_user_id()

    # Delete per-user config (reverts to shared)
    delete_user_mcp_config(user_id)

    # Clear MCP cache
    from executive_assistant.tools.registry import clear_mcp_cache
    clear_mcp_cache()

    return f"MCP tools disabled for user {user_id}. Per-user config removed; reverting to shared configuration if available."


@tool
def add_mcp_server(
    server_name: str,
    command: str,
    args: list[str] = [],
    env: dict[str, str] = {},
    user_id: str | None = None,
) -> str:
    """
    Add a custom MCP server configuration.

    Args:
        server_name: Name for MCP server (must be unique).
        command: Command to run the MCP server (e.g., "npx", "node").
        args: Command arguments (e.g., ["-y", "firecrawl-mcp"]).
        env: Environment variables for the MCP server.
        user_id: User ID. If None, uses current thread context.

    Returns:
        Confirmation message.

    Example:
        add_mcp_server("my-api", "node", ["dist/api.js"], {"API_KEY": "secret"})
    """
    if user_id is None:
        user_id = _get_current_user_id()

    # Load current config
    config = load_mcp_config(user_id)

    # Add server
    if "mcpServers" not in config:
        config["mcpServers"] = {}

    config["mcpServers"][server_name] = {
        "command": command,
        "args": args,
        "env": env,
    }

    save_user_mcp_config(user_id, config)

    # Clear MCP cache to reload
    from executive_assistant.tools.registry import clear_mcp_cache
    clear_mcp_cache()

    return f"MCP server '{server_name}' added for user {user_id}. Use reload_mcp_tools to activate."


@tool
def remove_mcp_server(server_name: str, user_id: str | None = None) -> str:
    """
    Remove an MCP server configuration.

    Args:
        server_name: Name of the MCP server to remove.
        user_id: User ID. If None, uses current thread context.

    Returns:
        Confirmation message.
    """
    if user_id is None:
        user_id = _get_current_user_id()

    # Load current config
    config = load_mcp_config(user_id)

    if "mcpServers" in config and server_name in config["mcpServers"]:
        del config["mcpServers"][server_name]
        save_user_mcp_config(user_id, config)

        # Clear MCP cache
        from executive_assistant.tools.registry import clear_mcp_cache
        clear_mcp_cache()

        return f"MCP server '{server_name}' removed for user {user_id}."
    else:
        return f"MCP server '{server_name}' not found for user {user_id}."
```

---

### Change 3: Update Tool Registry

**File:** `src/executive_assistant/tools/registry.py`

**Changes:**

```python
# Add import for MCP storage
from executive_assistant.storage.mcp_storage import load_mcp_config

# Add cache clearing function
_mcp_client_cache: dict[str, Any] = {}

def clear_mcp_cache() -> None:
    """Clear MCP client cache to force reload."""
    global _mcp_client_cache
    _mcp_client_cache.clear()


# Update get_all_tools() to load MCP tools
async def get_all_tools() -> list[BaseTool]:
    """
    Get all available tools for the agent.

    Aggregates tools from:
    - File operations (read_file, write_file, list_files, create_folder, delete_folder, rename_folder, move_file, glob_files, grep_files)
    - Database operations (create_db_table, query_db, etc. with scope="context"|"shared")
    - Vector Store (create_vs_collection, search_vs, vs_list, etc.)
    - Memory (create_memory, update_memory, delete_memory, list_memories, search_memories, etc.)
    - Identity (request_identity_merge, confirm_identity_merge, merge_additional_identity, get_my_identity)
    - Time tools (get_current_time, get_current_date, list_timezones)
    - Reminder tools (reminder_set with dateparser, reminder_list, reminder_cancel, reminder_edit)
    - Python execution (execute_python for calculations and data processing)
    - Web search (search_web via SearXNG)
    - OCR (extract text/structured data from images/PDFs)
    - Confirmation (confirmation_request for large operations)
    - Standard tools (search)
    - **MCP configuration tools** (get_mcp_config, reload_mcp_tools, enable_mcp_tools, disable_mcp_tools, add_mcp_server, remove_mcp_server)
    - **MCP tools** (auto-loaded if enabled via load_mcp_tools_if_enabled)
    - **Skills** (load_skill)
    """
    all_tools = []

    # Add file tools
    all_tools.extend(await get_file_tools())

    # Add database tools
    all_tools.extend(await get_db_tools())

    # Add skills tools
    all_tools.extend(await get_skills_tools())

    # Add VS tools
    all_tools.extend(await get_vs_tools())

    # Add memory tools
    all_tools.extend(await get_memory_tools())

    # Add identity tools
    all_tools.extend(await get_identity_tools())

    # Add time tools
    all_tools.extend(await get_time_tools())

    # Add reminder tools
    all_tools.extend(await get_reminder_tools())

    # Add meta tools
    all_tools.extend(await get_meta_tools())

    # Add python tools
    all_tools.extend(await get_python_tools())

    # Add search tools
    all_tools.extend(await get_search_tools())

    # Add OCR tools
    all_tools.extend(await get_ocr_tools())

    # Add confirmation tools
    all_tools.extend(await get_confirmation_tools())

    # Add Firecrawl tools (only if API key is configured)
    from executive_assistant.tools.firecrawl_tool import get_firecrawl_tools
    all_tools.extend(get_firecrawl_tools())

    # Add MCP configuration tools ✅ NEW
    from executive_assistant.tools.mcp_tools import get_mcp_config_tools
    all_tools.extend(get_mcp_config_tools())

    # Add standard tools
    all_tools.extend(get_standard_tools())

    # Load MCP tools if enabled ✅ NEW
    from executive_assistant.tools.registry import load_mcp_tools_if_enabled
    all_tools.extend(await load_mcp_tools_if_enabled())

    return all_tools


async def load_mcp_tools_if_enabled() -> list[BaseTool]:
    """
    Load MCP tools from configured servers if enabled.

    Loads from both per-user and shared MCP configs (independent, no priority).
    Respects mcpEnabled and loadMcpTools settings.

    Returns:
        List of LangChain tools from MCP servers.
    """
    tools = []

    # Load MCP config (both per-user and shared) ✅ UPDATED
    try:
        from langchain_mcp_adapters import MCPClient
        from executive_assistant.storage.file_sandbox import get_thread_id
        from executive_assistant.storage.helpers import sanitize_thread_id_to_user_id
        from executive_assistant.storage.mcp_storage import (
            load_mcp_config,  # Loads both per-user + shared ✅ UPDATED
        )

        user_id = sanitize_thread_id_to_user_id(get_thread_id())

        # Load both configs independently
        user_config = load_mcp_config(user_id=user_id)
        shared_config = load_mcp_config(user_id=None)  # user_id=None = shared

        # Merge configs (both are independent, no override - they coexist) ✅ UPDATED
        mcp_servers = {}
        mcp_enabled = False

        # User config takes precedence (adds servers, overrides enabled mode)
        if user_config:
            mcp_servers.update(user_config.get("mcpServers", {}))
            mcp_enabled = user_config.get("mcpEnabled", True)
            load_mcp_tools_mode = user_config.get("loadMcpTools", "default")

        # Shared config is loaded independently (independent from user config) ✅ UPDATED
        if shared_config:
            mcp_servers.update(shared_config.get("mcpServers", {}))
            mcp_enabled = shared_config.get("mcpEnabled", mcp_enabled)
            load_mcp_tools_mode = shared_config.get("loadMcpTools", user_config.get("loadMcpTools", "default"))

        # Check if MCP is enabled globally
        if not mcp_enabled:
            return []

        # Check load mode
        load_mode = user_config.get("loadMcpTools", shared_config.get("loadMcpTools", "default"))

        if load_mode == "disabled":
            return []

        # Connect to each MCP server and get tools
        # Use cache to avoid reconnecting
        global _mcp_client_cache

        for server_name, server_config in mcp_servers.items():
            cache_key = f"{user_id}:{server_name}"  # Include user_id in cache key

            if cache_key not in _mcp_client_cache:
                try:
                    client = MCPClient(server_config)
                    server_tools = await client.get_tools()
                    tools.extend(server_tools)
                    _mcp_client_cache[cache_key] = client
                except Exception as e:
                    print(f"Warning: Failed to connect to MCP server '{server_name}': {e}")

    except ImportError:
        print("Warning: langchain-mcp-adapters not installed. MCP tools unavailable.")

    return tools
```

---

### Change 4: Update System Prompts

**File:** `src/executive_assistant/agent/prompts.py`

**Add to system prompt:**

```python
**MCP Tools (External Integrations):**

You have access to MCP (Model Context Protocol) tools for custom integrations:

**Built-in MCP Tools:**
- **firecrawl**: Web scraping with JavaScript rendering support
- **chrome-devtools**: Browser automation and debugging
- **meilisearch**: Full-text web search
- **Custom MCP**: Your own MCP servers (configure via `get_mcp_config` tool)
- **Per-user MCP configuration**: `data/users/{user_id}/mcp.json`
- **Shared MCP configuration**: `data/shared/mcp.json` (organization-wide)

**When to use MCP tools:**
- Built-in tools don't provide the functionality you need
- You need custom tools not available in Executive Assistant
- User explicitly requested external integration

**MCP Configuration Commands:**

To manage your MCP tools, use these commands:
- `get_mcp_config()` - View your current MCP configuration
- `reload_mcp_tools()` - Reload MCP tools after modifying config
- `enable_mcp_tools(mode="default"|"manual")` - Enable MCP auto-load or manual mode
- `disable_mcp_tools()` - Disable MCP tools entirely
- `add_mcp_server(name, command, args, env)` - Add a custom MCP server
- `remove_mcp_server(name)` - Remove an MCP server

**Configuration:**
Both per-user (`data/users/{user_id}/mcp.json`) and shared (`data/shared/mcp.json`) configs are **independent** and can coexist. Each provides its own set of MCP servers. No priority or fallback relationship.

To enable MCP tools:
1. Create config file at `data/users/{user_id}/mcp.json`
2. Use `add_mcp_server` tool to configure
3. Use `reload_mcp_tools` tool to activate

Example:
```
User: Configure my company API as MCP tool
Assistant: I'll help you configure a custom MCP server.
         Use add_mcp_server with:
           server_name="company-api"
           command="node"
           args=["dist/api-server.js"]
           env={"API_KEY": "your-secret-key"}
         Then use reload_mcp_tools to activate.
```
```

---

### Change 5: Update Skills System

**File:** `src/executive_assistant/skills/content/core/mcp_management.md` (NEW)

**Purpose:** Skill for MCP server configuration guidance.

```markdown
# MCP Server Configuration (BYO - Bring Your Own)

**Overview:**
Executive Assistant supports Bring Your Own (BYO) MCP servers for custom integrations. You can configure per-user MCP servers that extend Executive Assistant's capabilities beyond built-in tools.

**What is MCP?**
MCP (Model Context Protocol) enables:
- Dynamic tool discovery from external servers
- Real-time tool updates without code changes
- Per-user customization of external services

**When to use MCP vs Skills:**
- **MCP**: External services, APIs, web scrapers with special requirements
- **Skills**: Workflow guidance, multi-step processes, detailed instructions

**Configuration:**
Both per-user (`data/users/{user_id}/mcp.json`) and shared (`data/shared/mcp.json`) configs are **independent** and can coexist. Each provides its own set of MCP servers.

**When to use MCP vs Skills:**
- **MCP**: External services, APIs, web scrapers with special requirements
- **Skills**: Workflow guidance, multi-step processes, detailed instructions

**Configuration Workflow:**

1. **Create MCP config file:**
   ```
   Location: data/users/{user_id}/mcp.json

   Format:
   {
     "mcpServers": {
       "server-name": {
         "command": "npx"|"node"|"python",
         "args": ["-y", "package-name"],
         "env": {
           "ENV_VAR": "value"
         }
       }
     },
     "mcpEnabled": true              // Enable/disable all MCP tools
     "loadMcpTools": "default"        // "default"|"manual"|"disabled"
   }
   ```

2. **Configure server:**
   - Use `add_mcp_server` tool
   - Provide server name, command, args, and env variables

3. **Reload tools:**
   - Use `reload_mcp_tools` tool
   - Agent will discover and load new MCP tools

**Common MCP Use Cases:**

1. **Custom Web Scrapers:**
   - Company-specific scraping rules
   - Authenticated APIs requiring special headers
   - Rate-limited or CAPTCHA-protected sites

2. **Browser Automation:**
   - E-commerce workflows (add to cart, checkout)
   - Form filling on complex sites
   - Multi-step interactions requiring JavaScript execution

3. **Full-Text Search Engines:**
   - Private web indexes
   - Specialized domain search
   - Language-specific search engines

4. **API Integrations:**
   - Internal company APIs
   - Partner service APIs
   - Custom authentication flows

**MCP Server Template:**

```javascript
// Node.js MCP server template
import { Server } from "@modelcontextprotocol/sdk/server/index.js";

const server = new Server(
  {
    name: "my-custom-api",
    version: "1.0.0",
  },
  {
    tools: [
      {
        name: "get_company_data",
        description: "Fetch data from company API",
        inputSchema: {
          type: "object",
          properties: {
            query: {
              type: "string",
              description: "Search query"
            }
          },
          required: ["query"]
        }
      }
    ]
  }
);

// Start server
server.connect(transport);
```

**Troubleshooting:**

- **MCP tools not appearing:**
  1. Use `get_mcp_config` to verify enabled status
  2. Use `reload_mcp_tools` to refresh tool list
  3. Check MCP server is running (if custom)

- **MCP tools not working:**
  1. Verify MCP server command is correct
  2. Check environment variables (env section in mcp.json)
  3. Review MCP server logs for connection errors

- **Want to disable MCP temporarily:**
  - Use `disable_mcp_tools` to revert to shared config only
  - No need to delete servers
  - Re-enable with `enable_mcp_tools`
```

---

## Implementation Summary

### Files Created (Phase 1) ✅:
1. **`src/executive_assistant/storage/mcp_storage.py`** (✅ Created)
   - `load_mcp_config(user_id=None)`: Loads both per-user and shared configs independently
   - `save_user_mcp_config()`: Saves per-user config
   - `delete_user_mcp_config()`: Removes per-user config
   - `save_shared_mcp_config()`: Saves shared config
   - `get_user_mcp_config_path(user_id)`: Path helper
   - `get_shared_mcp_config_path()`: Path helper

2. **`src/executive_assistant/tools/mcp_tools.py`** (✅ Created)
   - `get_mcp_config()`: View current MCP configuration
   - `reload_mcp_tools()`: Reload MCP tools with cache clearing
   - `enable_mcp_tools(mode, user_id)`: Enable MCP with mode selection
   - `disable_mcp_tools(user_id)`: Disable MCP (removes per-user config)
   - `add_mcp_server(name, command, args, env, user_id)`: Add custom server
   - `remove_mcp_server(name, user_id)`: Remove server

3. **`src/executive_assistant/tools/registry.py`** (✅ Updated)
   - Added `clear_mcp_cache()`: Clear MCP client connections
   - Added `load_mcp_tools_if_enabled()`: Auto-load MCP tools when enabled
   - Updated `get_all_tools()`: Added MCP configuration tools and auto-loading

4. **`TECHNICAL_ARCHITECTURE.md`** (✅ Updated)
   - Added MCP Configuration Storage section (per-user and shared configs)

### Configuration Model:

**Independent Coexistence:**
- Per-user MCP: `data/users/{user_id}/mcp.json` (user-specific servers)
- Shared MCP: `data/shared/mcp.json` (organization-wide servers)
- Both configs are loaded independently and merged (no priority, no fallback)
- Each provides its own set of MCP servers
- User has access to both config sets simultaneously

**Key Design Decisions:**
1. **No priority relationship**: Both configs are independent
2. **No fallback logic**: Shared config is always loaded, not as fallback
3. **No override behavior**: User and shared configs are merged (not overridden)
4. **Cache keys**: Include `user_id` to avoid conflicts between users

### Next Steps:

**Phase 2: System Prompt Updates** (PENDING)
- [ ] Update `src/executive_assistant/agent/prompts.py` with MCP tool guidance (file creation)
- [ ] Test updated prompts with agent

**Phase 3: Skills Integration** (PENDING)
- [ ] Create `src/executive_assistant/skills/content/core/mcp_management.md` skill (file creation)
- [ ] Register skill in skills system
- [ ] Test skill loading via `load_skill` tool

**Phase 4: Testing** (PENDING)
- [ ] Write unit tests for MCP configuration loading
- [ ] Test MCP tool loading in isolation
- [ ] Integration tests with agent

**Phase 5: Documentation** (PENDING)
- [ ] Update README.md with MCP setup section
- [ ] Update prompts.py documentation (add inline MCP guidance)
- [ ] Create MCP configuration guide document

---

**Document Created:** 2026-01-21
**Last Updated:** 2026-01-21
**Status:** Foundation Complete ✅ | System Prompts Pending | Skills Pending | Testing Pending | Documentation Pending
**Related Documents:**
- `discussions/subagents-vs-skills-plan-20250119.md` (skills system background)
- `discussions/framework-agnostic-agent-design-20250119.md` (framework design)
- `discussions/langchain-agent-plan-20260116-1118.md` (LangChain adoption)
- `TECHNICAL_ARCHITECTURE.md` (storage architecture updated)
