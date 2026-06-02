import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Per-workspace input drafts. Keyed by workspace_id.
/// In-memory only — not persisted to disk in this batch.
final draftProvider = StateNotifierProvider<DraftNotifier, Map<String, String>>(
  (ref) => DraftNotifier(),
);

class DraftNotifier extends StateNotifier<Map<String, String>> {
  DraftNotifier() : super(const {});

  String? load(String workspaceId) => state[workspaceId];

  void save(String workspaceId, String text) {
    if (text.isEmpty) {
      clear(workspaceId);
      return;
    }
    state = {...state, workspaceId: text};
  }

  void clear(String workspaceId) {
    if (!state.containsKey(workspaceId)) return;
    final next = Map<String, String>.from(state)..remove(workspaceId);
    state = next;
  }
}
