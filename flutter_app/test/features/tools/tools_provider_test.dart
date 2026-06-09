import 'dart:convert';
import 'package:executive_assistant/features/tools/tools_provider.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  group('ToolItem', () {
    test('fromJson parses all fields', () {
      final item = ToolItem.fromJson({
        'name': 'test_tool',
        'description': 'A test tool',
        'category': 'files',
        'annotations': {'read_only': true},
        'parameters': {'type': 'object'},
        'enabled': true,
        'source': 'native',
        'scope': 'all',
        'workspace_ids': ['personal'],
      });
      expect(item.name, 'test_tool');
      expect(item.description, 'A test tool');
      expect(item.category, 'files');
      expect(item.isReadOnly, isTrue);
      expect(item.isDestructive, isFalse);
      expect(item.scope, 'all');
      expect(item.workspaceIds, ['personal']);
    });

    test('fromJson handles missing fields', () {
      final item = ToolItem.fromJson({'name': 'minimal'});
      expect(item.name, 'minimal');
      expect(item.description, '');
      expect(item.category, 'core');
      expect(item.isReadOnly, isFalse);
      expect(item.isDestructive, isFalse);
      expect(item.scope, 'all');
      expect(item.workspaceIds, isEmpty);
    });

    test('isDestructive returns true when annotated', () {
      final item = ToolItem.fromJson({
        'name': 'delete',
        'annotations': {'destructive': true},
      });
      expect(item.isDestructive, isTrue);
    });
  });

  group('ToolsState', () {
    test('default state has empty tools', () {
      const state = ToolsState();
      expect(state.tools, isEmpty);
      expect(state.loading, isFalse);
      expect(state.searchQuery, '');
      expect(state.totalEnabled, 0);
    });

    test('filteredTools filters by search query', () {
      final state = ToolsState(
        tools: [
          ToolItem.fromJson({'name': 'files_read', 'description': 'Read files'}),
          ToolItem.fromJson({'name': 'email_send', 'description': 'Send email'}),
        ],
        searchQuery: 'email',
      );
      expect(state.filteredTools.length, 1);
      expect(state.filteredTools[0].name, 'email_send');
    });

    test('filteredTools returns all when no query', () {
      final state = ToolsState(
        tools: [
          ToolItem.fromJson({'name': 'a'}),
          ToolItem.fromJson({'name': 'b'}),
        ],
      );
      expect(state.filteredTools.length, 2);
    });

    test('totalEnabled counts enabled tools', () {
      final state = ToolsState(
        tools: [
          ToolItem.fromJson({'name': 'a', 'enabled': true}),
          ToolItem.fromJson({'name': 'b', 'enabled': false}),
          ToolItem.fromJson({'name': 'c', 'enabled': true}),
        ],
      );
      expect(state.totalEnabled, 2);
    });
  });

  group('ToolsNotifier', () {
    test('starts with default state', () {
      final notifier = ToolsNotifier(http.Client());
      expect(notifier.state.tools, isEmpty);
      expect(notifier.state.loading, isFalse);
    });

    test('setSearch updates query', () {
      final notifier = ToolsNotifier(http.Client());
      notifier.setSearch('test');
      expect(notifier.state.searchQuery, 'test');
    });

    test('loadTools sets error on failure', () async {
      final mockClient = MockClient((_) async => http.Response('{}', 500));
      final notifier = ToolsNotifier(mockClient);
      await notifier.loadTools(host: 'localhost', userId: 'u', workspaceId: 'w');
      expect(notifier.state.error, isNotNull);
      expect(notifier.state.loading, isFalse);
    });

    test('loadTools parses tools on success', () async {
      final mockClient = MockClient((_) async => http.Response(jsonEncode({
        'tools': [
          {'name': 'files_read', 'description': 'Read files', 'category': 'files'},
        ],
        'categories': {
          'files': {'count': 1, 'enabled': 1},
        },
      }), 200));
      final notifier = ToolsNotifier(mockClient);
      await notifier.loadTools(host: 'localhost', userId: 'u', workspaceId: 'w');
      expect(notifier.state.tools.length, 1);
      expect(notifier.state.tools[0].name, 'files_read');
      expect(notifier.state.categories['files']?.count, 1);
    });

    test('toggleTool updates state optimistically', () async {
      final mockClient = MockClient((_) async => http.Response('{}', 200));
      final notifier = ToolsNotifier(mockClient);
      notifier.state = ToolsState(
        tools: [ToolItem.fromJson({'name': 'test_tool', 'enabled': false})],
      );
      await notifier.toggleTool(
        host: 'localhost', userId: 'u', workspaceId: 'w',
        toolName: 'test_tool', enabled: true,
      );
      expect(notifier.state.tools[0].enabled, isTrue);
    });
  });
}
