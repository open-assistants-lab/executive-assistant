# Custom Tools — CLI Tool Discovery & Registration

## Problem

The agent has ~100 built-in native tools (`@tool` decorators in `src/sdk/tools_core/`) plus MCP tools, connector tools, and potentially user-created custom tools. Loading all definitions into the context window:

- **Degrades tool selection accuracy** past 30-50 tools (Anthropic's documented threshold)
- **Consumes 10-20K tokens per turn** on tool definitions
- **No reuse** — a CLI tool discovered once via `--help` must be re-discovered every session

## Solution

A cross-cutting **tool search** system that keeps a small core inline and discovers everything else on demand via search. All tool types (native, custom, MCP, connector) go into the same searchable index. HybridDB powers the index — FTS5 for keyword matching, optional ChromaDB embeddings for semantic search.

### Artifact comparison

| Artifact | Seed/Built-in | User-created | Discovery | Format | Namespace |
|----------|--------------|--------------|-----------|--------|-----------|
| **Skill** | `src/skills_seed/*/SKILL.md` | `{ea_root}/Skills/*/SKILL.md` | Scan skills dir | YAML frontmatter + Markdown | Flat |
| **Subagent** | — | `{ea_root}/Subagents/*/PROFILE.md` | Scan subagents dir | YAML frontmatter + Markdown | Flat |
| **Native tool** | `src/sdk/tools_core/*.py` | — | Hardcoded imports | `@tool` decorator | Flat |
| **Custom tool** | — | `{ea_root}/Tools/*/TOOL.md` | Scan tools dir | YAML frontmatter + Markdown | Flat |
| **MCP tool** | — | `{ea_root}/.mcp.json` servers | MCPManager starts servers | `mcp` SDK objects | `mcp__{server}__{tool}` |
| **Connector tool** | — | connectkit OAuth vault | ConnectKitBridge reads YAML | CLI args or spawned MCP | `{namespace}__{tool}` |

### Tool type handling

All four tool types share the same infrastructure — HybridDB index, `tool_search`, lazy-load, `tool_reload`, recency tracking. They differ only in how their function is reconstructed at load time:

| Type | Source | Function backend | Reconstructed by |
|------|--------|-----------------|-----------------|
| `native` | `get_native_tools()` | Hardcoded Python callable | Re-import from native tools by name |
| `custom` | `{ea_root}/Tools/*/TOOL.md` | `subprocess.run(shell=True)` with rendered command | `_rebuild_custom_function()` from `reconstruct.command` |
| `mcp` | MCPManager from `.mcp.json` | Closure over `session.call_tool()` | `loop._mcp_bridge.get_tool_definition(name)` re-resolves from live session |
| `connector` | ConnectKitBridge from vault | CLI subprocess with OAuth token injection or MCP session call | `loop._connectkit_bridge.get_tool_definition(namespace, name)` re-resolves from live bridge |

### Tool loading strategy

Three tiers, applied uniformly across all tool types:

| Tier | Condition | Inline | Searchable |
|------|-----------|--------|------------|
| **Core** | Always | ~16 essential tools (`shell_execute`, `files_read`, `files_write`, `files_edit`, `message_search`, `memory_search`, `time_get`, `web_search`, `web_scrape`, `todos_list`, `email_list`, `contacts_list`, `skills_load`, `subagent_delegate`, `mcp_reload`, `tool_reload`) | Everything else |
| **Recency** | Tools called in current conversation | Stay loaded for subsequent turns | — |
| **Search** | Agent calls `tool_search(query)` | 3-5 matching results loaded for the current + subsequent turns | Full index |

The model receives this system prompt hint:

```
You have access to {N} additional tools across all categories.
Use tool_search(description="what you need") to find and load a specific tool.
```

Discovered tools remain inline for the rest of the conversation (or until context compaction evicts them, at which point the agent can search again).

### TOOL.md format

A `TOOL.md` file uses YAML frontmatter delimited by `---` with a Markdown body for usage notes. Custom tools share the **flat namespace** with native tools (no prefix), so names must be globally unique:

```yaml
---
name: pdf_extract_text
description: Extract text from PDF files using ocrmypdf + pdftotext. Use when the user needs text content from a PDF document.
command: ocrmypdf "{{input}}" /tmp/_ocr_output.pdf && pdftotext /tmp/_ocr_output.pdf "{{output}}"
parameters:
  type: object
  properties:
    input:
      type: string
      description: Path to the PDF file
    output:
      type: string
      description: Path for the extracted text file
  required:
    - input
    - output
annotations:
  title: PDF Text Extractor
  read_only: true
  destructive: false
  idempotent: true
  open_world: false
output_schema:
  type: string
  description: Path to the extracted text file on disk
install:
  - brew install ocrmypdf poppler
  - pip install ocrmypdf
---
```

**Frontmatter fields (mirrors `ToolDefinition`):**

| Field | Required | Maps to | Description |
|-------|----------|---------|-------------|
| `name` | Yes | `ToolDefinition.name` | Tool identifier. Imperative verb + domain context recommended. |
| `description` | Yes | `ToolDefinition.description` | When to use this tool, with keywords. Primary search surface. |
| `command` | Yes | (stored as extra field) | Shell command template with `{{param}}` placeholders. Used by generated `function` wrapper. |
| `parameters` | No | `ToolDefinition.parameters` | JSON Schema dict (`type`, `properties`, `required`). If omitted, auto-generated from `{{param}}` placeholders. |
| `annotations` | No | `ToolDefinition.annotations` | ToolAnnotations fields. `read_only` defaults true, `destructive` defaults false. |
| `output_schema` | No | `ToolDefinition.output_schema` | JSON Schema describing the tool's output structure. |
| `install` | No | Not in ToolDefinition | Installation instructions used when tool is not found via `which`. |
| `os` | No | Not in ToolDefinition | OS the tool was created on (auto-detected). Used for portability hints. |
| `python_version` | No | Not in ToolDefinition | Python version if the tool uses Python (auto-detected). |

### Directory structure

```
ea_root/
├── .mcp.json              # MCP server config
├── Tools/
│   ├── pdf_extract_text/
│   │   └── TOOL.md
│   ├── video_convert/
│   │   └── TOOL.md
│   └── analyze_data/
│       ├── TOOL.md
│       ├── script.py          # Python implementation (optional)
│       └── requirements.txt   # pip dependencies (optional)
└── Workspaces/{workspace_id}/
    └── Tools/
        └── project_tool/
            └── TOOL.md    # workspace overrides user by name
```

### Python-based tools

For tools that need more than a simple shell pipeline, the tool can use a **Python script** stored alongside the `TOOL.md`. The project uses **`uv`** as its Python toolchain (`uv run`, `uv add`) — all Python tool execution and dependency management should use `uv`.

```yaml
name: analyze_data
description: Analyze a CSV file and return summary statistics. Uses pandas.
command: uv run "{{tool_dir}}/script.py" "{{input}}" "{{output}}"
parameters:
  type: object
  properties:
    input:
      type: string
      description: Path to the CSV file
    output:
      type: string
      description: Path for the JSON results file
  required:
    - input
    - output
install:
  - uv add pandas
```

The `script.py` lives in the same directory (`{ea_root}/Tools/analyze_data/script.py`). The `{{tool_dir}}` placeholder is auto-resolved to the tool's directory at load time.

**Dependency management:**
- `pyproject.toml` or `requirements.txt` in the same directory lists dependencies
- Install via `uv add <package>` rather than `pip install <package>`
- `uv` is pre-installed and on PATH (the EA itself runs under `uv`)
- If `uv run` finds no venv, it auto-creates one

**Python version:**
- Use `uv run python3` (which respects `.python-version` if present)
- Defaults to Python 3.13 in this environment (as per `pyproject.toml: requires-python >=3.11,<3.14`)

**CLI Toolkit skill Phase 5 workflow for Python tools:**
1. Check `uv` availability: `which uv`, `uv --version`
2. Install required libraries: `uv add pandas`
3. Write `script.py` to `{ea_root}/Tools/{name}/`
4. Write `TOOL.md` with `command` using `uv run "{{tool_dir}}/script.py"`
5. Test: run the tool on a sample input
6. `tool_reload()` to register

### HybridDB tool index

On loop creation, all tools are ingested into a HybridDB database at `{ea_root}/Tools/.index/`:

```python
class ToolIndex:
    """Searchable index of all available tools using HybridDB."""

    def __init__(self, db_dir: Path):
        self.db = HybridDB(db_dir)
        self.db.create_table("tools", {
            "name": "TEXT UNIQUE",
            "description": "LONGTEXT",
            "search_text": "LONGTEXT",       # "name description" for FTS
            "namespace": "TEXT",              # "native", "custom", "mcp__{server}", "{namespace}"
            "tool_type": "TEXT",              # "native", "custom", "mcp", "connector"
            "definition_json": "LONGTEXT",    # ToolDefinition minus function
            "reconstruct": "TEXT",            # metadata to rebuild function on load
        })

    def index_tool(self, td: ToolDefinition, tool_type: str, namespace: str, reconstruct: dict | None = None):
        existing = self.db.query("tools", where="name = ?", params=(td.name,))
        row = {
            "name": td.name,
            "description": td.description,
            "search_text": f"{td.name} {td.description}",
            "namespace": namespace,
            "tool_type": tool_type,
            "definition_json": td.model_dump_json(exclude={"function"}),
            "reconstruct": json.dumps(reconstruct or {}),
        }
        if existing:
            self.db.update("tools", existing[0]["id"], row)
        else:
            self.db.insert("tools", row)

    def search(self, query: str, limit: int = 5) -> list[tuple[str, str]]:
        """Returns (name, description) of matching tools. Full ToolDefinition loaded on call."""
        rows = self.db.search("tools", "search_text", query, mode="hybrid", limit=limit)
        return [(r["name"], r["description"]) for r in rows]

    def get_definition(self, name: str) -> ToolDefinition | None:
        """Load full definition (minus function) by name. Caller reconstructs function."""
        rows = self.db.query("tools", where="name = ?", params=(name,))
        if not rows:
            return None
        return ToolDefinition(**json.loads(rows[0]["definition_json"]))

    def remove_tool(self, name: str) -> None:
        """Remove a tool from the index by name."""
        rows = self.db.query("tools", where="name = ?", params=(name,))
        if rows:
            self.db.delete("tools", rows[0]["id"])

    def list_all_names(self) -> list[str]:
        """List all tool names currently in the index."""
        rows = self.db.query("tools")
        return [r["name"] for r in rows]
```

**Reconstruction on lazy-load:** When the loop detects a tool is not inline, `_try_lazy_load()` is called:

1. Load `definition_json` from index via `get_definition(name)`
2. Load `reconstruct` metadata  
3. Rebuild function based on `tool_type`:
   - `"custom"`: rebuild with `_rebuild_custom_function()` — renders command template from `reconstruct`, runs via `subprocess.run(shell=True)`
   - `"mcp"`: resolve `server_name` + `mcp_tool_name` through `loop._mcp_bridge.get_tool_definition(name)`. If the session is dead, return error: `"MCP server '{server}' not connected. Run mcp_reload() to reconnect."`
   - `"connector"`: resolve through `loop._connectkit_bridge.get_tool_definition(namespace, tool_name)`. The bridge re-looks up the tool from its current runtime state (CLI or MCP backend). Returns error if the connector session has expired: `"Connector tool '{name}' session expired. Reconnect the service and try again."`
   - `"native"`: look up from `get_native_tools()` by name
4. Register the rebuilt `ToolDefinition` inline (`self._registry.register(td)`)
5. Add to recency set (`self._recently_used.add(name)`)
6. Execute the tool call against the now-registered definition

**Note on MCP tools:** `tool_reload` re-indexes MCP tools from the **current state** of MCPManager (already-connected sessions). To reconnect servers after `.mcp.json` changes, call `mcp_reload()` first, then `tool_reload()`. `mcp_reload()` is a separate core tool that reconnects MCP servers and updates the loop's `_mcp_bridge`; `tool_reload()` only reads from whatever bridge state exists.

**Note on connector tools:** Connector tools are indexed at loop creation from `ConnectKitBridge.discover()`. The `reconstruct` metadata stores `namespace` and `tool_name` so the function can be rebuilt from the live bridge on lazy-load. On connect/disconnect, `reset_user_sdk_loops()` clears the loop cache and `tool_reload()` re-indexes connector tools from the bridge's current state.

HybridDB provides:
- **FTS5** for keyword matching on `name` + `description`
- **ChromaDB** embeddings for semantic search if "what if I need to..." queries
- **Hybrid search** (`mode="hybrid"`) that combines both with configurable weighting

### Auto-loading on loop start

`runner.py` assembles all tools and builds the index:

1. **Load all sources** — native tools, custom tools (`Tools/*/TOOL.md`), MCP tools (MCPToolBridge), connector tools (ConnectKitBridge)
2. **Apply scope filtering** — `ItemScopeDB` filters all tool types uniformly
3. **Build HybridDB index** — index all tools by name + description:
   - **Native tools**: indexed as `tool_type="native"`, reconstruct metadata empty (lookup by name from `get_native_tools()`)
   - **Custom tools**: indexed as `tool_type="custom"`, reconstruct stores `command` template + `install` cmds
   - **MCP tools**: indexed as `tool_type="mcp"`, reconstruct stores `server_name` + `mcp_tool_name` for re-resolution through `MCPToolBridge`
   - **Connector tools**: indexed as `tool_type="connector"`, reconstruct stores `namespace` + `tool_name` for re-resolution through `ConnectKitBridge`
4. **Select core set** — 16 essential tools loaded inline (`shell_execute`, `files_read`, `files_write`, `files_edit`, `message_search`, `memory_search`, `time_get`, `web_search`, `web_scrape`, `todos_list`, `email_list`, `contacts_list`, `skills_load`, `subagent_delegate`, `mcp_reload`, `tool_reload`)
5. **Register `tool_search`** — always registered (core set always < total tools ~100+)
6. **Pass to AgentLoop** — only core + tool_search, everything else searchable
7. **Attach bridges** — `loop._connectkit_bridge` and `loop._mcp_bridge` are stored for lazy-load reconstruction

### `tool_search` tool

A synthetic tool always registered in the AgentLoop:

```python
@tool
def tool_search(
    description: str,
) -> str:
    """Search for a tool by describing what you need. Returns 3-5 matching tool names with descriptions.
    
    After finding the right tool, call it directly by name — it will be loaded for subsequent turns.
    
    Args:
        description: Describe the capability you need in detail. Use specific keywords about what the tool should do.
    
    Returns:
        Name and truncated description of matching tools
    """
```

Results include tool names + descriptions (truncated to 200 chars to avoid context bloat). When the agent calls a discovered tool by name, the loop detects it's not inline, reconstructs its `ToolDefinition` from the index (including the function via `reconstruct` metadata), and keeps it loaded for subsequent turns.

### `tool_reload` tool

A synthetic tool that rescans all tool sources and rebuilds the HybridDB index without a loop restart:

```python
@tool
def tool_reload(
    user_id: str = "default_user",
    workspace_id: str = "personal",
) -> str:
    """Reload and re-index all custom tools from disk. Use after creating, editing, or deleting a TOOL.md file.
    
    This applies to:
      - Custom tools (TOOL.md files in Tools/ directory)
      - MCP tools (.mcp.json changes)
      - Connector tools
    
    Native tools (built-in) are always available and don't need reloading.
    
    Returns:
        Summary of tools added, removed, or changed
    """
```

This enables the CLI Toolkit skill's **Phase 5 — Register** to work in the same conversation:
1. `files_write` creates `TOOL.md` (or `files_edit` modifies it, or `files_delete` removes it)
2. `tool_reload()` rescans all sources, diffs against previous index, rebuilds HybridDB
3. New tools are immediately searchable via `tool_search()`. Removed tools are gone from the index.
4. `tool_reload` evicts changed/removed tools from the loop's recency set, so stale inline copies are re-discovered on next use.
5. If called directly, it loads into recency set for rest of conversation

`tool_reload` also handles **deletion** of tools mid-conversation — it compares the current index contents against on-disk sources and removes entries for deleted `TOOL.md` files.

**Connector tools in `tool_reload`:** If the loop has a `_connectkit_bridge`, `tool_reload` also re-indexes connector tools by calling `connectkit_bridge.get_tool_definitions()` and indexing each as `tool_type="connector"` with reconstruct metadata storing `namespace` + `tool_name`. This ensures connector changes (new auth, new spec) are reflected without a full loop restart.

### Index change detection

The HybridDB index at `{ea_root}/Tools/.index/` persists between sessions. On loop start, `runner.py` checks whether re-indexing is needed:

```python
import hashlib

def _compute_source_hashes(tools_dir: Path, workspace_tools_dir: Path | None, mcp_config: Path, connectkit_bridge: Any | None = None) -> dict[str, str]:
    """Hash all tool sources for change detection."""
    hashes = {}
    # User-level custom tools
    if tools_dir.exists():
        for tool_dir in sorted(tools_dir.iterdir()):
            tool_file = tool_dir / "TOOL.md"
            key = f"user:{tool_dir.name}"
            if tool_file.exists():
                hashes[key] = hashlib.sha256(tool_file.read_bytes()).hexdigest()
            else:
                hashes[key] = ""
    # Workspace-level custom tools
    if workspace_tools_dir and workspace_tools_dir.exists():
        for tool_dir in sorted(workspace_tools_dir.iterdir()):
            tool_file = tool_dir / "TOOL.md"
            key = f"workspace:{tool_dir.name}"
            if tool_file.exists():
                hashes[key] = hashlib.sha256(tool_file.read_bytes()).hexdigest()
    # MCP tools
    if mcp_config.exists():
        hashes["mcp:config"] = hashlib.sha256(mcp_config.read_bytes()).hexdigest()
    # Connector tools: spec file + connected state
    ck_config = (tools_dir.parent if tools_dir.exists() else Path()) / ".connectkit.json"
    if ck_config.exists():
        hashes["connector:config"] = hashlib.sha256(ck_config.read_bytes()).hexdigest()
    if connectkit_bridge:
        connected = sorted(connectkit_bridge.connected_services())
        hashes["connector:state"] = hashlib.sha256(json.dumps(connected).encode()).hexdigest()
    return hashes
```

Sources checked:
- **Custom tools**: content hash of each `TOOL.md`, presence/absence of tool dirs
- **MCP tools**: content hash of `.mcp.json`
- **Native tools**: assumed static (Python code doesn't change at runtime)
- **Connector tools**: content hash of `.connectkit.json` spec + sorted set of connected service names (catches OAuth changes without file modification)

If hashes match → load existing HybridDB (instant).
If any hash changed → rebuild index fully, persist new hashes to `{ea_root}/Tools/.index/.index_hashes.json`.

### Recency tracking

The AgentLoop maintains a `recently_used` set of tool names. Any tool called in the current conversation is added to this set and loaded inline for subsequent turns. This handles the common pattern where a tool is used multiple times in a session.

On context compaction (summarization), the recency set is preserved so tools don't need to be re-discovered after summarization.

### CLI Toolkit skill

A new seed skill `cli-toolkit` (`src/skills_seed/cli-toolkit/SKILL.md`) guides the agent through the full lifecycle:

**Phase 1 — Discover** — Identify the right CLI tool using LLM knowledge, web search, or package manager search (`brew search`, `pip search`, `npm search`). Check `uname -s` and `uname -m` first to know the OS — macOS uses `brew`, Linux uses `apt`/`dnf`, Windows uses `winget`/`scoop`.

**Phase 2 — Install** — Check availability with `which <tool>`. If missing, install via appropriate package manager based on detected OS. Verify with `--version`.

**Phase 3 — Learn** — Run `tool --help` to understand flags, subcommands, and expected arguments.

**Phase 4 — Execute** — Run the command via `shell_execute`, check exit code, validate output. Retry up to 3 times with different flags on failure. If all 3 attempts fail, surface the error to the user.

**Phase 5 — Register** — Write a `TOOL.md` file to `{ea_root}/Tools/{name}/TOOL.md`. Choose a descriptive name and keyword-rich description for search discoverability. Include `os` (from `uname -s`) and if Python-based, `python_version` (from `python3 --version`) in the frontmatter so the tool is portable and debuggable. Then call `tool_reload()` to make it immediately available in the search index.

### Tool naming and descriptions

Tool names and descriptions are the primary search surface in HybridDB FTS5:

- **Names**: Imperative verb + domain context. `pdf_extract_text` > `pdf-tool`. `search_slack_messages` > `query_slack`.
- **Descriptions**: Include specific keywords, input/output patterns, and trigger contexts. "Search Slack messages by keyword, channel, or date range" > "Query Slack messages."
- **No prefix needed** — namespace is stored separately in the index, not embedded in the name.

### Scope filtering

`ItemScopeDB` applies uniformly to all tool types — native, custom, MCP (`mcp__{server}__{tool}`), and connector (`{namespace}__{tool}`). A tool excluded by scope is removed from both the inline set and the search index.

### Implementation plan

1. `src/storage/paths.py` — add `user_tools_dir()` and `workspace_tools_dir()`
2. `src/sdk/tools_custom.py` — `CustomToolRegistry` parses `TOOL.md`, builds `ToolDefinition` with `subprocess.run(shell=True)` wrapper
3. `src/sdk/tool_index.py` — `ToolIndex` wrapping HybridDB for all-tool search, with change detection
4. `src/sdk/tools_core/tool_search.py` — `tool_search` synthetic core tool
5. `src/sdk/tools_core/tool_reload.py` — `tool_reload` core tool that rescans all sources (custom TOOL.md + MCP bridge + connector bridge) and rebuilds index
6. `src/sdk/loop.py` — add recency tracking (`_recently_used` set), lazy-load `_try_lazy_load()` from index with reconstruct for all 4 tool types
7. `src/sdk/runner.py` — index ALL tool sources (native, custom, MCP, connector) into HybridDB; attach bridges to loop; include connector auth state in change detection hashes
8. `src/skills_seed/cli-toolkit/SKILL.md` — the discover/install/learn/execute/register workflow
9. Tests in `tests/sdk/test_tool_search.py`, `tests/sdk/test_custom_tools.py`, `tests/sdk/test_tool_lazy_load.py`