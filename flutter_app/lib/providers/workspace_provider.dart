import 'dart:convert';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'agent_provider.dart';

final workspaceScrollPositions = StateProvider<Map<String, double>>((ref) => {});

final currentWorkspaceIdProvider = StateProvider<String>((ref) => 'personal');
final currentWorkspaceNameProvider = StateProvider<String>((ref) => 'Personal');

final workspaceListProvider = FutureProvider<List<Map<String, dynamic>>>((ref) async {
  final host = ref.read(hostProvider);
  final userId = ref.read(userIdProvider);
  final url = Uri.parse('http://$host/workspaces?user_id=$userId');
  try {
    final response = await http.get(url);
    if (response.statusCode == 200) {
      final data = jsonDecode(response.body) as Map<String, dynamic>;
      return List<Map<String, dynamic>>.from(data['workspaces'] ?? []);
    }
  } catch (_) {}
  return [];
});

class WorkspaceNotifier extends StateNotifier<String> {
  final Ref ref;

  WorkspaceNotifier(this.ref) : super('personal');

  Future<void> switchWorkspace(String id, String name) async {
    state = id;
    ref.read(currentWorkspaceIdProvider.notifier).state = id;
    ref.read(currentWorkspaceNameProvider.notifier).state = name;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('active_workspace_id', id);

    ref.read(agentProvider.notifier).setWorkspaceId(id);
    ref.read(apiClientProvider).workspaceId = id;
    ref.read(agentProvider.notifier).clearHistory();
    ref.read(agentProvider.notifier).loadHistory();
  }

  Future<void> createWorkspace(String name, String description, String instructions) async {
    final host = ref.read(hostProvider);
    final userId = ref.read(userIdProvider);
    final url = Uri.parse('http://$host/workspaces?user_id=$userId');
    try {
      final response = await http.post(url,
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({
        'name': name,
        'description': description,
        'instructions': instructions,
      }));
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final id = data['id']?.toString() ?? '';
        final wsName = data['name']?.toString() ?? name;
        ref.invalidate(workspaceListProvider);
        await switchWorkspace(id, wsName);
      }
    } catch (_) {}
  }

  Future<void> deleteWorkspace(String id) async {
    final host = ref.read(hostProvider);
    final userId = ref.read(userIdProvider);
    final url = Uri.parse('http://$host/workspaces/$id?user_id=$userId');
    try {
      await http.delete(url);
      ref.invalidate(workspaceListProvider);
    } catch (_) {}
  }
}

final workspaceNotifierProvider =
    StateNotifierProvider<WorkspaceNotifier, String>((ref) {
  return WorkspaceNotifier(ref);
});
