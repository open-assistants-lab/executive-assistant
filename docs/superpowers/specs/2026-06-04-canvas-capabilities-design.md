# EA: Canvas Tab + Unified Capabilities Panel

2026-06-04

## Context

The workspace panel currently has four bottom tabs (Files, Skills, Subagents, Tools) each with a
dedicated UI. When the agent needs to create a skill or subagent, there's no visual workspace — the
user types in chat, the agent generates, and the result appears as text. We want an agent-driven
visual workspace (Canvas) and a unified management view (Capabilities).

OpenAI calls this pattern **Canvas**, Claude calls it **Artifacts**. The user stays in the
conversation while a side panel renders structured output the agent generates — forms, cards,
results. We're adopting the same pattern using **Open-JSON-UI** as the declarative component spec.

## Summary

Three bottom tabs in the workspace panel:

| Tab | Purpose |
|-----|---------|
| **Canvas** | Agent-driven visual workspace. Renders Open-JSON-UI components (forms, cards, lists) the agent generates. Empty state when idle. |
| **Files** | Existing file viewer. Unchanged. |
| **Capabilities** | Unified Tools + Skills + Subagents management view. Collapsible sections, searchable, per-workspace ScopePicker per item. |

Sidebar keeps standalone panels (Tools, Skills, Subagents) for focused work. The Canvas is the
conversation's visual companion — whatever the agent generates appears there.

## Architecture

```
┌─ Chat Tab ────────────────────────────────────────────────┐
│ Text messages + tool calls                                 │
│ 🧠 skills_load → skill-creator loaded  (inline event)     │
│ "Check Canvas →" when agent generates structured output    │
└───────────────────────────────────────────────────────────┘

┌─ Canvas Tab ──────────────────────────────────────────────┐
│ Open-JSON-UI renderer                                      │
│ Agent generates JSON → Flutter maps to native widgets      │
│ Surfaces: forms, cards, lists, text blocks                 │
│ Multiple surfaces can coexist (e.g. skill form + result)   │
│ User interacts → actions sent back to agent               │
└───────────────────────────────────────────────────────────┘

┌─ Files Tab ───────────────────────────────────────────────┐
│ Existing file viewer. Unchanged.                           │
└───────────────────────────────────────────────────────────┘

┌─ Capabilities Tab ────────────────────────────────────────┐
│ 🔧 Tools    ▸ 24/88 enabled                                │
│ 🧠 Skills   ▸ 3/6 enabled                                  │
│ 🤖 Subagents ▸ 1/2 enabled                                 │
│ ScopePicker per item, search across all types              │
└───────────────────────────────────────────────────────────┘
```

Sidebar: Connection | Tools | Skills | Subagents | Settings (no Files — Files is ws-scoped, belongs
in the workspace panel tabs).

## Sidebar Changes

Remove **Files** from sidebar. Files are workspace-scoped and accessed via the workspace panel's
Files tab.

| Before | After |
|--------|-------|
| Files, Connection, Tools, Skills, Subagents, Settings | Connection, Tools, Skills, Subagents, Settings |

## Chat Changes

When the agent loads a skill via `skills_load`, render an inline event in the conversation stream
(like tool calls today):

```
User: Create a skill for commit messages

🔧 skills_load
  └─ Loaded: skill-creator

Agent: I can help you create skills. Let me ask a few questions...
```

No persistent header in the Canvas tab. No loaded-skill indicator in the UI chrome. The event is a
moment in the conversation.

## Canvas Tab

### HTML Rendering

The agent generates HTML (with optional inline CSS or `<style>` blocks). A Flutter
`WebView` (`webview_flutter`) renders it in a sandboxed iframe. A JavaScript
`postMessage` bridge handles user interactions back to the agent.

```html
<!-- Agent generates: -->
<div class="skill-form" style="padding:16px;font-family:system-ui">
  <h2>New Skill</h2>
  <input name="name" placeholder="Name" value="commit-writer">
  <textarea name="description" placeholder="Description"></textarea>
  <textarea name="content" placeholder="Skill instructions" rows="8"></textarea>
  <button onclick="postMessage({action:'save',fields:{...}})">Save</button>
</div>
```

**Why HTML over Open-JSON-UI or A2UI:**
- Agents already know HTML/CSS well — no protocol to learn
- No component catalog to build and maintain
- No renderer mapping to implement — `webview_flutter` exists
- Unlimited flexibility — any UI the agent can describe
- `canvas-painting` skill provides templates and validation

#### Required Fields Validation

The `canvas-painting` skill includes field schemas for known surface types.
The system prompt embeds these schemas so the agent always generates complete forms.

Backend validation before sending `canvas_update` to the frontend:

```python
CANVAS_SCHEMAS = {
    "skill-form": ["name", "description", "content"],
    "subagent-form": ["name", "description", "model", "system_prompt"],
    "result-card": [],  # free-form
}
```

### WebSocket Events

Single new event type `canvas_update` on the existing WebSocket:

```json
{
  "type": "canvas_update",
  "surface_id": "skill-form-abc",
  "action": "create" | "update" | "destroy",
  "spec": { "components": [...] }
}
```

- `surface_id` — unique ID for this canvas surface (supports multiple concurrent surfaces)
- `action: "create"` — new surface, renderer creates a fresh canvas area
- `action: "update"` — replace surface content (agent regenerates)
- `action: "destroy"` — remove surface (user cancels, agent finishes)

### Empty State

When no canvas content is active, the Canvas tab shows a centered empty state:

```
┌─ Canvas ────────────────────────────────────────┐
│                                                  │
│                  🖼️                              │
│        Agent-generated content appears here      │
│                                                  │
└──────────────────────────────────────────────────┘
```

### Multiple Surfaces

The agent can generate multiple surfaces. Example: skill form + research results side by side.
Surfaces stack vertically in the Canvas tab, each with its own `surface_id`.

### User Interaction

When the user interacts with a canvas component (types in a field, clicks a button), the action is
sent back to the agent via the chat WebSocket as a message. The agent can then update the canvas
in response.

## Capabilities Tab

### Layout

```
┌─ Capabilities ─────────────────────────────────────────────┐
│ [Search all...]                     Workspace: marketing  ▼ │
│                                                              │
│ ▸ 🔧 Tools (24/88 enabled)                                   │
│   email_connect     [All ✓]    shell_execute    [All ✓]      │
│   app_create        [Off]      time_get         [All ✓]     │
│   ... (scrollable, shows first 5 then expands)               │
│                                                              │
│ ▸ 🧠 Skills (3/6 enabled)                                     │
│   skill-creator     [All ✓]    autoresearch     [2 WS ✓]     │
│   commit-writer     [Off]                                    │
│                                                              │
│ ▸ 🤖 Subagents (1/2 enabled)                                  │
│   researcher        [All ✓]    code-reviewer    [Off]        │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### Behavior

- **Collapsible sections** — each type (Tools, Skills, Subagents) is an `ExpansionTile`, expanded
  by default. Expand/collapse persists in-session.
- **Search** — searches across all three types simultaneously (name + description). Type erases
  section boundaries — results from all three types interleaved.
- **ScopePicker** — same `[All ✓] [Select] [Off]` segmented control per item. Respects
  `item_scopes` table.
- **Count** — shows "X/Y enabled" per section where Y is total count. Enabled = items with
  `scope=all` or `scope=selected && workspace matches`.
- **Workspace selector** — dropdown at top right to switch workspace context. Defaults to current
  workspace from sidebar.

### Data Source

Same API endpoints already in use — `GET /tools`, `GET /skills`, `GET /subagents` — all return
per-item `scope` and `workspace_ids`.

## Backend Changes

### New WebSocket event: `canvas_update`

Add handler to broadcast `canvas_update` events alongside existing `text_start`, `tool_start`, etc.
Events are scoped to `user_id` + `conversation_id`.

### Agent tool: `canvas_create` (optional future)

For V1, the agent generates Open-JSON-UI via the normal LLM response, parsed by the backend, and
forwarded as `canvas_update`. A future `canvas_create` tool could provide a structured interface
for the agent to create surfaces explicitly.

### State sync

Canvas surfaces have state (form field values, checkbox states). State flows through AG-UI pattern
(not yet adopted — custom for V1, AG-UI later):
- `canvas_state` event for initial state dump
- Field changes sent as user messages back to the agent
- Agent responds with updated `canvas_update` events

## Frontend Changes

### Files changed

| File | Change |
|------|--------|
| `desktop_layout.dart` | Remove Files from sidebar |
| `tablet_rail.dart` | Remove Files from sidebar |
| `workspace_panel.dart` | Replace 4 tabs with 3 (Canvas, Files, Capabilities) |
| `canvas_tab.dart` (new) | WebView widget with postMessage bridge |
| `capabilities_tab.dart` (new) | Unified Tools/Skills/Subagents view |
| `chat_screen.dart` | Render skills_load as inline event |
| `canvas_painter.dart` (new) | Backend: canvas-painting skill (SKILL.md seed) |
| `skills_seed/skill-creation/` | Renamed from skill-creator, SKILL.md updated |

### Widget: `CanvasTab`

Uses `webview_flutter` to render agent-generated HTML in a sandboxed WebView. A
JavaScript `postMessage` bridge relays user interactions (button clicks, form
submissions) back to the agent via the existing WebSocket.

```dart
class CanvasTab extends ConsumerStatefulWidget {
  // Listens for canvas_update events on WebSocket
  // Each surface renders as a WebView with unique surface_id
  // postMessage bridge sends user actions back to chat
}
```

### Widget: `CapabilitiesTab`

Reuses existing `ToolsPanel._ToolRow`, `SkillsSidebarPanel._buildRow`, and
`SubagentsSidebarPanel._buildRow` patterns. Fetches all three resource types in parallel.

```dart
class CapabilitiesTab extends ConsumerStatefulWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final tools = ref.watch(toolsProvider);
    final skills = ref.watch(skillsProvider);
    final subagents = ref.watch(subagentsProvider);
    final search = useTextEditingController();
    
    return Column(
      children: [
        SearchField(search: search),
        WorkspaceDropdown(),
        Expanded(
          child: ListView(
            children: [
              _Section('Tools', tools),
              _Section('Skills', skills),
              _Section('Subagents', subagents),
            ],
          ),
        ),
      ],
    );
  }
}
```

### Chat: skills_load event

In the chat message stream, interleave `skills_load` events alongside tool calls:

```dart
// In chat_screen.dart message builder
if (event.type == 'skills_load') {
  return SkillsLoadBanner(event: event);
}
```

The banner is a compact inline widget: icon + "Loaded: skill-creator" text.

## Workspace Panel Bottom Tabs

Remove the old Skills, Subagents, Tools tab buttons. Replace with 3 tabs:

```
[🖼️ Canvas]   [📁 Files]   [⚙️ Capabilities]
```

The existing Files tab (`_WorkspacePanelTab.files`) remains. The Skills, Subagents, and Tools
enums are removed. `_WorkspacePanelTab` becomes: `{files, canvas, capabilities}`.

## Non-Goals

- AG-UI adoption (use existing WebSocket, revise later)
- A2UI / Open-JSON-UI adoption (use HTML + WebView for simpler implementation)
- `canvas_create` agent tool (agent generates HTML inline, backend wraps in canvas_update)
- Full bidirectional state sync (V1: user actions → agent → updated canvas, no real-time
  optimistic updates)
- Capabilities bulk operations (scope picker per item only)
- Canvas for arbitrary HTML/iframes (sandboxed WebView only)

### Canvas Skill

A new seed skill `canvas-painting` ships alongside `skill-creation`. It provides:

- HTML/CSS templates for common surface types (skill forms, subagent forms, result cards)
- Required-field schemas for each surface type
- postMessage bridge pattern documentation
- Field validation rules

Skills follow the `{domain}-{action}` naming pattern:
`skill-creation`, `canvas-painting`, `subagent-creation`

## Migration Path

1. Create `CanvasTab` widget with Open-JSON-UI renderer
2. Create `CapabilitiesTab` widget with unified sections
3. Add `canvas_update` WebSocket event handler in backend
4. Update `workspace_panel.dart` tabs to Canvas | Files | Capabilities
5. Remove Skills, Subagents, Tools from workspace panel tab bar
6. Remove Files from sidebar (desktop + tablet)
7. Add `skills_load` inline event rendering in chat
8. Manual test + full test pass

## Open Questions

1. Should the Canvas tab auto-focus (switch to it) when the agent generates content, or should
   the user click "Check Canvas →" manually? Leaning toward a notification badge on the Canvas
   tab + optional auto-switch.

2. Should the Capabilities tab show items from all workspaces or just the selected one?
   Leaning toward selected workspace only (dropdown at top to switch).

3. Open-JSON-UI spec: use the full spec or a subset? Leaning toward the subset in this spec
   (text, text_field, text_area, checkbox, dropdown, button, section, card). Expand as needed.
