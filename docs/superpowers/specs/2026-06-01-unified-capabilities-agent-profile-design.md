# EA: Unified Capabilities & Agent Profile

2026-05-31

## Context

EA currently manages tools, skills, and subagents as three separate subsystems
with different storage formats, different APIs, and different scoping rules:

- **Tools**: static registry in `native_tools.py`, `GET /tools/names` returns flat list, no per-workspace enable/disable, no persistence
- **Skills**: YAML files per scope (user/workspace), full CRUD API with `is_loaded` flags
- **Subagents**: YAML `config.yaml` per agent under `Workspaces/{ws}/Subagents/{name}/`, uses `disallowed_tools` for tool filtering

No consistency. No unified view of "what can the agent do in this workspace."

## Summary

Three changes:

1. **`capabilities.yaml`** — unified per-scope config replacing three separate files. One file for tools + skills + subagents enable state per user and per workspace.

2. **`AgentProfile`** — standardized subagent definition format. Lives in its own OSS repo (`/Users/eddy/Developer/Python/AgentProfile`) — same pattern as `HybridDB` and `CoreMem`. Replaces loose `config.yaml`. Aligned with skill specification conventions. Drops `disallowed_tools`.

3. **Expanded API surface** — tool list with metadata, capabilities CRUD, agent profile CRUD. Same scope pattern as skills/subagents (user_id + workspace_id query params).

## capabilities.yaml

### Format

```yaml
# {ea_root}/capabilities.yaml          (user-level default)
version: 1

tools:
  files_read: true
  files_write: true
  files_delete: false
  shell_execute: false
  time_get: true
  browser_open: false
  # ... ~100 tools

skills:
  file-management: true
  data-analysis: true
  # ...

subagents:
  researcher: true
  planner: true
  # ...
```

```yaml
# {ea_root}/Workspaces/{ws}/capabilities.yaml  (workspace override)
version: 1

tools:
  files_delete: true          # enable destructive for this project
  browser_open: true
  shell_execute: false        # explicitly disable

skills:
  agent-browser: false        # disable browser skill

subagents:
  researcher: true
```

### Merge

Workspace overrides user. Missing keys inherit from user. Explicit `false` at
workspace level means "disabled for this workspace." The null escape hatch
reverts a key to default:

```
PATCH /capabilities  {"tools": {"files_read": null}}
→ removes files_read from workspace capabilities.yaml
→ reverts to user-level value (or default if absent)
```

### Defaults for new tools

When a new tool appears (EA update, MCP bridge) and is absent from both
user and workspace config, the default is derived from annotations:

| Annotation | Default |
|---|---|
| `read_only: true`, `destructive: false` | `true` (enabled) |
| `destructive: true`, `read_only: false` | `false` (disabled) |
| Both `true` | `false` (safety wins) |
| Both `false` | `true` |

This ensures new destructive tools (from an EA update or MCP) don't silently
become available without user approval.

### Runtime filter

At AgentLoop creation, the merged capabilities gates the tool registry:

```python
merged = merge(user_caps, workspace_caps)
loop_tools = {
    t for t in tool_registry
    if merged.tools.get(t.name, _tool_default(t.annotations)) is not False
}
```

Skills loaded into the loop are filtered identically. A skill's `allowed_tools`
must be a subset of the enabled tools — skills never expand access. If a skill
references a disabled tool, a warning is logged and the tool is stripped.

### Storage

Follows existing patterns:

```
{ea_root}/capabilities.yaml                  ← user scope
{ea_root}/Workspaces/{ws}/capabilities.yaml  ← workspace scope
```

Single file per scope. No migration needed for existing skills/subagents
on-disk — `capabilities.yaml` is additive, not a migration of existing files.

## AgentProfile

AgentProfile lives as a standalone OSS package (`agentprofile` on PyPI,
`/Users/eddy/Developer/Python/AgentProfile` on disk) following the same
extraction pattern as `HybridDB` and `CoreMem`. It provides the schema
and parser only — no EA-specific dependencies.

EA layers models.dev + skill registry validation on top in
`src/sdk/agent_profile.py`.

### Schema

```yaml
# Workspaces/{ws}/Subagents/{name}/profile.yaml
# (user-level: {ea_root}/Subagents/{name}/profile.yaml)
version: 1
name: researcher              # ^[a-zA-Z0-9_-]+$, max 64, unique per scope
description: |
  Research agent that searches the web and reads files.
model: openai:gpt-4o         # validated against models.dev
tools:                        # validated: must exist in tool registry
  - web_search
  - files_read
  - time_get
system_prompt: |
  You are a research assistant. When asked to research a topic,
  use web_search first, then files_read to save findings.
skills:
  - file-management
tags:
  - research
  - production
output_schema:                # JSON Schema, optional
  type: object
  properties:
    findings:
      type: array
    sources:
      type: array
provider_options:
  anthropic:
    thinking:
      type: enabled
      budget_tokens: 4000
handoff_instructions: |
  Researcher has found relevant sources. Review findings.
```

### Fields

| Field | Required | Description |
|-------|----------|-------------|
| `version` | ✅ | Schema version, always `1` |
| `name` | ✅ | Unique identifier, `^[a-zA-Z0-9_-]+$`, 1-64 chars |
| `description` | ✅ | What this agent does — used by parent agent to decide when to invoke |
| `model` | ✅ | Provider:model string, validated against models.dev |
| `tools` | ✅ | Tool names, must exist in registry |
| `system_prompt` | ✅ | Agent instructions |
| `skills` | No | Skill names, validated against registry |
| `tags` | No | Free-form UI organization |
| `output_schema` | No | JSON Schema for structured output |
| `provider_options` | No | Per-provider config (thinking blocks, etc.) |
| `handoff_instructions` | No | What parent sees on handoff |

### Validation

Core validation (AgentProfile package):
- `name`: alphanumeric + hyphen/underscore, 1-64 chars, unique per scope
- `version`: must be `1`
- `output_schema`: valid JSON Schema draft
- All required fields present

EA-specific validation (`src/sdk/agent_profile.py`):
- `model`: must resolve through models.dev, provider prefix must match known provider
- `tools`: each name must exist in `get_native_tool_names()`
- `skills`: each name must exist in skill registry
- `provider_options`: key must be a valid provider ID
- `skills.allowed_tools` content must be ⊆ profile.tools

### What moved

| From `AgentDef` (old) | To |
|---|---|
| `disallowed_tools` | Removed — replaced by `capabilities.yaml` |
| `workspace_id` | Derived from scope, not stored in profile |
| `max_llm_calls`, `cost_limit_usd`, `timeout_seconds` | Stay on `AgentDef` (harness runtime config, not profile identity) |
| `artifact_policy` | Stay on harness config |
| `mcp_config` | Stay on harness config |

### Tool gating chain

```
capabilities.yaml (user)
    ↓ merge
capabilities.yaml (workspace)
    ↓ gates
profile.tools (what agent wants)
    ↓ gates
skill.allowed_tools (what skill needs)
    = runtime tools
```

`profile.tools` can't add tools disabled in `capabilities.yaml`.
`skill.allowed_tools` can't add tools not in `profile.tools`.
A warning is logged when a skill's tool references are silently unavailable.

## API Endpoints

### Tools

```
GET  /tools                          → list all with metadata
GET  /tools/:name                    → single tool detail
PATCH /tools/:name                   → toggle enabled per scope
```

`GET /tools` response (category derived from tool naming convention `category_verb`):

```json
{
  "tools": [
    {
      "name": "files_read",
      "description": "Read file from filesystem",
      "category": "files",
      "annotations": {"read_only": true, "destructive": false},
      "parameters": {"type": "object", "properties": {...}},
      "enabled": true,
      "source": "native"
    }
  ],
  "categories": {
    "files": {"count": 12, "enabled": 8},
    "core": {"count": 5, "enabled": 3},
    "browser": {"count": 20, "enabled": 0},
    "apps": {"count": 13, "enabled": 5},
    "subagent": {"count": 10, "enabled": 0},
    "workspace": {"count": 5, "enabled": 5},
    "message": {"count": 4, "enabled": 4},
    "memory": {"count": 2, "enabled": 2},
    "mcp": {"count": 3, "enabled": 3},
    "web": {"count": 2, "enabled": 0},
    "research": {"count": 2, "enabled": 0},
    "skills": {"count": 6, "enabled": 6},
    "core": {"count": 3, "enabled": 3},
    "connectkit": {"count": 4, "enabled": 0}
  }
}
```

`PATCH /tools/:name` body (scope determined by `user_id` + `workspace_id` query params):

```json
{"enabled": true}
```

Writes to the current scope's `capabilities.yaml`. If scope is workspace and
the key doesn't exist, it's created as an override. If the value equals the
user-level value, the key is removed (keeps workspace config minimal).

### Capabilities

```
GET  /capabilities                   → merged capabilities for scope
PUT  /capabilities                   → full replace
PATCH /capabilities                  → partial merge
```

`PATCH` merge semantics: keys not in body are left unchanged. `null` deletes
a key (revert to user-level or default). `GET` returns the fully merged
capabilities object (user → workspace) — same shape as the YAML, no per-scope
breakout.

### Agents

```
GET  /agents                         → list AgentProfiles for scope
POST /agents                         → create
GET  /agents/:name                   → get profile + runtime state (task statuses, last run ts)
PATCH /agents/:name                  → update profile
DELETE /agents/:name                 → delete profile + cancel running tasks
POST /agents/:name/start             → start (existing, unchanged)
POST /agents/:name/cancel            → cancel (existing)
POST /agents/:name/instruct          → instruct (existing)
GET  /agents/:name/tasks             → task history (existing)
```

All endpoints accept `user_id` + `workspace_id` query params (same pattern
as skills/subagents).

When a subagent is disabled via `PATCH /capabilities` or `DELETE /agents`:
already-running tasks are allowed to finish (no kill), queued/pending tasks
are cancelled immediately, and new `start` requests are rejected.

## Data Flow

```
Flutter toggle → PATCH /tools/:name → capabilities.yaml saved
                                       ↓
                                  _reset_sdk_loop(user_id, workspace_id)
                                       ↓
                            Next turn: fresh AgentLoop with
                            merged capabilities ∩ tool_registry
                            (running subagents keep their frozen tool set)
```

At loop creation:

```python
def _build_loop_tools(workspace_id, user_id, tool_registry):
    # reads both capabilities.yaml files, workspace overrides user
    merged = load_and_merge_capabilities(user_id, workspace_id)
    return {
        t for t in tool_registry
        if merged.tools.get(t.name, _tool_default(t.annotations)) is not False
    }
```

## Flutter UI

Follows existing patterns — Skills/Subagents are tabs in Workspace panel.

New sidebar items: Tools, Skills, Subagents (currently commented out on line 43
of `desktop_layout.dart` — was always the intent).

Each sidebar item opens a full panel with:
- **Scope switcher** at top (User / Workspace toggle)
- **Search + counter** ("28 / 100 enabled")
- **Category-grouped list** with collapsible sections
- **Toggle switch** per item with annotation badges (read-only, destructive)
- **Inline expand** for detail (parameters, description, danger warnings)

Workspace tabs remain as convenience filters — showing only the current
workspace's overrides, with "inherited from user" indicators.

## Migration Path

1. Create `AgentProfile` OSS repo (Pydantic model + YAML parser, zero deps)
2. Add `capabilities.yaml` support (new file, doesn't touch existing configs)
3. Wire `_build_loop_tools` to filter tool registry by capabilities
4. Add expanded API endpoints
5. Add `src/sdk/agent_profile.py` (EA-specific validation layer)
6. Update `AgentDef` to read from `AgentProfile` files
7. Update Flutter app: new sidebar items, panels, provider
8. Remove `disallowed_tools` from `AgentDef` (backward compat: ignore field
   if present, warn)
9. Existing `SubagentCoordinator` methods (create, list_defs, load_def)
    continue working — they read `config.yaml` if `profile.yaml` absent
10. No data migration — old `config.yaml` files are still readable,
    new agents get `profile.yaml`

## Non-goals

- No auto-migration of existing agent configs to profile format
- No cross-workspace capability comparison UI
- No capability templates (pre-set configs for "coding workspace" vs "research workspace")
- No runtime limit controls in capabilities (max_llm_calls stays on AgentDef)
- No capabilities API for subagent-managed subagents (recursion guard stays)
