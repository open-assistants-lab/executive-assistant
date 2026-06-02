import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'dart:convert';
import 'workspace_provider.dart';

/// Tracks which workspace tabs are open in the chat panel.
/// Key: workspace_id, Value: workspace_name
final openChatTabsProvider = StateProvider<Map<String, String>>((ref) {
  return {'personal': 'Personal'};
});

/// Increments every time the user switches workspaces (even to the same one).
/// Use this to trigger scroll-to-bottom reliably — unlike activeChatTabProvider,
/// this always changes, so listeners fire even when clicking the active tab.
final workspaceSwitchSignalProvider = StateProvider<int>((ref) => 0);

/// The workspace_id of the currently focused chat tab.
final activeChatTabProvider = StateProvider<String>((ref) => 'personal');

class ChatTabNotifier extends StateNotifier<Map<String, String>> {
  final Ref ref;

  ChatTabNotifier(this.ref) : super({'personal': 'Personal'}) {
    _restoreTabs();
  }

  Future<void> _restoreTabs() async {
    final prefs = await SharedPreferences.getInstance();
    final saved = prefs.getString('open_tabs');
    if (saved != null) {
      try {
        final tabs = Map<String, String>.from(jsonDecode(saved));
        if (tabs.isNotEmpty) {
          state = tabs;
          final activeId = prefs.getString('active_workspace_id') ?? 'personal';
          final activeName = tabs[activeId] ?? 'Personal';
          ref.read(activeChatTabProvider.notifier).state = activeId;
          ref.read(workspaceNotifierProvider.notifier).switchWorkspace(activeId, activeName);
        }
      } catch (_) {}
    }
  }

  Future<void> _persistTabs() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('open_tabs', jsonEncode(state));
  }

  void openWorkspace(String id, String name) {
    if (state.containsKey(id)) {
      ref.read(activeChatTabProvider.notifier).state = id;
      ref.read(workspaceNotifierProvider.notifier).switchWorkspace(id, name);
      ref.read(workspaceSwitchSignalProvider.notifier).state++;
      return;
    }
    state = {...state, id: name};
    ref.read(activeChatTabProvider.notifier).state = id;
    ref.read(workspaceNotifierProvider.notifier).switchWorkspace(id, name);
    _persistTabs();
    ref.read(workspaceSwitchSignalProvider.notifier).state++;
  }

  void closeTab(String id) {
    if (state.length <= 1) return;
    final updated = Map<String, String>.from(state)..remove(id);
    state = updated;

    if (ref.read(activeChatTabProvider) == id) {
      final nextId = updated.keys.first;
      ref.read(activeChatTabProvider.notifier).state = nextId;
      final nextName = updated[nextId]!;
      ref.read(workspaceNotifierProvider.notifier).switchWorkspace(nextId, nextName);
    }
    _persistTabs();
  }
}

final chatTabNotifierProvider =
    StateNotifierProvider<ChatTabNotifier, Map<String, String>>((ref) {
  return ChatTabNotifier(ref);
});
