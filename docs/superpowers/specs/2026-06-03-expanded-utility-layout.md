# EA: Expanded Workspace for Sidebar Routes

2026-06-03

## Context

When the user taps **Tools**, **Skills**, **Subagents**, **Connection**, or
**Settings** in the sidebar, the panel renders in the rightmost 40% column
(`contentWidth`). The middle 60% is the chat panel, which is irrelevant for
these utility views. The result:

- These utility panels feel cramped — a tool description or skill form
  doesn't have room to breathe
- The chat panel is showing messages that are unrelated to what the user is
  doing (configuring tools, editing a skill, etc.)
- Users can still see the chat and accidentally type into it, breaking flow

Slack, Linear, VS Code, and most modern desktop apps follow the same
pattern: when a utility/management view is open, it expands to fill the
content area (minus sidebar). The chat/primary view only takes the full
width when the user is actually using it (e.g., on `/chat` or when no
utility route is active).

## Summary

Five routes — `/tools`, `/skills`, `/subagents`, `/connectors`, `/settings`
— expand to cover the chat panel + RHS when active. The sidebar stays
fixed. When the user navigates back to `/workspace`, `/email`, `/chat`, or
any non-utility route, the normal three-column layout returns.

Visual comparison:

```
Current (all routes):                 After this change:
┌──────┬─────────┬──────────┐         ┌──────┬─────────────────────┐
│ Side │  Chat   │ Content  │         │ Side │   Utility Panel     │
│ bar  │ (60%)   │  (40%)   │         │ bar  │   (100% of rest)    │
│      │         │ <panel>  │         │      │   <full width>      │
└──────┴─────────┴──────────┘         └──────┴─────────────────────┘
```

## Routes

**Utility routes (expand to full content width):**
- `/tools` — `ToolsPanel` (88 tools, category sections)
- `/skills` — `SkillsSidebarPanel`
- `/subagents` — `SubagentsSidebarPanel`
- `/connectors` — `ConnectorsModal` (currently a modal — needs to be promoted to a full panel)
- `/settings` — `SettingsScreen`

**Normal routes (keep current three-column layout):**
- `/workspace` — `WorkspacePanel` (files, skills, subagents tabs)
- `/email` — `EmailListScreen`
- `/chat` — `ChatScreen` (already full-width, separate route)
- `/tasks`, `/contacts`, `/more` — placeholder screens

## Approach

Use GoRouter's `state.matchedLocation` (or a derived `isUtilityRoute` flag)
in `ResponsiveShell` to decide which layout to render. The simplest split:

- `DesktopLayout` (current three-column) is used for non-utility routes
- `DesktopUtilityLayout` (new, two-column: sidebar | expanded panel) is
  used for utility routes

The sidebar widget (`_Sidebar`) stays identical in both layouts. The
expanded panel is the `child` from `ResponsiveShell` — same widget tree,
just wider container.

```dart
// ResponsiveShell.build
if (isUtilityRoute(state.matchedLocation)) {
  return DesktopUtilityLayout(child: child);
} else {
  return DesktopLayout(child: child);
}
```

## Files

### New
- `flutter_app/lib/core/layout/desktop_utility_layout.dart` — the new
  two-column layout (sidebar + full-width content)

### Modify
- `flutter_app/lib/core/layout/desktop_layout.dart` — rename `_Sidebar` →
  `Sidebar` (and `_SidebarItem` → `SidebarItem`) so `ResponsiveShell`
  can reference it from another file
- `flutter_app/lib/core/layout/responsive_shell.dart` — branch on
  `isUtilityRoute`
- `flutter_app/lib/core/router/app_router.dart` — add a helper
  `isUtilityRoute(String path)`; add the missing `/connectors` route
- `flutter_app/lib/features/connectors/connectors_modal.dart` — fix the
  close button to work in both dialog and routed contexts
- `flutter_app/test/core/layout/responsive_shell_test.dart` — new test
  file for route-to-layout mapping

## Design

### DesktopUtilityLayout

```dart
class DesktopUtilityLayout extends ConsumerWidget {
  final Widget sidebar;
  final Widget child;
  const DesktopUtilityLayout({
    super.key,
    required this.sidebar,
    required this.child,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Scaffold(
      body: Stack(
        children: [
          Row(
            children: [
              sidebar,
              Container(
                width: 1,
                color: context.tokens.colors.borderSubtle,
              ),
              Expanded(child: child),  // utility panel fills the rest
            ],
          ),
          const CompanionToastOverlay(),
        ],
      ),
    );
  }
}
```

Same `Stack` + `Row` pattern as `DesktopLayout`, but only two columns.
The `sidebar` parameter accepts the `Sidebar` widget (renamed from
`_Sidebar` for cross-file access). The expanded panel is the `child`
from `ResponsiveShell` — same widget tree, just wider container.

### Route classification

```dart
// app_router.dart
const _utilityRoutes = {
  '/tools', '/skills', '/subagents', '/connectors', '/settings',
};

bool isUtilityRoute(String path) => _utilityRoutes.contains(path);
```

Use `GoRouterState.matchedLocation` (or `GoRouterState.uri.toString()`)
inside `ResponsiveShell` to check the active route. Since
`ResponsiveShell` is built by the `ShellRoute.builder`, it receives
`state` as a parameter.

```dart
ShellRoute(
  builder: (context, state, child) {
    return ResponsiveShell(state: state, child: child);
  },
  ...
)
```

### Connectors panel promotion

Currently `ConnectorsModal` is opened via a method call (likely a
`showDialog` or similar). To make it a routed panel:

1. Create a new widget `ConnectorsPanel` (or rename `ConnectorsModal` →
  `ConnectorsPanel` and remove the dialog wrapper)
2. Wire it to `/connectors` in `app_router.dart`
3. Replace the modal-open call site with a `context.go('/connectors')`
  (or keep the modal behavior and just add the route as an alternate
  entry point)

The exact promotion approach depends on how `ConnectorsModal` is
currently invoked — needs investigation during implementation.

## Testing

### Widget tests
- `DesktopUtilityLayout` renders sidebar + child in two columns
- `ResponsiveShell` selects `DesktopUtilityLayout` for each utility
  route (`/tools`, `/skills`, `/subagents`, `/connectors`, `/settings`)
- `ResponsiveShell` selects `DesktopLayout` for non-utility routes
  (`/workspace`, `/email`)
- Existing tools/skills/subagents panel tests still pass (they test the
  panel widgets, not the layout)

### Manual smoke test
- Tap each utility sidebar item — panel expands to full width
- Tap `/workspace` — three-column layout returns
- Resize window — both layouts respond to breakpoints
- Open `/chat` — full-width chat (unchanged)

## Out of scope (deferred)
- Tablet/mobile behavior for utility routes — they already use a
  full-width single-column stack on smaller breakpoints, so no change
  needed
- Animation/transition between the two layouts — current route
  transition (fade) is sufficient
- Collapsing the chat panel to a smaller "minimized" state — full
  replacement is simpler and clearer
