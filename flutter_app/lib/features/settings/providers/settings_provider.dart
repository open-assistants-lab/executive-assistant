import 'dart:convert';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import '../../../core/error_messages.dart';
import '../../../providers/agent_provider.dart';

class SettingsState {
  final String host;
  final String defaultModel;
  final Map<String, String> providerKeys;
  final Map<String, bool> providerKeyStatus;
  final bool loading;
  final String? error;

  const SettingsState({
    this.host = '127.0.0.1:8080',
    this.defaultModel = 'deepseek:deepseek-v4-flash',
    this.providerKeys = const {},
    this.providerKeyStatus = const {},
    this.loading = false,
    this.error,
  });

  SettingsState copyWith({
    String? host,
    String? defaultModel,
    Map<String, String>? providerKeys,
    Map<String, bool>? providerKeyStatus,
    bool? loading,
    Object? error,
  }) {
    return SettingsState(
      host: host ?? this.host,
      defaultModel: defaultModel ?? this.defaultModel,
      providerKeys: providerKeys ?? this.providerKeys,
      providerKeyStatus: providerKeyStatus ?? this.providerKeyStatus,
      loading: loading ?? this.loading,
      error: error != null ? error.toString() : this.error,
    );
  }
}

class SettingsNotifier extends StateNotifier<SettingsState> {
  SettingsNotifier(this.ref) : super(const SettingsState());
  final Ref ref;

  String get _baseUrl => 'http://${state.host}';

  Future<void> load() async {
    final prefs = await SharedPreferences.getInstance();
    final host = prefs.getString('ea_host') ?? '127.0.0.1:8080';
    final model = prefs.getString('ea_model') ?? 'deepseek:deepseek-v4-flash';
    final keys = <String, String>{};
    for (final key in prefs.getKeys()) {
      if (key.startsWith('ea_key_')) {
        final pid = key.substring(7);
        final val = prefs.getString(key);
        if (val != null && val.isNotEmpty) keys[pid] = val;
      }
    }
    state = SettingsState(
      host: host,
      defaultModel: model,
      providerKeys: keys,
    );

    ref.read(selectedModelProvider.notifier).state = model;
    ref.read(providerKeysProvider.notifier).state = Map.from(keys);

    try {
      final resp = await http.get(
        Uri.parse('http://$host/settings?user_id=default_user'),
      );
      if (resp.statusCode == 200) {
        final data = jsonDecode(resp.body) as Map<String, dynamic>;
        final status = <String, bool>{};
        final providerStatus =
            data['provider_status'] as Map<String, dynamic>? ?? {};
        for (final entry in providerStatus.entries) {
          status[entry.key] = (entry.value as Map)['has_key'] == true;
        }
        state = state.copyWith(
          providerKeyStatus: status,
          defaultModel: data['default_model'] as String? ?? model,
        );
      }
    } catch (_) {}
  }

  Future<void> setDefaultModel(String model) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('ea_model', model);
    state = state.copyWith(defaultModel: model);
    ref.read(selectedModelProvider.notifier).state = model;
    ref.read(agentProvider.notifier).updateModel(model);
    try {
      await http.patch(
        Uri.parse('$_baseUrl/settings?user_id=default_user'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'default_model': model}),
      );
    } catch (_) {}
  }

  Future<void> setApiKey(String provider, String apiKey) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('ea_key_$provider', apiKey);
    state = state.copyWith(
      providerKeys: {...state.providerKeys, provider: apiKey},
      providerKeyStatus: {
        ...state.providerKeyStatus,
        provider: apiKey.isNotEmpty,
      },
    );
    ref.read(providerKeysProvider.notifier).state = Map.from(state.providerKeys);
    ref
        .read(agentProvider.notifier)
        .updateProviderKeys(Map.from(state.providerKeys));
    try {
      await http.post(
        Uri.parse('$_baseUrl/settings/api-keys?user_id=default_user'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'provider': provider, 'api_key': apiKey}),
      );
    } catch (_) {}
  }

  Future<({bool valid, String? error})> testApiKey(
    String provider,
    String apiKey,
  ) async {
    try {
      final resp = await http.post(
        Uri.parse('$_baseUrl/settings/test-key'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'provider': provider, 'api_key': apiKey}),
      );
      final data = jsonDecode(resp.body) as Map<String, dynamic>;
      final valid = data['valid'] == true;
      return (valid: valid, error: data['error'] as String?);
    } catch (e) {
      return (valid: false, error: humanReadableError('Could not reach backend: $e'));
    }
  }

  Future<void> removeApiKey(String provider) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('ea_key_$provider');
    final keys = Map<String, String>.from(state.providerKeys)..remove(provider);
    final status = Map<String, bool>.from(state.providerKeyStatus)
      ..remove(provider);
    state = state.copyWith(providerKeys: keys, providerKeyStatus: status);
    ref.read(providerKeysProvider.notifier).state = keys;
    try {
      await http.delete(
        Uri.parse(
          '$_baseUrl/settings/api-keys/$provider?user_id=default_user',
        ),
      );
    } catch (_) {}
  }

  void setHost(String host) {
    SharedPreferences.getInstance().then((p) => p.setString('ea_host', host));
    state = state.copyWith(host: host);
    ref.read(hostProvider.notifier).state = host;
    ref.read(agentProvider.notifier).updateHost(host);
  }
}

final settingsProvider =
    StateNotifierProvider<SettingsNotifier, SettingsState>((ref) {
  return SettingsNotifier(ref);
});
