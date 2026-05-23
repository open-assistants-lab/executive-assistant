# Workspace Switch Transition

## Design Tokens Available

| Token | Value | Usage |
|-------|-------|-------|
| `EaMotion.fluid` | 300ms | Crossfade duration |
| `EaMotion.intuitive` | 400ms | Panel slide duration |
| `Curves.easeInOutCubic` | — | Smooth acceleration/deceleration |

## Key Constraints

1. **Panel-level, not item-level** — the transition must animate the whole panel container, not individual messages. The original slide bug was caused by `Transform.translate` on list items.
2. **No scroll state loss** — the `ListView` is keyed by `ValueKey('chat_list_$workspaceId')`, so a transition must not interfere with scroll controller attachment.
3. **Loading state first** — after the transition starts, the panel shows a loading spinner while history loads. The transition should complete before content appears.

## Recommended Approach: AnimatedSwitcher

Wrap the chat panel body in `AnimatedSwitcher` keyed by `workspaceId`:

### 1. `DesktopLayout._ChatPanel`

```dart
AnimatedSwitcher(
  duration: t.motion.fluid,
  switchInCurve: Curves.easeInOutCubic,
  switchOutCurve: Curves.easeInOutCubic.flipped,
  transitionBuilder: (child, animation) {
    final slideTween = Tween<Offset>(
      begin: const Offset(0.3, 0),
      end: Offset.zero,
    ).animate(CurvedAnimation(
      parent: animation,
      curve: Curves.easeOutCubic,
    ));
    return FadeTransition(
      opacity: animation,
      child: SlideTransition(
        position: slideTween,
        child: child,
      ),
    );
  },
  child: KeyedSubtree(
    key: ValueKey('chat_panel_$workspaceId'),
    child: _buildPanelContent(state),
  ),
)
```

### 2. `KeyedSubtree`

Use `KeyedSubtree(key: ValueKey('chat_panel_$workspaceId'))` as the `AnimatedSwitcher` child so that Flutter detects a widget type change (old → new key) and triggers the out/in animation. Without explicit keying, `AnimatedSwitcher` can't distinguish old from new content.

### 3. Layout

The panel layout is:

```
AnimatedSwitcher
  └─ KeyedSubtree(key: workspaceId)
       ├─ _PendingApprovalBar (if has approval)
       ├─ ChatMessageList (keyed by workspaceId internally)
       ├─ ConnectionBanner (if disconnected)
       └─ _InputBar
```

### 4. Mobile

The mobile layout (`MobileLayout`) also switches workspaces via `ChatScreen`. Apply the same `AnimatedSwitcher` in `chat_screen.dart` for consistency. Use `EaMotion.fluid` (300ms) or `EaMotion.intuitive` (400ms) depending on whether it's a push navigation or in-place switch.

## Alternative: AnimatedCrossFade (simpler, no slide)

If the slide feel is too much, `AnimatedCrossFade` gives a clean opacity crossfade with zero layout risk:

```dart
AnimatedCrossFade(
  duration: t.motion.fluid,
  firstChild: _oldPanel,
  secondChild: _newPanel,
  crossFadeState: _showingNew
      ? CrossFadeState.showSecond
      : CrossFadeState.showFirst,
)
```

The downside is both children remain in the tree during the crossfade, so this is only appropriate when both panels are lightweight (not with a full message list).

## Files to Modify

| File | Change |
|------|--------|
| `flutter_app/lib/core/layout/desktop_layout.dart` | Wrap `_ChatPanel` body in `AnimatedSwitcher` |
| `flutter_app/lib/providers/chat_tab_provider.dart` | Expose `workspaceId` as a signal for the transition |
| `flutter_app/lib/features/chat/chat_screen.dart` | Same `AnimatedSwitcher` pattern for mobile |

## Verification

- Transition runs on workspace switch (sidebar click, workspace command)
- Loading spinner shows during history fetch
- Scroll position preserved after content loads
- Works in both light and dark mode
- `flutter test test/core/layout/desktop_layout_test.dart` passes
