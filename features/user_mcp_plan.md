# User-Specific MCP (Model Context Protocol) Plan

**Status**: Planning Phase - NOT FOR IMPLEMENTATION
**Last Updated**: January 31, 2026
**Priority**: Low (Feature complete after instinct system validation)

---

## Executive Summary

Enable users to add, manage, and use their own MCP (Model Context Protocol) servers per conversation, similar to the Claude Desktop experience. This feature gives users control over their tool ecosystem while maintaining security and isolation.

**Current State**: Global admin MCP configuration exists via `data/admins/mcp.json` (line 199-210 in registry.py)
**Proposed**: Add per-thread/user MCP configuration with hot-reload capabilities

---

## Table of Contents

1. [Goals & Use Cases](#goals--use-cases)
2. [Current Architecture](#current-architecture)
3. [Proposed Architecture](#proposed-architecture)
4. [Storage Model](#storage-model)
5. [User Experience Design](#user-experience-design)
6. [Security Considerations](#security-considerations)
7. [Implementation Plan](#implementation-plan)
8. [Success Criteria](#success-criteria)

---

## Goals & Use Cases

### Primary Goals
1. **User Autonomy**: Allow users to add custom tools without admin intervention
2. **Isolation**: Per-thread MCP configuration prevents cross-contamination
3. **Hot-Reload**: Tools appear immediately without agent restart
4. **UX Parity**: Mirror Claude Desktop's MCP management experience

### Use Cases

**Developers**:
- Add local MCP servers for development tools (ast, eslint, etc.)
- Test new MCP integrations in isolated conversations
- Switch toolsets between projects without restarting

**Teams**:
- Share team-specific MCP servers via config import
- Manage tool access per conversation/channel
- Audit MCP tool usage per thread

**Power Users**:
- Combine admin MCP servers (global tools) with user MCP servers (custom tools)
- A/B test different MCP servers
- Create tool profiles for different workflows

---

## Current Architecture

### Global Admin MCP (Existing)

**Configuration**: `data/admins/mcp.json` (admin-managed)
```json
{
  "mcpServers": {
    "fetch": {
      "command": "uvx",
      "args": ["mcp-server-fetch", "--port", "3000"]
    }
  }
}
```

**Loading**: `get_mcp_tools_if_enabled()` in `registry.py` (line 419-457)
- Checks if MCP is enabled via config
- Loads from admin config path only
- No per-user or per-thread support

**Integration**:
- Loaded via `MultiServerMCPClient` (langchain-mcp-adapters)
- Tools appear in agent's tool registry
- Global scope: all threads share the same MCP tools

**Current Limitations**:
- ❌ No per-user MCP configuration
- ❌ Requires admin access to add servers
- ❌ No hot-reload (requires agent rebuild or restart)
- ❌ No import/export of MCP configurations

---

## Proposed Architecture

### Multi-Tier MCP Loading

**Priority Order** (highest priority first):
1. **User-Local MCP** (std/io): `data/users/{thread_id}/mcp.json`
2. **User-Remote MCP** (HTTP/SSE): `data/users/{thread_id}/mcp_remote.json`
3. **Admin MCP** (global): `data/admins/mcp.json` (existing)

**Tool Loading Flow**:
```python
def get_mcp_tools_for_thread(thread_id: str) -> list[BaseTool]:
    """Load MCP tools with priority: User > Admin."""

    tools = []

    # 1. User-local MCP (highest priority)
    user_mcp_config = load_user_mcp_config(thread_id)
    if user_mcp_config:
        tools.extend(load_mcp_servers(user_mcp_config))

    # 2. User-remote MCP (medium priority)
    user_remote_config = load_user_remote_mcp_config(thread_id)
    if user_remote_config:
        tools.extend(load_mcp_servers(user_remote_config))

    # 3. Admin MCP (fallback, lowest priority)
    admin_config = load_admin_mcp_config()  # Existing
    if admin_config:
        tools.extend(load_mcp_servers(admin_config))

    return tools
```

**Tool Name Collision Handling**:
- User tools override admin tools (same name)
- Warning logged when collision occurs
- User can see which tools are from which source

---

## Storage Model

### Directory Structure

```
data/users/{thread_id}/
├── mcp.json              # User-local MCP servers (stdio)
├── mcp_remote.json       # User-remote MCP servers (HTTP/SSE)
└── instincts/
    ├── instincts.jsonl
    └── instincts.snapshot.json
```

### Schema: `mcp.json` (User-Local)

```json
{
  "version": "1.0",
  "updated_at": "2026-01-31T10:00:00Z",
  "mcpServers": {
    "filesystem": {
      "type": "stdio",
      "command": "uvx",
      "args": ["mcp-server-filesystem", "--allow", "."],
      "env": {
        "PATH": "/usr/local/bin"
      },
      "cwd": "/home/user/projects"
    },
    "ast": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@astrojs/mcp-server-ast"],
      "env": {}
    }
  }
}
```

### Schema: `mcp_remote.json` (User-Remote)

```json
{
  "version": "1.0",
  "updated_at": "2026-01-31T10:00:00:00Z",
  "mcpServers": {
    "github": {
      "type": "http",
      "url": "https://api.github.com/mcp",
      "headers": {
        "Authorization": "Bearer ${GITHUB_TOKEN}"
      }
    },
    "custom-api": {
      "type": "http",
      "url": "https://api.example.com/mcp",
      "headers": {
        "X-API-Key": "${API_KEY}"
      }
    }
  }
}
```

---

## User Experience Design

### Command Interface

**Discovery**:
- `/mcp list` - Show all configured MCP servers (user + admin)
- `/mcp show <name>` - Display server details (config, tools, status)
- `/mcp search <query>` - Search for MCP servers by name/description

**Management**:
- `/mcp add` - Interactive guided flow to add server
- `/mcp add-json <json>` - Add server from JSON config
- `/mcp upload` - Upload config file (creates backup first)
- `/mcp remove <name>` - Remove server (requires confirmation)
- `/mcp edit <name>` - Edit server configuration
- `/mcp disable <name>` - Disable server (keep config, don't load)
- `/mcp enable <name>` - Re-enable disabled server

**Import/Export**:
- `/mcp download` - Download current config as file
- `/mcp import <file>` - Import config from file (merge/replace options)

**Testing**:
- `/mcp test <name>` - Test MCP server connection
- `/mcp tools <name>` - List available tools from server

### Interactive Add Flow (`/mcp add`)

```
You: /mcp add

Assistant: Let's add an MCP server. First, what type?

1. Local (command-line tool)
2. Remote (HTTP/SSE API)

You: 1

Assistant: What should we call this server?
You: filesystem

Assistant: What command runs this server?
You: npx mcp-server-filesystem

Assistant: What arguments should I pass?
You: --allow .

Assistant: Any environment variables? (enter 'done' when finished)
You: PATH=/usr/local/bin

Assistant: Working directory? (optional, press enter to skip)
You: /home/user/projects

Assistant: I'll add this MCP server:
  Type: Local (stdio)
  Name: filesystem
  Command: npx mcp-server-filesystem
  Args: --allow .
  Env: PATH=/usr/local/bin
  CWD: /home/user/projects

Confirm? (yes/no)
You: yes

Assistant: ✓ Added 'filesystem' MCP server
  Tools detected: 12
  Status: Connected

Would you like to test it now?
```

### Configuration File Upload (`/mcp upload`)

1. User uploads `mcp.json` file
2. Parse and validate JSON schema
3. Show diff/summary of changes
4. Ask for confirmation
5. If confirmed:
   - Backup current config to `mcp.backup.{timestamp}.json`
   - Write new config
   - Hot-reload tools
   - Show which tools were added/removed

---

## Security Considerations

### Isolation

**Per-Thread Scope**:
- Each `thread_id` has isolated MCP configuration
- No cross-thread tool access
- File system operations respect thread isolation (via FileSandbox)

**Storage Isolation**:
- User MCP configs stored in `data/users/{thread_id}/`
- Admin cannot access user MCP configs (privacy)
- Users cannot modify admin MCP configs

### Tool Safety

**Denylist by Default** (applied to user MCP tools):
```python
HIGH_RISK_TOOLS = {
    # Filesystem access
    "read_file", "write_file", "delete_file",
    "create_folder", "delete_folder",

    # Shell access
    "execute_python", "execute_command",

    # Database modification
    "delete_tdb_table", "drop_vdb_collection",
}
```

**Allowlist Mode**:
- User can opt-in to risky tools with explicit confirmation
- Warning: "This tool can modify files. Continue?"
- Audit log: All tool calls logged with thread_id

### Validation

**JSON Schema Validation**:
- Command must exist (PATH check or absolute path required)
- Args must be list
- Env must be dict
- CWD must be within allowed paths

**URL Validation** (remote MCP):
- HTTPS required (no HTTP unless explicitly allowed)
- Domain allowlist (optional)
- Token validation

---

## Implementation Plan

### Phase 1: Storage & Discovery (Week 1)

**Files to Create**:
- `src/executive_assistant/storage/user_mcp_storage.py`
  - `load_user_mcp_config(thread_id)` - Load user's local MCP config
  - `load_user_remote_mcp_config(thread_id)` - Load user's remote MCP config
  - `save_user_mcp_config(thread_id, config)` - Save with validation
  - `validate_mcp_config(config)` - Schema validation
  - `backup_user_mcp_config(thread_id)` - Create backup before changes

**Files to Modify**:
- `src/executive_assistant/tools/registry.py`
  - Add `get_mcp_tools_for_thread(thread_id)` function
  - Replace `get_mcp_tools_if_enabled()` with tiered loading

**Deliverables**:
- ✅ User MCP storage layer
- ✅ Tiered MCP loading (user > admin)
- ✅ Config validation
- ✅ Backup/restore functionality

### Phase 2: CLI Commands (Week 2)

**Files to Create**:
- `src/executive_assistant/tools/user_mcp_tools.py`
  - 15+ tools for MCP management (add, list, show, remove, edit, test, etc.)

**CLI Commands** (if using command framework):
- Map tools to `/mcp` command namespace in channels

**Deliverables**:
- ✅ Complete MCP management toolset
- ✅ Interactive add/remove flows
- ✅ Config import/export
- ✅ Server testing capabilities

### Phase 3: Hot-Reload (Week 2)

**Approach**:
1. File watcher on `mcp.json` changes (when feasible)
2. Explicit reload command `/mcp reload`
3. Check for config on each message (expensive, use sparingly)

**Implementation Options**:
- **Simple**: Reload on `get_all_tools()` call (check file mtime)
- **Advanced**: Watchdog background task with file notifications
- **Recommended**: Explicit reload for simplicity + control

**Deliverables**:
- ✅ Hot-reload functionality
- ✅ Changed config detection
- ✅ Graceful error handling (reload failures don't break agent)

### Phase 4: Testing & Polish (Week 3)

**Test Coverage**:
- Unit tests for storage layer
- Integration tests for tool loading
- End-to-end tests for CLI flows
- Security tests (tool denylist, isolation)

**Documentation**:
- User guide for adding MCP servers
- Admin guide for managing user MCP
- Troubleshooting common issues

---

## Success Criteria

### Must Have (P0)
- ✅ Users can add local MCP servers via `/mcp add`
- ✅ Tools load immediately without restart
- ✅ Per-thread isolation (configs stored separately)
- ✅ JSON schema validation
- ✅ Basic security (command validation, CWD restrictions)

### Should Have (P1)
- ✅ Remote MCP support via `/mcp connect`
- ✅ Config import/export
- ✅ Tool name collision handling with warnings
- ✅ Server testing command

### Nice to Have (P2)
- ⏳ OAuth flow for remote MCP authentication
- ⏳ Tool allowlist/denylist configuration
- ⏳ Config file watcher for auto-reload
- ⏳ Per-server enable/disable (vs removing)
- ⏳ MCP tool usage analytics

---

## Open Questions

1. **Tool Priority**: If user and admin both provide same tool name, which takes precedence?
   - **Recommendation**: User tools override admin tools (user autonomy principle)

2. **Config Validation**: Should we validate that the MCP server actually exists/works before adding?
   - **Recommendation**: Validate schema only (not connectivity) to avoid blocking configs for offline scenarios

3. **Remote MCP Security**: How to store OAuth tokens securely?
   - **Recommendation**: Use keyring/secret store or encrypted storage with access controls

4. **Admin Override**: Should admins be able to disable user MCP servers?
   - **Recommendation**: Yes, for safety/compliance reasons

5. **Hot-Reload Frequency**: How often to check for config changes?
   - **Recommendation**: On-demand (`/mcp reload`) + check on thread start

---

## Migration Notes

### From Global Admin MCP

**Before** (current):
- All threads share same MCP tools
- Admin adds servers in `data/admins/mcp.json`
- Requires restart to add new tools

**After** (proposed):
- Each thread can have custom tools
- Users add servers via `/mcp add` in conversation
- No restart required (hot-reload)

**Compatibility**:
- Global admin MCP still works (fallback)
- Existing `data/admins/mcp.json` format unchanged
- Backward compatible with current deployment

---

## Alternative Approaches Considered

### Option A: Single Config File (Rejected)
- **Idea**: Single `mcp.json` with `scope: "user"` vs `scope: "admin"`
- **Rejected**: Mixing scopes increases complexity and error risk

### Option B: Database Storage (Rejected)
- **Idea**: Store MCP configs in PostgreSQL
- **Rejected**: Overkill for this use case; files are simpler and more portable

### Option C: Inline Tool Definition (Rejected)
- **Idea**: Define MCP tools directly in `/mcp add` command
- **Rejected**: MCP requires external process management, not just tool definitions

---

## Dependencies

**Required**:
- `langchain-mcp-adapters` (already in use for admin MCP)
- JSON schema validation (pydantic or jsonschema)

**Optional**:
- Watchdog for file watching (if auto-reload desired)
- Keyring/secret store (for OAuth tokens)
- File upload handling (already exists in channels)

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| **User adds malicious MCP server** | High - Can compromise system | ⚠️ Command validation, CWD restrictions, tool denylist |
| **MCP server crashes frequently** | Medium - Degrades UX | ⚠️ Retry logic, graceful degradation |
| **Tool name collisions** | Low - Confusion | ⚠️ Warnings, admin override capability |
| **Config file corruption** | Low - Lost MCP servers | ⚠️ Backups, validation, recovery prompts |
| **Hot-reload race conditions** | Medium - Tool loading mid-conversation | ⚠️ Reload between conversations, not during |
| **Too many tools** | Medium - Token cost, confusion | ⚠️ Tool limit, categorization UI |

---

## Post-MVP Enhancements

1. **MCP Marketplace** (curated list of community MCP servers)
2. **Tool Reputation Scoring** (learn which tools are reliable)
3. **Automatic Tool Discovery** (scan for MCP servers on localhost)
4. **MCP Server Metrics** (latency, error rates, usage stats)
5. **Config Versioning** (git-style history for configs)

---

**Next Steps**: Wait for user confirmation of test results, then approve this plan for implementation prioritization.
