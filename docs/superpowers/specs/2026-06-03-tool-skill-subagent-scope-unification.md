# EA: Unified Tool / Skill / Subagent Scope Model

2026-06-03

## Context

Currently, the Tools panel has a `ScopeSwitcher` that toggles between "workspace" and
"personal" (user-level) views. Switching the scope swaps the entire tool list, which is
disorienting:

- You can't see what's enabled in "personal" while looking at a workspace view
- You have to toggle back and forth to compare or manage across scopes
- The "personal" vs "workspace" distinction is developer-centric, not user-centric
- Skills and Subagents don't have a scope switcher at all — inconsistent with Tools
- The split was introduced before workspaces could share tools, back when "personal"
  was the only way to apply settings globally

The goal is a single, unified model for enabling/disabling capabilities (tools, skills,
subagents) across workspaces — consistent UX across all three panels.

## Summary

Replace the `ScopeSwitcher` with a **three-state scope picker per item**:

| State | Badge (example) | Behavior |
|-------|-----------------|----------|
| **All** | `All ✓` (green) | Enabled in every workspace — existing and future |
| **Selected** | `3 WS ✓` (green) | Enabled for specific workspaces only. Tooltip on hover/long-press shows workspace names. |
| **None** | `Off` (grey) | Disabled in all workspaces |

Each tool/skill/subagent toggle becomes a popup menu (tap the state badge):

```
○ Enable for all workspaces
● Enable for selected workspaces…  ← reveals workspace checklist
○ Disable
```

When "Selected" is chosen, a modal dialog opens with a scrollable checklist of
all available workspaces and their checkboxes. User selects one or more, then
confirms with "Apply".

The `ScopeSwitcher` widget is removed from `ToolsPanel`, `SkillsSidebarPanel`, and
`SubagentsSidebarPanel`.

For Skills, this means skills stop being global-only — a user can now restrict a skill
to specific workspaces, same as tools.

For Subagents, same — agents can be scoped to the workspaces they're relevant for.

All three panels use identical state model and identical UX.

## Backend Changes

### GET endpoints

All three resource types return scope data alongside item metadata. Query by
workspace ID to filter — the backend resolves `scope=all` items automatically:

```
GET /tools?user_id=U&workspace_id=W

Response:
[
  {
    "name": "shell_execute",
    "description": "Execute shell commands",
    "category": "core",
    "enabled": true,              // computed for this workspace
    "scope": "all",               // all | selected | none
    "workspace_ids": [],          // when scope=selected, the list of workspace IDs
    "read_only": false,
    "destructive": true,
    …
  },
  {
    "name": "app_create",
    "description": "Create a new application",
    "category": "apps",
    "enabled": true,              // computed: scope=selected && W is in workspace_ids
    "scope": "selected",
    "workspace_ids": ["ws-1", "ws-2"],
    …
  },
  …
]
```

The `enabled` field is derived server-side — the frontend doesn't need to
compute intersection logic. Same pattern for `/skills` and `/subagents`.

### POST / PUT toggle endpoints

Current:

```
POST /tools/{name}?user_id=U&workspace_id=W    body: {enabled: true/false}
```

New:

```
POST /tools/{name}?user_id=U
body: {
  scope: "all" | "selected" | "none",
  workspace_ids: ["ws-1", "ws-2"]   // only when scope="selected"
}
```

Same for skills and subagents endpoints. The backend stores scope info per item,
keyed by user.

### Storage

A unified `capabilities` table (or per-resource tables) tracks scope per item:

```
capabilities:
  user_id, resource_type (tool/skill/subagent), resource_name,
  scope (all/selected/none), workspace_ids (json list)
```

Backward compatibility: during migration, existing per-workspace tool state is
converted per the rules in Migration Path below. Existing "personal" scope tools
(global, no workspace override) map to `scope=all`. Tools with explicit
per-workspace enable/disable map to `scope=selected` with the union of all
workspace IDs.

## Frontend Changes

### `ToolsPanel`

- Remove `_scope` state and `ScopeSwitcher` widget
- Load tools once per workspace (pass `workspace_id` query param)
- Each tool row shows a tappable scope badge that replaces the existing `Switch`
  widget — the badge communicates both enable state and scope in one tap target
- Badge tap opens a popup menu: All / Selected / None
- Choosing "Selected" opens a workspace multi-select dialog
- The header count shows "X / Y enabled" for the current workspace only

### `ScopePicker` (new shared widget)

A reusable widget used by Tools, Skills, and Subagents panels:

```dart
class ScopePicker extends StatelessWidget {
  final ScopeState scope;       // all, selected, none
  final List<String> workspaces; // ids of selected workspaces (when scope=selected)
  final List<Workspace> allWorkspaces; // all available workspaces
  final ValueChanged<ScopeChange> onChanged;
  …
}
```

On tap, shows a popup menu anchored to the badge:
1. Three radio options: All / Selected / None
2. If "Selected" is chosen, tapping it opens a modal dialog with a scrollable
   checklist of workspaces and an "Apply" button.

### Badge display

Each item row shows one of:

```
[All ✓]     — green, enabled everywhere
[3 WS ✓]    — green, enabled for 3 named workspaces
[Off]       — grey, disabled
```

The badge text is derived from the current scope state.

### Badge replaces Switch

Each item row currently has a `Switch` widget on the right (for tools: on/off toggle;
for skills/subagents: coming soon). With the scope model, the `Switch` is replaced
by a tappable `TextButton` or `Chip` showing the state badge. Tapping it reveals
the scope picker popup menu. The visual result is cleaner — one interactive element
per row instead of two (switch + scope indicator).

## Agent Loop Integration

When an agent loop is created for workspace W, the backend resolves available
tools/skills/subagents by querying:

```sql
SELECT * FROM capabilities
WHERE user_id = ?
  AND (
    scope = 'all'
    OR (scope = 'selected' AND workspace_ids CONTAINS ?)
  )
```

Items with `scope=none` or `scope=selected` without W in `workspace_ids`
are excluded from the agent's tool list. This replaces the current logic in
`create_sdk_loop()` that loads tools per-workspace from the old schema.

Skills are treated the same way — `SkillRegistry` filters loaded skills
against the capabilities table before injecting them into the agent.

Subagents follow the same pattern — available subagents are filtered by
workspace scope before the coordinator can invoke them.

## Edge Cases

1. **New workspace created**: Items with `scope=all` are automatically available.
   Items with `scope=selected` are not (user must add the workspace explicitly).
   Items with `scope=none` are not available anywhere.

2. **New tool added by SDK update**: Defaults to `scope=all` (opt-out — new
   capabilities are available everywhere until explicitly restricted). Same
   for new skills and subagents added via registry updates.

3. **Workspace deleted**: References to deleted workspaces in `workspace_ids` are
   cleaned up by the backend on delete. If no workspaces remain, the item
   automatically falls back to `scope=none`.

4. **Workspace renamed**: Uses workspace ID internally, so rename has no effect.

5. **Default state for new user-created items** (skills/subagents created by the
   user): Default to `scope=selected` with the current workspace preselected.
   This is the conservative default — user explicitly expands scope.

6. **Bulk operations**: Future consideration — not in V1. Each item is
   independently configurable.

7. **"Personal" workspace after migration**: Continues to exist for chat
   history, files, and conversations. For tools/skills/subagents, it has no
   special meaning — it's just another workspace in the picker list.

8. **Item enabled in both personal and specific workspace (conflict resolution)**:
   During migration, if a tool has state in both personal AND workspace W, the
   union is taken: `scope=selected` with `workspace_ids` containing all
   workspaces where it was explicitly enabled (ignoring personal).

## Non-Goals

- Bulk enable/disable for multiple items
- Per-item scope for Connectors and Settings (these remain user-level)
- Copy/import scope config between workspaces
- Role-based or team-level scoping (enterprise feature, out of scope)

## Migration Path

1. Add the `capabilities` table and scope API endpoints
2. Migrate existing per-workspace tool state:
   - If tool is enabled in personal scope AND has no per-workspace overrides →
     `scope=all`
   - If tool has per-workspace state (enabled in one or more specific workspaces)
     → `scope=selected` with the union of all enabled workspace IDs, ignoring
     the personal scope state
   - If tool is not enabled anywhere → `scope=none`
3. Add migration for skills and subagents (currently no per-workspace state —
   all existing items default to `scope=all`)
4. Update `ToolsPanel` → remove ScopeSwitcher, add per-item scope picker
5. Update `SkillsSidebarPanel` → add per-item scope picker
6. Update `SubagentsSidebarPanel` → add per-item scope picker
7. Remove `ScopeSwitcher` widget
