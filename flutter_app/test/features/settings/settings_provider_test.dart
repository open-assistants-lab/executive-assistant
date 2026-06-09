import 'dart:convert';
import 'package:executive_assistant/features/settings/providers/settings_provider.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('SettingsState', () {
    test('default state has correct values', () {
      final state = const SettingsState();
      expect(state.host, '127.0.0.1:8080');
      expect(state.defaultModel, 'deepseek:deepseek-v4-flash');
      expect(state.providerKeys, isEmpty);
      expect(state.loading, isFalse);
    });

    test('copyWith overrides specified fields', () {
      final state = const SettingsState();
      final modified = state.copyWith(host: 'other:9090');
      expect(modified.host, 'other:9090');
      expect(modified.defaultModel, 'deepseek:deepseek-v4-flash');
    });

    test('copyWith with error converts to string', () {
      final state = const SettingsState();
      final modified = state.copyWith(error: Exception('test'));
      expect(modified.error, contains('test'));
    });
  });

  group('SettingsNotifier', () {
    test('starts with default state via provider', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);
      final state = container.read(settingsProvider);
      expect(state.host, '127.0.0.1:8080');
      expect(state.providerKeys, isEmpty);
    });

    test('setApiKey updates state', () async {
      SharedPreferences.setMockInitialValues({});
      final container = ProviderContainer();
      addTearDown(container.dispose);
      await container.read(settingsProvider.notifier).setApiKey('openai', 'sk-test');
      final state = container.read(settingsProvider);
      expect(state.providerKeys, {'openai': 'sk-test'});
    });

    test('setApiKey persists to SharedPreferences', () async {
      SharedPreferences.setMockInitialValues({});
      final container = ProviderContainer();
      addTearDown(container.dispose);
      await container.read(settingsProvider.notifier).setApiKey('openai', 'sk-test');
      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString('ea_key_openai'), 'sk-test');
    });

    test('removeApiKey removes key', () async {
      SharedPreferences.setMockInitialValues({});
      final container = ProviderContainer();
      addTearDown(container.dispose);
      final notifier = container.read(settingsProvider.notifier);
      await notifier.setApiKey('openai', 'sk-test');
      await notifier.removeApiKey('openai');
      expect(container.read(settingsProvider).providerKeys, isEmpty);
    });

    test('setDefaultModel updates state', () async {
      SharedPreferences.setMockInitialValues({});
      final container = ProviderContainer();
      addTearDown(container.dispose);
      await container.read(settingsProvider.notifier).setDefaultModel('gpt-4');
      expect(container.read(settingsProvider).defaultModel, 'gpt-4');
    });

    test('setHost updates state', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);
      container.read(settingsProvider.notifier).setHost('localhost:9090');
      expect(container.read(settingsProvider).host, 'localhost:9090');
    });

    test('testApiKey returns valid result type', () async {
      final container = ProviderContainer();
      addTearDown(container.dispose);
      final result = await container.read(settingsProvider.notifier).testApiKey('openai', 'sk-test');
      expect(result, isA<({bool valid, String? error})>());
    });

    test('load() reads keys from SharedPreferences', () async {
      SharedPreferences.setMockInitialValues({
        'ea_host': 'localhost:9090',
        'ea_model': 'gpt-4',
        'ea_key_openai': 'sk-test',
        'ea_key_anthropic': 'ant-test',
      });
      final container = ProviderContainer();
      addTearDown(container.dispose);
      await container.read(settingsProvider.notifier).load();
      final state = container.read(settingsProvider);
      expect(state.host, 'localhost:9090');
      expect(state.defaultModel, 'gpt-4');
      expect(state.providerKeys, {'openai': 'sk-test', 'anthropic': 'ant-test'});
    });
  });
}
