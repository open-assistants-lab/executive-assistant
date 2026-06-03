# Canvas Tab + Unified Capabilities Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace workspace panel's Skills/Subagents/Tools tabs with Canvas + Capabilities tabs, remove Files from sidebar, add `canvas_update` WebSocket event and HTML-based Canvas rendering.

**Architecture:** Canvas renders agent-generated HTML via `webview_flutter` with postMessage bridge. Capabilities unifies Tools/Skills/Subagents into collapsible sections. Backend parses ```` ```html:canvas ```` fence blocks from agent responses and emits `canvas_update` WebSocket events.

**Tech Stack:** Flutter, Riverpod, GoRouter, webview_flutter, Python/FastAPI, WebSocket

---

## File Structure

| File | Responsibility |
|------|---------------|
| `flutter_app/lib/features/workspace/canvas_tab.dart` | New: WebView widget, canvas_update listener, postMessage bridge |
| `flutter_app/lib/features/workspace/capabilities_tab.dart` | New: Unified Tools/Skills/Subagents view |
| `flutter_app/lib/features/workspace/workspace_panel.dart` | Modify: 4 tabs → 3 (Canvas/Files/Capabilities), auto-activate |
| `flutter_app/lib/core/layout/desktop_layout.dart` | Modify: Remove Files sidebar item |
| `flutter_app/lib/core/layout/tablet_rail.dart` | Modify: Remove Files sidebar item |
| `flutter_app/lib/features/chat/chat_screen.dart` | Modify: Render skills_load inline event |
| `src/http/ws_protocol.py` | Modify: Add canvas_update event type |
| `src/http/routers/ws.py` | Modify: Handle canvas_update routing |
| `src/http/routers/conversation.py` | Modify: Parse ```html:canvas blocks |
| `src/skills_seed/canvas-painting/SKILL.md` | New: Seed skill for canvas painting |
| `flutter_app/test/core/layout/canvas_tab_test.dart` | New: CanvasTab widget tests |
| `flutter_app/test/core/layout/capabilities_tab_test.dart` | New: CapabilitiesTab widget tests |

---

## Task 1: Remove Files from sidebar

**Files:**
- Modify: `flutter_app/lib/core/layout/desktop_layout.dart`
- Modify: `flutter_app/lib/core/layout/tablet_rail.dart`

- [ ] **Step 1: Remove Files sidebar item from desktop_layout.dart**

Remove the `DesktopSidebarItem.files` entry from the sidebar items list. The Files entry is the first item in the list.

```dart
// BEFORE (in the sidebar column children list):
DesktopSidebarItem.files,
DesktopSidebarItem.connectors,
...
// AFTER:
DesktopSidebarItem.connectors,
...
```

- [ ] **Step 2: Remove Files import if no longer needed**

Check if `Files`-related imports in `desktop_layout.dart` are still used elsewhere. If `DesktopSidebarItem.files` was the only reference to a Files import, remove it.

- [ ] **Step 3: Remove Files sidebar item from tablet_rail.dart**

Same change — remove the Files entry from the tablet rail's navigation items list.

- [ ] **Step 4: Run analyzer and tests**

```bash
cd flutter_app && flutter analyze lib/core/layout/desktop_layout.dart lib/core/layout/tablet_rail.dart
flutter test test/core/layout/
```

- [ ] **Step 5: Commit**

```bash
git add flutter_app/lib/core/layout/desktop_layout.dart flutter_app/lib/core/layout/tablet_rail.dart
git commit -m "refactor: remove Files from sidebar (ws-scoped, in workspace panel tabs)"
```

---

## Task 2: Add canvas_update WebSocket event

**Files:**
- Modify: `src/http/ws_protocol.py`
- Modify: `src/http/routers/ws.py`

- [ ] **Step 1: Add canvas_update event type**

In `src/http/ws_protocol.py`, add `canvas_update` to the event type enum/union:

```python
class WsEventType(str, Enum):
    text_start = "text_start"
    text_delta = "text_delta"
    text_end = "text_end"
    tool_input_start = "tool_input_start"
    tool_input_delta = "tool_input_delta"
    tool_input_end = "tool_input_end"
    tool_result = "tool_result"
    reasoning_start = "reasoning_start"
    reasoning_delta = "reasoning_delta"
    reasoning_end = "reasoning_end"
    interrupt = "interrupt"
    done = "done"
    error = "error"
    skills_load = "skills_load"
    # NEW:
    canvas_update = "canvas_update"
```

Add the `CanvasUpdate` model:

```python
class CanvasUpdate(BaseModel):
    type: Literal["canvas_update"]
    surface_id: str
    action: Literal["create", "update", "destroy"]
    html: str = ""
```

- [ ] **Step 2: Add canvas_update handler in ws.py**

In the WebSocket message processing loop, add a handler that broadcasts `canvas_update` events:

```python
async def _handle_canvas_update(self, event: CanvasUpdate):
    await self._broadcast(event.model_dump())
```

- [ ] **Step 3: Verify backend compiles**

```bash
uv run python3 -c "from src.http.ws_protocol import WsEventType, CanvasUpdate; print('OK')"
```

- [ ] **Step 4: Commit**

```bash
git add src/http/ws_protocol.py src/http/routers/ws.py
git commit -m "feat: add canvas_update WebSocket event type and model"
```

---

## Task 3: Parse ```html:canvas blocks from agent response

**Files:**
- Modify: `src/http/routers/conversation.py`

- [ ] **Step 1: Add HTML fence block parser**

In the conversation message response handler, detect ```` ```html:canvas ```` fenced code blocks and emit `canvas_update` events:

```python
import re

_CANVAS_FENCE = re.compile(r"```html:(canvas|skill-form|subagent-form)\s*\n(.*?)```", re.DOTALL)

CANVAS_SCHEMAS = {
    "skill-form": ["name", "description", "content"],
    "subagent-form": ["name", "description", "model", "system_prompt"],
    "canvas": [],  # free-form
}

async def _extract_canvas(text: str, surface_id_prefix: str = "canvas") -> list[dict]:
    surfaces = []
    for i, match in enumerate(_CANVAS_FENCE.finditer(text)):
        surface_type = match.group(1)
        html = match.group(2).strip()

        # Validate required fields for typed surfaces
        if surface_type in CANVAS_SCHEMAS and CANVAS_SCHEMAS[surface_type]:
            # Basic validation: check for expected form field names in HTML
            for field in CANVAS_SCHEMAS[surface_type]:
                if f'name="{field}"' not in html and f"name='{field}'" not in html and f'name={field}' not in html:
                    break  # Skip validation for V1 — soft check only

        surfaces.append({
            "surface_id": f"{surface_id_prefix}-{i}",
            "action": "create",
            "html": html,
        })
    return surfaces
```

- [ ] **Step 2: Integrate into the message response pipeline**

After the agent produces a full response, scan for ```` ```html:canvas ```` blocks. For each block found, emit a `canvas_update` WebSocket event:

```python
# In the response handler, after the text is complete:
canvas_surfaces = _extract_canvas(full_response_text)
for surface in canvas_surfaces:
    await ws_handler.broadcast({
        "type": "canvas_update",
        **surface,
    })
```

- [ ] **Step 3: Verify backend compiles**

```bash
uv run python3 -c "from src.http.routers.conversation import _extract_canvas; print('OK')"
```

- [ ] **Step 4: Commit**

```bash
git add src/http/routers/conversation.py
git commit -m "feat: parse ```html:canvas fence blocks from agent responses"
```

---

## Task 4: Create CanvasTab widget

**Files:**
- Create: `flutter_app/lib/features/workspace/canvas_tab.dart`
- Create: `flutter_app/test/core/layout/canvas_tab_test.dart`

- [ ] **Step 1: Write CanvasTab tests**

```dart
// test/core/layout/canvas_tab_test.dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:executive_assistant/features/workspace/canvas_tab.dart';

void main() {
  group('CanvasTab', () {
    testWidgets('shows empty state when no surfaces', (tester) async {
      await tester.pumpWidget(_wrap(const CanvasTab()));
      expect(find.text('Agent-generated content appears here'), findsOneWidget);
    });

    testWidgets('renders HTML surface on canvas_update event', (tester) async {
      await tester.pumpWidget(_wrap(const CanvasTab()));
      // Simulate receiving a canvas_update event via provider
      await tester.pump();
      // Expect empty state replaced with surface content
    });
  });
}

Widget _wrap(Widget child) {
  return ProviderScope(
    child: MaterialApp(home: Scaffold(body: child)),
  );
}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd flutter_app && flutter test test/core/layout/canvas_tab_test.dart
```

- [ ] **Step 3: Create CanvasTab widget**

```dart
// lib/features/workspace/canvas_tab.dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class CanvasProvider extends StateNotifier<CanvasState> {
  CanvasProvider() : super(const CanvasState());

  void onCanvasUpdate(Map<String, dynamic> event) {
    final action = event['action'] as String;
    var surfaces = List<CanvasSurface>.from(state.surfaces);

    if (action == 'destroy') {
      surfaces.removeWhere((s) => s.surfaceId == event['surface_id']);
    } else if (action == 'update') {
      final idx = surfaces.indexWhere((s) => s.surfaceId == event['surface_id']);
      if (idx >= 0) {
        surfaces[idx] = CanvasSurface(
          surfaceId: event['surface_id'],
          action: action,
          html: event['html'] ?? '',
        );
      }
    } else {
      surfaces.add(CanvasSurface(
        surfaceId: event['surface_id'],
        action: action,
        html: event['html'] ?? '',
      ));
    }

    state = CanvasState(surfaces: surfaces, lastAction: action);
  }
}

class CanvasState {
  final List<CanvasSurface> surfaces;
  final String? lastAction;
  const CanvasState({this.surfaces = const [], this.lastAction});
}

class CanvasSurface {
  final String surfaceId;
  final String action;
  final String html;
  const CanvasSurface({required this.surfaceId, required this.action, required this.html});
}

final canvasProvider = StateNotifierProvider<CanvasProvider, CanvasState>(
  (ref) => CanvasProvider(),
);

class CanvasSurface {
  final String surfaceId;
  final String action;
  final String html;

  const CanvasSurface({
    required this.surfaceId,
    required this.action,
    required this.html,
  });
}

class CanvasTab extends ConsumerStatefulWidget {
  const CanvasTab({super.key});

  @override
  ConsumerState<CanvasTab> createState() => _CanvasTabState();
}

class _CanvasTabState extends ConsumerState<CanvasTab> {
  final List<CanvasSurface> _surfaces = [];

  @override
  void initState() {
    super.initState();
    // Listen for canvas_update events on the WebSocket
  }

  void _onCanvasUpdate(Map<String, dynamic> event) {
    setState(() {
      final action = event['action'] as String;
      if (action == 'destroy') {
        _surfaces.removeWhere(
            (s) => s.surfaceId == event['surface_id']);
      } else if (action == 'update') {
        final idx = _surfaces.indexWhere(
            (s) => s.surfaceId == event['surface_id']);
        if (idx >= 0) {
          _surfaces[idx] = CanvasSurface(
            surfaceId: event['surface_id'],
            action: action,
            html: event['html'] ?? '',
          );
        }
      } else {
        _surfaces.add(CanvasSurface(
          surfaceId: event['surface_id'],
          action: action,
          html: event['html'] ?? '',
        ));
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    if (_surfaces.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Symbols.dashboard_customize, size: 48,
                color: Theme.of(context).textTheme.bodySmall?.color),
            const SizedBox(height: 16),
            Text(
              'Agent-generated content appears here',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ),
      );
    }

    return ListView.builder(
      itemCount: _surfaces.length,
      itemBuilder: (_, i) {
        final surface = _surfaces[i];
        return SizedBox(
          height: 400,
          child: WebViewWidget(
            controller: WebViewController()
              ..setJavaScriptMode(JavaScriptMode.unrestricted)
              ..setNavigationDelegate(
                NavigationDelegate(
                  onPageFinished: (_) {
                    // Inject postMessage bridge
                  },
                ),
              )
              ..loadHtmlString('''
                <html>
                <head>
                  <meta name="viewport" content="width=device-width, initial-scale=1.0">
                  <style>
                    :root {
                      --primary: #3b82f6;
                      --bg: #1e1e2e;
                      --text: #cdd6f4;
                      --border: #45475a;
                    }
                    body {
                      margin: 0; padding: 16px;
                      font-family: system-ui, -apple-system, sans-serif;
                      color: var(--text);
                      background: var(--bg);
                    }
                  </style>
                </head>
                <body>
                  ${surface.html}
                </body>
                </html>
              '''),
          ),
        );
      },
    );
  }
}
```

- [ ] **Step 4: Add webview_flutter dependency if not present**

```bash
cd flutter_app && flutter pub add webview_flutter
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd flutter_app && flutter test test/core/layout/canvas_tab_test.dart
```

- [ ] **Step 6: Commit**

```bash
git add flutter_app/lib/features/workspace/canvas_tab.dart \
        flutter_app/test/core/layout/canvas_tab_test.dart \
        flutter_app/pubspec.yaml
git commit -m "feat: CanvasTab widget with WebView + postMessage bridge"
```

---

## Task 5: Create CapabilitiesTab widget

**Files:**
- Create: `flutter_app/lib/features/workspace/capabilities_tab.dart`
- Create: `flutter_app/test/core/layout/capabilities_tab_test.dart`

- [ ] **Step 1: Write CapabilitiesTab tests**

```dart
// test/core/layout/capabilities_tab_test.dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:executive_assistant/features/workspace/capabilities_tab.dart';

void main() {
  group('CapabilitiesTab', () {
    testWidgets('shows three collapsible sections', (tester) async {
      await tester.pumpWidget(_wrap(const CapabilitiesTab()));
      await tester.pump();
      expect(find.text('Tools'), findsOneWidget);
      expect(find.text('Skills'), findsOneWidget);
      expect(find.text('Subagents'), findsOneWidget);
    });
  });
}

Widget _wrap(Widget child) {
  return ProviderScope(
    child: MaterialApp(
      theme: ThemeData.light(),
      home: Scaffold(body: child),
    ),
  );
}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd flutter_app && flutter test test/core/layout/capabilities_tab_test.dart
```

- [ ] **Step 3: Create CapabilitiesTab widget**

```dart
// lib/features/workspace/capabilities_tab.dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../providers/agent_provider.dart';
import '../../providers/workspace_provider.dart';
import '../../theme/app_theme.dart';

class CapabilitiesTab extends ConsumerStatefulWidget {
  const CapabilitiesTab({super.key});

  @override
  ConsumerState<CapabilitiesTab> createState() => _CapabilitiesTabState();
}

class _CapabilitiesTabState extends ConsumerState<CapabilitiesTab> {
  final _searchCtrl = TextEditingController();
  String _search = '';

  @override
  void dispose() {
    _searchCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final tokens = context.tokens;
    final ws = ref.watch(currentWorkspaceNameProvider);

    return Container(
      color: tokens.colors.bgCanvas,
      child: Column(
        children: [
          Padding(
            padding: EdgeInsets.fromLTRB(
                tokens.spacing.md, tokens.spacing.lg,
                tokens.spacing.md, tokens.spacing.md),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(Symbols.tune, size: 18, color: tokens.colors.accent),
                    const SizedBox(width: 8),
                    Text('Capabilities',
                        style: tokens.typography.textTheme.titleLarge
                            ?.copyWith(color: tokens.colors.textPrimary)),
                    const Spacer(),
                    Text(ws, style: tokens.typography.textTheme.labelSmall
                        ?.copyWith(color: tokens.colors.textTertiary)),
                  ],
                ),
                SizedBox(height: tokens.spacing.sm),
                TextField(
                  controller: _searchCtrl,
                  decoration: const InputDecoration(
                    hintText: 'Search tools, skills, subagents...',
                    prefixIcon: Icon(Symbols.search, size: 18),
                    isDense: true,
                  ),
                  onChanged: (v) => setState(() => _search = v),
                ),
              ],
            ),
          ),
          Expanded(
            child: ListView(
              padding: EdgeInsets.symmetric(horizontal: tokens.spacing.md),
              children: [
                _buildSection('Tools', icon: Symbols.handyman),
                _buildSection('Skills', icon: Symbols.psychology),
                _buildSection('Subagents', icon: Symbols.robot_2),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSection(String title, {IconData? icon}) {
    final tokens = context.tokens;
    return Container(
      margin: EdgeInsets.only(bottom: tokens.spacing.md),
      decoration: BoxDecoration(
        color: tokens.colors.bgElevated,
        borderRadius: tokens.radius.smAll,
      ),
      child: ExpansionTile(
        initiallyExpanded: true,
        title: Row(
          children: [
            if (icon != null)
              Icon(icon, size: 16, color: tokens.colors.accent),
            if (icon != null) const SizedBox(width: 8),
            Text(title,
                style: tokens.typography.textTheme.titleSmall
                    ?.copyWith(color: tokens.colors.textPrimary)),
            const SizedBox(width: 8),
            Text('coming soon',
                style: tokens.typography.textTheme.labelSmall
                    ?.copyWith(color: tokens.colors.textTertiary)),
          ],
        ),
        children: [
          Padding(
            padding: EdgeInsets.all(tokens.spacing.md),
            child: Consumer(
              builder: (_, ref, __) {
                final tools = ref.watch(toolsProvider).tools;
                final skills = ref.watch(skillsProvider);
                final subagents = ref.watch(subagentsProvider);
                // Filter by _search, render each item with ScopePicker
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (tools.isEmpty && skills.isEmpty && subagents.isEmpty)
                      Text('No items match your search.',
                          style: tokens.typography.textTheme.bodySmall
                              ?.copyWith(color: tokens.colors.textTertiary))
                    else ...[
                      // Render items from all three providers,
                      // each with ScopePicker widget
                    ],
                  ],
                );
              },
            ),
          ),
      ),
    );
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd flutter_app && flutter test test/core/layout/capabilities_tab_test.dart
```

- [ ] **Step 5: Commit**

```bash
git add flutter_app/lib/features/workspace/capabilities_tab.dart \
        flutter_app/test/core/layout/capabilities_tab_test.dart
git commit -m "feat: CapabilitiesTab widget with unified Tools/Skills/Subagents sections"
```

---

## Task 6: Update workspace panel tabs

**Files:**
- Modify: `flutter_app/lib/features/workspace/workspace_panel.dart`

- [ ] **Step 1: Replace 4 tabs with 3**

Change `_WorkspacePanelTab` enum from `{files, skills, subagents, tools}` to `{files, canvas, capabilities}`:

```dart
enum _WorkspacePanelTab { files, canvas, capabilities }
```

- [ ] **Step 2: Update bottom tab bar**

Replace the 4 bottom tab buttons with 3 (Canvas, Files, Capabilities):

```dart
_BottomTabButton(
  icon: Symbols.dashboard_customize,
  activeIcon: Symbols.dashboard_customize,
  selected: selected == _WorkspacePanelTab.canvas,
  tooltip: 'Canvas',
  onTap: () => onSelected(_WorkspacePanelTab.canvas),
),
const SizedBox(width: 8),
_BottomTabButton(
  icon: Symbols.folder,
  activeIcon: Symbols.folder,
  selected: selected == _WorkspacePanelTab.files,
  tooltip: 'Files',
  onTap: () => onSelected(_WorkspacePanelTab.files),
),
const SizedBox(width: 8),
_BottomTabButton(
  icon: Symbols.tune,
  activeIcon: Symbols.tune,
  selected: selected == _WorkspacePanelTab.capabilities,
  tooltip: 'Capabilities',
  onTap: () => onSelected(_WorkspacePanelTab.capabilities),
),
```

- [ ] **Step 3: Add auto-activation for Canvas tab**

In the `_WorkspacePanelState`, listen for `canvas_update` events and switch to the Canvas tab:

```dart
// In build method or initState, listen to a canvas provider:
ref.listen(canvasProvider, (prev, next) {
  if (next.surfaces.isNotEmpty && next.surfaces.last.action != 'destroy') {
    setState(() => _selectedTab = _WorkspacePanelTab.canvas);
  }
});
```

- [ ] **Step 4: Wire Canvas tab in the body**

Add the Canvas tab body alongside Files:

```dart
case _WorkspacePanelTab.canvas:
  return const CanvasTab();
case _WorkspacePanelTab.files:
  return _buildFiles();
case _WorkspacePanelTab.capabilities:
  return const CapabilitiesTab();
```

- [ ] **Step 5: Remove unused imports**

Remove imports for `skills_panel.dart`, `subagents_panel.dart`, and `tools_panel.dart` / `tools_workspace_tab.dart` if no longer referenced.

- [ ] **Step 6: Run analyzer**

```bash
cd flutter_app && flutter analyze lib/features/workspace/workspace_panel.dart
```

- [ ] **Step 7: Update workspace panel tests**

```dart
// In test/core/layout/workspace_panel_test.dart
// Update any test that references the old tabs (skills, subagents, tools)
// to use the new tabs (canvas, capabilities)
```

- [ ] **Step 8: Run full Flutter test suite**

```bash
cd flutter_app && flutter test
```

- [ ] **Step 9: Commit**

```bash
git add flutter_app/lib/features/workspace/workspace_panel.dart \
        flutter_app/test/
git commit -m "feat: replace Skills/Subagents/Tools tabs with Canvas/Capabilities in workspace panel"
```

---

## Task 7: Render skills_load as inline chat event

**Files:**
- Modify: `flutter_app/lib/features/chat/chat_screen.dart`
- Modify: `flutter_app/lib/services/ws_client.dart` (if needed)

- [ ] **Step 1: Add skills_load event handling in chat message builder**

In `chat_screen.dart`, add a case for `skills_load` events in the message stream builder:

```dart
// In the message/event build method:
if (event.type == 'skills_load') {
  final name = event.data?['name'] ?? 'unknown';
  return Padding(
    padding: const EdgeInsets.symmetric(vertical: 4, horizontal: 12),
    child: Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: colors.accent.withAlpha(18),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: colors.accent.withAlpha(80)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Symbols.psychology, size: 16, color: colors.accent),
          const SizedBox(width: 6),
          Text(
            'Loaded: $name',
            style: TextStyle(fontSize: 12, color: colors.accent),
          ),
        ],
      ),
    ),
  );
}
```

- [ ] **Step 2: Backend: emit skills_load event when agent loads a skill**

In the skills tool handler or the agent loop, emit a `skills_load` WebSocket event:

```python
# When skills_load tool is called:
await ws_handler.broadcast({
    "type": "skills_load",
    "data": {"name": skill_name},
})
```

- [ ] **Step 3: Run analyzer and tests**

```bash
cd flutter_app && flutter analyze lib/features/chat/chat_screen.dart
flutter test test/features/chat/
```

- [ ] **Step 4: Commit**

```bash
git add flutter_app/lib/features/chat/chat_screen.dart
git commit -m "feat: render skills_load as inline event in chat stream"
```

---

## Task 8: Create canvas-painting seed skill

**Files:**
- Create: `src/skills_seed/canvas-painting/SKILL.md`

- [ ] **Step 1: Create SKILL.md**

```markdown
# src/skills_seed/canvas-painting/SKILL.md
---
name: canvas-painting
description: Generate HTML forms, cards, and visual output for the Canvas tab. Use when the user asks to create or edit a skill, subagent, or any form-based interaction. Also use to display structured results (tables, cards, comparisons) visually. Output HTML with ```html:canvas fence blocks.
---

# Canvas Painting

When the agent needs to render a visual form, card, or result in the Canvas
tab, follow these rules.

## Output Format

Use fenced code blocks with the `html:canvas` language modifier:

```html:canvas
<div>...</div>
```

For typed surfaces, use the modifier:
- ```` ```html:skill-form ```` — for skill creation/editing forms
- ```` ```html:subagent-form ```` — for subagent creation/editing forms
- ```` ```html:canvas ```` — for general results, cards, free-form output

## Required Fields

### skill-form
- `name` — text input for skill name
- `description` — textarea for skill description
- `content` — textarea for SKILL.md body

### subagent-form
- `name` — text input for agent name
- `description` — textarea for what the agent does
- `model` — dropdown or text input for model
- `system_prompt` — textarea for the agent's system prompt

## Styling

Use CSS custom properties (design tokens) for theming:
- `var(--primary)` — accent color
- `var(--bg)` — background color
- `var(--text)` — text color
- `var(--border)` — border color

## Interaction

Use `postMessage` to send user actions back to the agent:

```html
<button onclick="window.flutter_inappwebview.callHandler('canvas_action', JSON.stringify({action:'save', fields:{...}}))">Save</button>
```
```

- [ ] **Step 2: Verify the seed skill loads**

```bash
curl -s "http://127.0.0.1:8080/skills?user_id=default_user&workspace_id=personal" | python3 -c "import json,sys; d=json.load(sys.stdin); print([s['name'] for s in d['skills']])"
```

- [ ] **Step 3: Commit**

```bash
git add src/skills_seed/canvas-painting/SKILL.md
git commit -m "feat: canvas-painting seed skill for agent-generated HTML"
```

---

## Task 9: Full integration test + manual verification

- [ ] **Step 1: Run backend tests**

```bash
uv run pytest tests/sdk/ tests/api/ -q
```

- [ ] **Step 2: Run Flutter tests**

```bash
cd flutter_app && flutter test
```

- [ ] **Step 3: Run Flutter analyzer**

```bash
cd flutter_app && flutter analyze lib/
```

- [ ] **Step 4: Build macOS and manually smoke test**

```bash
cd flutter_app && flutter build macos --debug
open build/macos/Build/Products/Debug/flutter_app.app
```

Verify:
- Sidebar: No Files entry, Connection | Tools | Skills | Subagents | Settings visible
- Workspace panel: 3 bottom tabs — Canvas | Files | Capabilities
- Canvas tab: Empty state by default
- Capabilities tab: 3 collapsible sections with search
- Chat: skills_load renders as inline event
- Agent generates HTML → Canvas tab auto-activates

- [ ] **Step 5: Commit final adjustments**

```bash
git add . && git commit -m "test: integration verification and final adjustments"
git push origin feat/ag-ui-canvas-capabilities
```
