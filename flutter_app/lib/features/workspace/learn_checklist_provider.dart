import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

const _dismissedKey = 'ea_learn_checklist_dismissed';
const _completedKey = 'ea_learn_checklist_completed';

class LearnChecklistItem {
  final String id;
  final String title;
  final String description;
  final String icon; // emoji
  LearnChecklistItem({
    required this.id,
    required this.title,
    required this.description,
    required this.icon,
  });
}

final checklistItems = [
  LearnChecklistItem(
    id: 'chat',
    title: 'Start a conversation',
    description: 'Ask me anything — draft an email, research a topic, or manage tasks.',
    icon: '\u{1F4AC}',
  ),
  LearnChecklistItem(
    id: 'email',
    title: 'Connect Google Workspace',
    description: 'Auth into Gmail, Calendar, and Contacts — or try a general task.',
    icon: '\u{1F4E7}',
  ),
  LearnChecklistItem(
    id: 'todos',
    title: 'Create and manage tasks',
    description: 'Add todos, set priorities, and track what\'s due.',
    icon: '\u{1F4CB}',
  ),
  LearnChecklistItem(
    id: 'web',
    title: 'Search the web',
    description: 'Find articles, research topics, and pull live information.',
    icon: '\u{1F310}',
  ),
  LearnChecklistItem(
    id: 'files',
    title: 'Work with files',
    description: 'Read, write, and organize files in your workspace.',
    icon: '\u{1F4C1}',
  ),
];

class LearnChecklistState {
  final bool dismissed;
  final Set<String> completed;
  const LearnChecklistState({
    this.dismissed = false,
    this.completed = const {},
  });
}

class LearnChecklistNotifier extends StateNotifier<LearnChecklistState> {
  LearnChecklistNotifier() : super(const LearnChecklistState()) {
    _load();
  }

  Future<void> _load() async {
    final prefs = await SharedPreferences.getInstance();
    state = LearnChecklistState(
      dismissed: prefs.getBool(_dismissedKey) ?? false,
      completed: (prefs.getStringList(_completedKey) ?? []).toSet(),
    );
  }

  Future<void> _save() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_dismissedKey, state.dismissed);
    await prefs.setStringList(_completedKey, state.completed.toList());
  }

  void dismiss() {
    state = LearnChecklistState(dismissed: true, completed: state.completed);
    _save();
  }

  Future<void> reset() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_dismissedKey);
    await prefs.remove(_completedKey);
    state = const LearnChecklistState();
  }

  void complete(String id) {
    final updated = Set<String>.from(state.completed)..add(id);
    state = LearnChecklistState(dismissed: state.dismissed, completed: updated);
    _save();
  }
}

final learnChecklistProvider =
    StateNotifierProvider<LearnChecklistNotifier, LearnChecklistState>((ref) {
  return LearnChecklistNotifier();
});
