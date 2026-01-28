# User-Specific MCP Plan (Claude Desktop–like Experience)

## Goal
Let each user add, manage, and use their own MCP servers without restart, with a UX similar to adding MCP servers in Claude Desktop.

## Background (Claude Desktop UX to mirror)
- Local MCP servers are configured by editing `claude_desktop_config.json` and adding entries under `mcpServers` (command/args/env). This is a “Developer > Edit Config” flow in Claude Desktop. See public setup guides that point users to that config file and the `mcpServers` map. 
- Remote MCP servers are added via Claude Desktop **Settings > Connectors** (not by editing the config file). Claude Desktop won’t connect to remote servers configured directly in `claude_desktop_config.json`. 

## User Experience (Proposed)
### A) Local MCP (stdio) — “Edit Config”–style
- `/mcp add` (interactive), `/mcp add-json <json>`, or `/mcp upload` (file)
- Prompts for:
  - Server name
  - Command + args
  - Env vars
  - (Optional) working dir
- Writes to per-user config: `data/users/{thread_id}/mcp.json`
- Immediately loads tools (hot reload)
- `/mcp list`, `/mcp remove <name>`, `/mcp edit <name>`
- `/mcp download` returns the current `mcp.json` for review

### B) Remote MCP (HTTP/SSE) — “Connectors”–style
- `/mcp connect` opens a guided flow:
  - Server URL
  - Auth method (none / API key / OAuth)
  - If OAuth: return a connect link and store token on success
- Store remote entries separately in `data/users/{thread_id}/mcp_remote.json`
- Apply remote policy: only enable remote MCPs added via this flow

### C) Parity with Claude Desktop behavior
- Separate **local config** vs **remote connectors**
- Clear warnings about security and trust
- Explicit allow/deny list per user
- Confirmation before enabling a new MCP server

## Storage Model
- Local: `data/users/{thread_id}/mcp.json`
  - schema aligns to MCP server config:
    - `type: "stdio"`, `command`, `args`, `env`, `cwd`
- Remote: `data/users/{thread_id}/mcp_remote.json`
  - `type: "http" | "sse"`, `url`, `headers` or OAuth token reference

## Runtime Architecture
- Load order:
  1) User-local MCP (stdio)
  2) User-remote MCP
  3) Admin MCP (if allowed)
- Per-thread tool registry with caching
- Hot reload on config change (file watcher or on-demand reload)

## Security & Safety
- User confirmation required before enabling a new MCP server
- Allowlist tool names per user (optional)
- Denylist for risky tools (filesystem, shell) by default
- Token/response size guardrails
- Visible audit log of MCP tool calls

## Implementation Steps
1) Add a `user_mcp_storage.py` for reading/writing user MCP configs
2) Add `mcp` management commands:
   - `/mcp list`, `/mcp add`, `/mcp add-json`, `/mcp upload`, `/mcp download`, `/mcp remove`, `/mcp disable`, `/mcp enable`
3) Add JSON file upload flow:
   - Accept a file, parse + validate schema, show a diff/summary, ask confirmation
   - On confirm, write to `data/users/{thread_id}/mcp.json` and hot-reload
4) Add download flow:
   - Serialize current config and send as a file to the user
5) Update tool registry to load user MCP servers per thread
6) Add hot-reload (watcher or explicit reload on change)
7) Add OAuth hook for remote MCPs (optional phase)

## Success Criteria
- A user can add a local MCP server with a guided flow in chat
- Tools appear immediately without restart
- Remote MCP servers are only added via the connector flow, not config edits
- Security prompts occur before activation
