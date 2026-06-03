# EA: Canvas Tab + Unified Capabilities Panel

2026-06-04

## Context

The workspace panel currently has four bottom tabs (Files, Skills, Subagents, Tools) each with a
dedicated UI. When the agent needs to create a skill or subagent, there's no visual workspace — the
user types in chat, the agent generates, and the result appears as text. We want an agent-driven
visual workspace (Canvas) and a unified management view (Capabilities).

OpenAI calls this pattern **Canvas**, Claude calls it **Artifacts**. The user stays in the
conversation while a side panel renders structured output the agent generates — forms, cards,
results. We're adopting the same pattern using **HTML + WebView** with a `canvas-painting` skill
to ensure correctness.

## Summary

Three bottom tabs in the workspace panel:

| Tab | Purpose |
|-----|---------|
| **Canvas** | Agent-driven visual workspace. Renders HTML in a sandboxed WebView. Empty state when idle. |
| **Files** | Existing file viewer. Unchanged. |
| **Capabilities** | Unified Tools + Skills + Subagents management view. Collapsible sections, searchable, per-workspace ScopePicker per item. |

Sidebar keeps standalone panels (Tools, Skills, Subagents) for focused work. The Canvas is the
conversation's visual companion — whatever the agent generates appears there.

## Architecture

```
┌─ Chat Tab ────────────────────────────────────────────────┐
│ Text messages + tool calls                                 │
│ 🧠 skills_load → skill-creation loaded  (inline event)  │
└───────────────────────────────────────────────────────────┘

┌─ Canvas Tab ──────────────────────────────────────────────┐
│ HTML + WebView renderer                                     │
│ Agent generates HTML → WebView renders it                   │
│ Surfaces: forms, cards, lists, text blocks                 │
│ Multiple surfaces can coexist (e.g. skill form + result)   │
│ User interacts → postMessage bridge → agent updates       │
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
  └─ Loaded: skill-creation

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

### CSS Styling

The agent controls styling through any valid CSS method — inline `style` attributes,
`<style>` blocks, or external stylesheets. Three approaches, agent's choice:

```html
<!-- Inline (compact, self-contained) -->
<div style="padding:16px; font-family: var(--font); color: var(--text)">

<!-- <style> block (reusable, multi-component) -->
<style>
  .skill-form { padding: 16px; border: 1px solid var(--border); }
  .skill-form input { width: 100%; margin-bottom: 8px; }
</style>

<!-- External (for complex layouts, Tailwind CDN) -->
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/tailwindcss@...">
```

**Default stylesheet:** The WebView pre-injects a base theme with CSS custom properties
matching the app's design tokens (colors, spacing, typography). The agent references these
via `var(--primary)`, `var(--bg)`, `var(--text)`, etc. The `canvas-painting` skill knows
these variables.

**Isolation:** The WebView is sandboxed — CSS and JS cannot access the Flutter app's DOM,
local files, or system resources. External stylesheet URLs are allowed but executed in
the same sandbox.

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
  "html": "<div>...</div>"
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

The agent can generate multiple surfaces. Example: skill form + research results.
Surfaces stack vertically in a scrollable `ListView` in the Canvas tab, each
with its own `surface_id`. Each surface is a separate WebView instance.

### User Interaction

When the user interacts with a canvas component (types in a field, clicks a button), the action is
sent back to the agent via the chat WebSocket as a message. The agent can then update the canvas
in response.

### Auto-Activation

When the agent sends a `canvas_update` event (creates or updates a surface), the workspace panel
**automatically switches to the Canvas tab**. If the user is on Files or Capabilities, the Canvas
tab becomes active immediately. No notification badge, no "Check Canvas →" prompt — the canvas
appears as soon as the agent generates it.

If the user manually switches away while the agent is still painting, the canvas stays in its
current state. A new `canvas_update` event will switch back.

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
│   skill-creation     [All ✓]    autoresearch     [2 WS ✓]     │
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

For V1, the agent generates HTML via the normal LLM response. The backend detects
HTML destined for canvas using fenced code blocks:

```
```html:canvas
<div>...</div>
```
```

The `:canvas` language modifier distinguishes canvas HTML from regular code examples.
Any fenced block without `:canvas` is treated as a normal code block in chat, not
routed to the canvas. The backend strips the fence and sends the body as the
`html` field in `canvas_update`.

If the block has a `:skill-form` or `:subagent-form` modifier, the backend also
validates required fields against the `CANVAS_SCHEMAS` for that surface type.

### State sync

Canvas surfaces have state (form field values). V1 uses a simple request-response pattern:
- User edits a field in the WebView → `postMessage` sent to the Flutter layer → forwarded as
  a chat message to the agent
- Agent responds with an updated `canvas_update` event → WebView re-renders
- No optimistic updates, no real-time sync — each round trip is a full agent response

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
| `canvas_painting/SKILL.md` (new) | Seed skill: canvas-painting |
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

The banner is a compact inline widget: icon + "Loaded: skill-creation" text.

## Workspace Panel Bottom Tabs

Remove the old Skills, Subagents, Tools tab buttons. Replace with 3 tabs:

```
[🖼️ Canvas]   [📁 Files]   [⚙️ Capabilities]
```

The existing Files tab (`_WorkspacePanelTab.files`) remains. The Skills, Subagents, and Tools
enums are removed. `_WorkspacePanelTab` becomes: `{files, canvas, capabilities}`.

## Non-Goals

- AG-UI adoption (use existing WebSocket, revise later)
- A2UI / Open-JSON-UI (use HTML + WebView for simpler implementation)
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
`skill-creation`, `canvas-painting`.

## Migration Path

1. Create `CanvasTab` widget with WebView + postMessage bridge
2. Create `CapabilitiesTab` widget with unified sections
3. Create `canvas-painting` seed skill
4. Add `canvas_update` WebSocket event handler in backend
5. Update `workspace_panel.dart` tabs to Canvas | Files | Capabilities
6. Remove Skills, Subagents, Tools from workspace panel tab bar
7. Remove Files from sidebar (desktop + tablet)
8. Add `skills_load` inline event rendering in chat
9. Manual test + full test pass

## Open Questions

1. ~~Should the Canvas tab auto-focus?~~ → **Resolved: yes, auto-activate on `canvas_update`.**

2. Should the Capabilities tab show items from all workspaces or just the selected one?
   Leaning toward selected workspace only (dropdown at top to switch).

3. ~~How should the backend parse HTML from the agent's response?~~ → **Resolved:
   ```html:canvas fence blocks, with optional :skill-form/:subagent-form modifier.**
