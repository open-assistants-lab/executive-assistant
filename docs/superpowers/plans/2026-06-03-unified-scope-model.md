# Unified Scope Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the `ScopeSwitcher` with a three-state per-item scope picker (All / Selected / None) across Tools, Skills, and Subagents panels. Unify the UX and backend into a single `item_scopes` table.

**Spec:** `docs/superpowers/specs/2026-06-03-tool-skill-subagent-scope-unification.md`

**Tech Stack:** Flutter, Riverpod, GoRouter, Python/FastAPI, SQLite

---

## File Structure

| File | Responsibility |
|------|---------------|
| `packages/connectkit/connectkit/item_scopes.py` | New: `ItemScopeDB` — CRUD for `item_scopes` SQLite table |
| `src/http/routers/tools.py` | Modify: GET returns per-item scope, POST accepts scope body |
| `src/http/routers/skills.py` | Modify: GET returns per-item scope, POST accepts scope body |
| `src/http/routers/subagents.py` | Modify: GET returns per-item scope, POST accepts scope body |
| `src/sdk/runner.py` | Modify: `create_sdk_loop` queries `item_scopes` instead of old per-workspace schema |
| `src/sdk/native_tools.py` | Modify: default scope for new tools |
| `flutter_app/lib/features/tools/tools_panel.dart` | Modify: remove ScopeSwitcher, add per-item scope badge |
| `flutter_app/lib/features/tools/tools_provider.dart` | Modify: fetch & toggle with scope model |
| `flutter_app/lib/features/skills/skills_sidebar_panel.dart` | Modify: add per-item scope badge |
| `flutter_app/lib/features/subagents/subagents_sidebar_panel.dart` | Modify: add per-item scope badge |
| `flutter_app/lib/widgets/scope_picker.dart` | New: reusable ScopePicker widget (badge + popup + modal) |
| `flutter_app/lib/widgets/scope_switcher.dart` | Delete |
| `flutter_app/test/core/layout/scope_picker_test.dart` | New: widget tests for ScopePicker |
| `flutter_app/test/features/tools/tools_scope_test.dart` | New: unit tests for scope toggle logic |

---

## Task 1: Backend — `ItemScopeDB` + API endpoints

**Files:**
- Create: `packages/connectkit/connectkit/item_scopes.py`
- Modify: `src/http/routers/tools.py`
- Modify: `src/http/routers/skills.py`
- Modify: `src/http/routers/subagents.py`

**Steps:**

- [ ] Step 1: Create `ItemScopeDB`

```python
# packages/connectkit/connectkit/item_scopes.py
import json
import os
import sqlite3
from dataclasses import dataclass, field
from typing import Literal

ScopeKind = Literal["all", "selected", "none"]

@dataclass
class ItemScope:
    resource_type: str  # "tool", "skill", "subagent"
    resource_name: str
    scope: ScopeKind
    workspace_ids: list[str] = field(default_factory=list)

class ItemScopeDB:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS item_scopes (
                user_id TEXT NOT NULL,
                resource_type TEXT NOT NULL,
                resource_name TEXT NOT NULL,
                scope TEXT NOT NULL DEFAULT 'all',
                workspace_ids TEXT NOT NULL DEFAULT '[]',
                PRIMARY KEY (user_id, resource_type, resource_name)
            )
        """)
        return conn

    def get(
        self, user_id: str, resource_type: str, resource_name: str
    ) -> ItemScope | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM item_scopes WHERE user_id=? AND resource_type=? AND resource_name=?",
                (user_id, resource_type, resource_name),
            ).fetchone()
        if not row:
            return None
        return ItemScope(
            resource_type=row["resource_type"],
            resource_name=row["resource_name"],
            scope=row["scope"],
            workspace_ids=json.loads(row["workspace_ids"]),
        )

    def set(
        self,
        user_id: str,
        resource_type: str,
        resource_name: str,
        scope: ScopeKind,
        workspace_ids: list[str] | None = None,
    ) -> None:
        with self._connect() as conn:
            wids = json.dumps(workspace_ids or [])
            conn.execute(
                """INSERT INTO item_scopes (user_id, resource_type, resource_name, scope, workspace_ids)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(user_id, resource_type, resource_name) DO UPDATE SET
                   scope=excluded.scope, workspace_ids=excluded.workspace_ids""",
                (user_id, resource_type, resource_name, scope, wids),
            )

    def list_for_workspace(
        self, user_id: str, resource_type: str, workspace_id: str
    ) -> list[ItemScope]:
        """Return all items available for a given workspace.
        Includes scope=all, scope=selected with matching workspace_ids,
        and items not yet in the table (treated as scope=all)."""
        results: list[ItemScope] = []
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT * FROM item_scopes
                   WHERE user_id=? AND resource_type=? AND (
                     scope='all' OR
                     (scope='selected' AND EXISTS (
                       SELECT 1 FROM json_each(workspace_ids)
                       WHERE value = ?
                     ))
                   )""",
                (user_id, resource_type, workspace_id),
            ).fetchall()
        for row in rows:
            results.append(ItemScope(
                resource_type=row["resource_type"],
                resource_name=row["resource_name"],
                scope=row["scope"],
                workspace_ids=json.loads(row["workspace_ids"]),
            ))
        return results

    def get_available_names(
        self, user_id: str, resource_type: str, workspace_id: str
    ) -> set[str]:
        """Return names of resources available for a workspace.
        Items NOT in the table default to scope=all and are included."""
        names: set[str] = set()
        with self._connect() as conn:
            # Explicitly scoped items
            rows = conn.execute(
                """SELECT resource_name FROM item_scopes
                   WHERE user_id=? AND resource_type=? AND (
                     scope='all' OR scope='selected'
                   )""",
                (user_id, resource_type),
            ).fetchall()
            for row in rows:
                names.add(row["resource_name"])
            # Items with scope=none that have been explicitly set
            excluded = conn.execute(
                """SELECT resource_name FROM item_scopes
                   WHERE user_id=? AND resource_type=? AND scope='none'""",
                (user_id, resource_type),
            ).fetchall()
            excluded_names = {row["resource_name"] for row in excluded}
        return names - excluded_names

    def migrate_from_legacy(
        self, user_id: str, legacy_db_path: str
    ) -> int:
        """Migrate from old per-workspace tool_enabled table.
        Returns count of migrated items."""
        # Implementation details depend on current schema.
        # See spec Migration Path for rules.
        raise NotImplementedError
```

- [ ] Step 2: Modify `GET /tools?user_id=U&workspace_id=W` to include scope fields

Each tool in the response adds `scope` and `workspace_ids`:
```python
# In tools router:
scope_row = items_db.get(user_id, "tool", tool_name)
if scope_row:
    scope = scope_row.scope
    workspace_ids = scope_row.workspace_ids
else:
    scope = "all"  # default for SDK tools
    workspace_ids = []

enabled = (
    scope == "all"
    or (scope == "selected" and workspace_id in workspace_ids)
)

return {
    "name": tool_name,
    "enabled": enabled,
    "scope": scope,
    "workspace_ids": workspace_ids,
    ...
}
```

- [ ] Step 3: Modify `POST /tools/{name}` to accept scope body

```python
# New body: {"scope": "all"|"selected"|"none", "workspace_ids": ["w1","w2"]}
# Old body: {"enabled": true/false} — still accepted for backward compat,
# converts to scope mode: enabled=true → scope="selected" with current ws
```

- [ ] Step 4: Add scope endpoints for `/skills` and `/subagents` (same pattern)

- [ ] Step 5: Write backend tests for ItemScopeDB and scope endpoints

```bash
uv run pytest tests/sdk/test_item_scopes.py -v
```

- [ ] Step 6: Modify `src/sdk/runner.py` `create_sdk_loop()` to use item_scopes

Replace the current per-workspace tool loading with:
```python
available = items_db.get_available_names(user_id, "tool", workspace_id)
tools = [t for t in all_tools if t.name in available]
# Same for skills (resource_type="skill") and subagents
```

---

## Task 2: Frontend — `ScopePicker` widget

**Files:**
- Create: `flutter_app/lib/widgets/scope_picker.dart`
- Create: `flutter_app/test/core/layout/scope_picker_test.dart`

**Steps:**

- [ ] Step 1: Create `ScopePicker` widget

```dart
// flutter_app/lib/widgets/scope_picker.dart
enum ScopeState { all, selected, none }

class ScopePicker extends StatelessWidget {
  final ScopeState scope;
  final List<String> selectedWorkspaceIds;
  final List<WorkspaceInfo> allWorkspaces;
  final ValueChanged<ScopeChange> onChanged;

  // ScopeChange holds the new state + optional workspace list
  ...
}
```

Badge display (build method):
```dart
Widget build(BuildContext context) {
  final badge = switch (scope) {
    ScopeState.all => const ScopeBadge(label: 'All ✓', color: Colors.green),
    ScopeState.selected => ScopeBadge(
      label: '${selectedWorkspaceIds.length} WS ✓',
      color: Colors.green,
      tooltip: _workspaceNames(),
    ),
    ScopeState.none => const ScopeBadge(label: 'Off', color: Colors.grey),
  };
  return GestureDetector(
    onTap: _showPopup,
    child: badge,
  );
}
```

Popup menu (on badge tap):
```dart
void _showPopup(BuildContext context) {
  showMenu(
    items: [
      PopupMenuItem(value: ScopeState.all, child: Text('Enable for all workspaces')),
      PopupMenuItem(value: ScopeState.selected, child: Text('Enable for selected workspaces…')),
      PopupMenuItem(value: ScopeState.none, child: Text('Disable')),
    ],
  ).then((value) {
    if (value == ScopeState.selected) {
      _showWorkspaceModal(context);
    } else if (value != null) {
      onChanged(ScopeChange(scope: value));
    }
  });
}
```

Workspace modal (when "Selected" is chosen):
```dart
void _showWorkspaceModal(BuildContext context) {
  showDialog(
    context: context,
    builder: (ctx) => WorkspaceChecklistDialog(
      allWorkspaces: allWorkspaces,
      selectedIds: selectedWorkspaceIds,
      onApply: (ids) => onChanged(ScopeChange(
        scope: ScopeState.selected,
        workspaceIds: ids,
      )),
    ),
  );
}
```

- [ ] Step 2: Write widget tests

```dart
// flutter_app/test/core/layout/scope_picker_test.dart
void main() {
  group('ScopePicker', () {
    testWidgets('shows All badge when scope is all', ...)
    testWidgets('shows count badge when scope is selected', ...)
    testWidgets('shows Off badge when scope is none', ...)
    testWidgets('tapping badge opens popup menu', ...)
    testWidgets('choosing Selected opens workspace modal', ...)
  });
}
```

- [ ] Step 3: Run analyzer and tests

```bash
cd flutter_app
flutter analyze lib/widgets/scope_picker.dart
flutter test test/core/layout/scope_picker_test.dart
```

---

## Task 3: Frontend — Update `ToolsPanel`

**Files:**
- Modify: `flutter_app/lib/features/tools/tools_panel.dart`
- Modify: `flutter_app/lib/features/tools/tools_provider.dart`
- Create: `flutter_app/test/features/tools/tools_scope_test.dart`

**Steps:**

- [ ] Step 1: Remove `ScopeSwitcher` from `ToolsPanel`

Remove `_scope` state, `CapabilityScope`, and the `ScopeSwitcher` widget.
Remove the `import '../../widgets/scope_switcher.dart';`.

- [ ] Step 2: Load tools with workspace_id query param

```dart
void _load() {
  final host = ref.read(hostProvider);
  final userId = ref.read(userIdProvider);
  final wsId = ref.read(currentWorkspaceIdProvider);
  ref.read(toolsProvider.notifier).loadTools(
    host: host, userId: userId, workspaceId: wsId,
  );
}
```

- [ ] Step 3: Update `toolsProvider` to parse scope fields from API

```dart
// tools_provider.dart — update ToolItem to include scope
class ToolItem {
  final String name;
  final String description;
  final bool enabled;
  final String scope;       // "all" | "selected" | "none"
  final List<String> workspaceIds;  // when scope=selected
  ...
  factory ToolItem.fromJson(Map<String, dynamic> json) => ToolItem(
    name: json['name'],
    ...
    scope: json['scope'] ?? 'all',
    workspaceIds: (json['workspace_ids'] as List?)?.cast<String>() ?? [],
  );
}
```

- [ ] Step 4: Replace `Switch` widget with `ScopePicker`

In `_ToolRow.build()`, replace:
```dart
Switch(value: tool.enabled, onChanged: onToggle)
```
with:
```dart
ScopePicker(
  scope: _mapScope(tool.scope),
  selectedWorkspaceIds: tool.workspaceIds,
  allWorkspaces: _allWorkspaces,
  onChanged: (change) => _onScopeChanged(tool.name, change),
)
```

- [ ] Step 5: Handle scope changes in `toolsProvider`

```dart
Future<void> setScope(String toolName, ScopeChange change) async {
  final body = {
    'scope': change.scope.name,  // "all", "selected", "none"
    'workspace_ids': change.workspaceIds,
  };
  await http.post(
    Uri.parse('http://$host/tools/$toolName?user_id=$userId'),
    body: jsonEncode(body),
  );
  await loadTools(...);
}
```

- [ ] Step 6: Update header count

The count `"X / Y enabled"` now reflects the current workspace only — this is already what the API returns with the `workspace_id` query param.

- [ ] Step 7: Write scope toggle tests

```bash
flutter test test/features/tools/tools_scope_test.dart
```

---

## Task 4: Frontend — Update `SkillsSidebarPanel` and `SubagentsSidebarPanel`

**Files:**
- Modify: `flutter_app/lib/features/skills/skills_sidebar_panel.dart`
- Modify: `flutter_app/lib/features/subagents/subagents_sidebar_panel.dart`

**Steps:**

- [ ] Step 1: Remove `ScopeSwitcher` from `SkillsSidebarPanel`

Remove `_scope` state and `ScopeSwitcher`. Replace with space for future skill items.

- [ ] Step 2: Add per-item `ScopePicker` to skill rows (once the stub is replaced with real skill items)

For now (stub remains), the panel just shows title + search + "coming soon" placeholder. The ScopePicker wiring happens when the skill list is populated.

- [ ] Step 3: Repeat for `SubagentsSidebarPanel`

---

## Task 5: Frontend — Remove `ScopeSwitcher` widget

**Files:**
- Delete: `flutter_app/lib/widgets/scope_switcher.dart`

**Steps:**

- [ ] Step 1: Check all references to `ScopeSwitcher`

```bash
grep -r "ScopeSwitcher\|scope_switcher" flutter_app/lib/
```

- [ ] Step 2: Verify no remaining imports

After Tasks 3 and 4 remove ScopeSwitcher usage, the file has no consumers. Delete it.

- [ ] Step 3: Run full test suite

```bash
cd flutter_app && flutter test
```

---

## Task 6: Full test pass + manual verification

**Steps:**

- [ ] Step 1: Run backend tests

```bash
uv run pytest tests/ -v
```

- [ ] Step 2: Run Flutter tests

```bash
cd flutter_app && flutter test
```

- [ ] Step 3: Run Flutter analyzer

```bash
cd flutter_app && flutter analyze lib/
```

- [ ] Step 4: Build macOS and manually smoke test

```bash
cd flutter_app && flutter build macos --debug
open build/macos/Build/Products/Debug/flutter_app.app
```

Verify:
- Tools panel: scope badges per tool, popup → modal works
- Skills panel: no ScopeSwitcher
- Subagents panel: no ScopeSwitcher
- Workspace switching: tools apply correctly per workspace

- [ ] Step 5: Commit and push

```bash
git add ... && git commit -m "feat: unified scope model — All/Selected/None per item"
git push origin main
```
