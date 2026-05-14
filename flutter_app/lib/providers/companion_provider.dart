import 'dart:async';
import 'dart:convert';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../models/companion.dart';
import '../../services/api_client.dart';

final companionClientProvider = Provider<ApiClient>((ref) {
  return ApiClient();
});

final companionPausedProvider = StateProvider<bool>((ref) => false);

final companionStatusProvider = FutureProvider.autoDispose<CompanionStatus>((ref) {
  final client = ref.watch(companionClientProvider);
  return client.getCompanionStatus();
});

final companionNotificationsProvider = FutureProvider.autoDispose<List<CompanionNotification>>((ref) {
  final client = ref.watch(companionClientProvider);
  return client.getCompanionNotifications(limit: 50);
});

final companionActiveToastProvider = StateProvider<CompanionNotification?>((ref) => null);

final companionMemoryProvider = FutureProvider.autoDispose<List<CompanionMemoryFact>>((ref) {
  final client = ref.watch(companionClientProvider);
  return client.getCompanionMemory();
});

class CompanionNotifier extends StateNotifier<List<CompanionNotification>> {
  final ApiClient _client;
  Timer? _pollTimer;
  Timer? _statusTimer;

  CompanionNotifier(this._client) : super([]) {
    fetch();
    _pollTimer = Timer.periodic(const Duration(seconds: 30), (_) => fetch());
  }

  Future<void> fetch() async {
    try {
      final notifs = await _client.getCompanionNotifications(limit: 50);
      state = notifs;
    } catch (_) {}
  }

  Future<void> dismiss(String id) async {
    try {
      await _client.dismissCompanionNotification(id);
      state = state.map((n) => n.id == id ? n.copyWith(dismissed: true) : n).toList();
    } catch (_) {}
  }

  Future<void> pause() async {
    try {
      await _client.pauseCompanion();
    } catch (_) {}
  }

  Future<void> resume() async {
    try {
      await _client.resumeCompanion();
    } catch (_) {}
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    _statusTimer?.cancel();
    super.dispose();
  }
}

final companionNotifierProvider = StateNotifierProvider<CompanionNotifier, List<CompanionNotification>>((ref) {
  final client = ref.watch(companionClientProvider);
  return CompanionNotifier(client);
});
