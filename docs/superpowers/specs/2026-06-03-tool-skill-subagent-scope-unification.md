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
| **All** | `All WS ✓` (green) | Enabled in every workspace — existing and future |
| **Selected** | `3 WS ✓` (green) | Enabled for specific workspaces only |
| **None** | `Off` (grey) | Disabled in all workspaces |

Each tool/skill/subagent toggle becomes a popup menu (tap the state badge):

```
○ Enable for all workspaces
● Enable for selected workspaces…  ← reveals workspace checklist
○ Disable
```

When "Selected" is chosen, a multi-select workspace checklist appears inline below
the item (or as a second popup). The user picks one or more workspaces to enable
the item for.

The `ScopeSwitcher` widget is removed from `ToolsPanel`, `SkillsSidebarPanel`, and
`SubagentsSidebarPanel`.

For Skills, this means skills stop being global-only — a user can now restrict a skill
to specific workspaces, same as tools.

For Subagents, same — agents can be scoped to the workspaces they're relevant for.

All three panels use identical state model and identical UX.

## Backend Changes

### API: Scope parameter on toggle endpoints

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

Backward compatibility: existing per-workspace enable/disable state migrates to
`scope=selected` with `workspace_ids=[current_ws]`. Existing global ("personal")
state migrates to `scope=all`.

## Frontend Changes

### `ToolsPanel`

- Remove `_scope` state and `ScopeSwitcher` widget
- Load tools once (global view), not per-scope
- Each tool row shows a tappable scope badge
- Badge tap opens a popup menu: All / Selected / None
- Choosing "Selected" opens a workspace multi-select dialog

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

On tap, shows:
1. Three radio options: All / Selected / None
2. If "Selected" is chosen, a scrollable checklist of available workspaces
   with checkboxes appears inline
3. A "Done" or "Apply" button confirms the selection

### Badge display

Each item row shows one of:

```
[All ✓]     — green, enabled everywhere
[3 WS ✓]    — green, enabled for 3 named workspaces
[Off]       — grey, disabled
```

The badge text is derived from the current scope state.

## Edge Cases

1. **New workspace created**: If a tool has `scope=all`, the new workspace inherits it
   automatically. If `scope=selected`, it does not (user must explicitly add it).

2. **Workspace deleted**: References to deleted workspaces in `workspace_ids` are
   cleaned up by the backend on delete.

3. **Workspace renamed**: Uses workspace ID internally, so rename has no effect.

4. **Default state for new items**: New skills/subagents default to `scope=selected`
   with the current workspace preselected (the most conservative default — user
   explicitly opts into broader scope).

5. **Bulk operations**: Future consideration — not in V1. The spec intentionally
   keeps each item independently configurable for maximum control.

## Non-Goals

- Bulk enable/disable for multiple items
- Per-item scope for Connectors and Settings (these remain user-level)
- Copy/import scope config between workspaces
- Role-based or team-level scoping (enterprise feature, out of scope)

## Migration Path

1. Add the `capabilities` table and scope API endpoints
2. Migrate existing per-workspace tool state to the new model:
   - If tool is enabled in personal scope → `scope=all`
   - If tool is enabled only in workspace W → `scope=selected`, `workspace_ids=[W]`
3. Update `ToolsPanel` → remove ScopeSwitcher, add per-item scope picker
4. Update `SkillsSidebarPanel` → add per-item scope picker
5. Update `SubagentsSidebarPanel` → add per-item scope picker
6. Remove `ScopeSwitcher` widget (or deprecate it)
