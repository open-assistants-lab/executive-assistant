import 'dart:async';

import 'package:executive_assistant/core/layout/desktop_layout.dart';
import 'package:executive_assistant/providers/agent_provider.dart';
import 'package:executive_assistant/providers/workspace_provider.dart';
import 'package:executive_assistant/services/api_client.dart';
import 'package:executive_assistant/services/ws_client.dart';
import 'package:executive_assistant/models/message.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:shared_preferences/shared_preferences.dart';

class MockWsClient extends Mock implements WsClient {}

class MockApiClient extends Mock implements ApiClient {}

Widget _buildDesktopLayout(MockWsClient ws, MockApiClient api) {
  return ProviderScope(
    overrides: [
      wsClientProvider.overrideWithValue(ws),
      apiClientProvider.overrideWithValue(api),
      workspaceListProvider.overrideWith(
        (ref) async => [
          {'id': 'test', 'name': 'Test'},
          {'id': 'test-12', 'name': 'Test 12'},
        ],
      ),
    ],
    child: const MaterialApp(home: DesktopLayout(child: SizedBox.shrink())),
  );
}

void main() {
  late MockWsClient mockWs;
  late MockApiClient mockApi;
  late StreamController<WsMessage> msgCtrl;
  late StreamController<ConnectionStatus> statusCtrl;

  setUp(() {
    SharedPreferences.setMockInitialValues({});
    msgCtrl = StreamController<WsMessage>.broadcast();
    statusCtrl = StreamController<ConnectionStatus>.broadcast();
    mockWs = MockWsClient();
    mockApi = MockApiClient();

    when(() => mockWs.status).thenAnswer((_) => statusCtrl.stream);
    when(() => mockWs.messages).thenAnswer((_) => msgCtrl.stream);
    when(() => mockWs.connect()).thenReturn(null);
    when(() => mockApi.workspaceId = any<String>()).thenReturn('');
    var testLoads = 0;
    when(
      () => mockApi.getConversation(
        limit: any(named: 'limit'),
        workspaceId: any(named: 'workspaceId'),
      ),
    ).thenAnswer((invocation) async {
      final workspaceId = invocation.namedArguments[#workspaceId] as String;
      if (workspaceId != 'test') return [];
      testLoads++;
      final count = testLoads > 1 ? 50 : 40;
      return List.generate(
        count,
        (i) => {
          'role': 'assistant',
          'content': 'message $i',
          'timestamp': DateTime(2026, 1, 1, 0, i).toIso8601String(),
          'metadata': <String, dynamic>{},
        },
      );
    });
  });

  tearDown(() {
    msgCtrl.close();
    statusCtrl.close();
  });

  testWidgets(
    'restores each workspace chat scroll position after switching tabs',
    (tester) async {
      await tester.pumpWidget(_buildDesktopLayout(mockWs, mockApi));
      statusCtrl.add(ConnectionStatus.connected);
      await tester.pump(const Duration(milliseconds: 100));

      await tester.tap(find.text('Test').first);
      await tester.pump(const Duration(milliseconds: 100));
      await tester.pump(const Duration(milliseconds: 100));

      final messageList = find.byKey(
        const ValueKey('desktop-chat-message-list'),
      );
      await tester.drag(messageList, const Offset(0, -5000));
      await tester.pump(const Duration(milliseconds: 100));
      ScrollableState messageScrollable() => tester.state<ScrollableState>(
        find
            .descendant(of: messageList, matching: find.byType(Scrollable))
            .last,
      );
      expect(messageScrollable().position.extentAfter, lessThan(1));

      await tester.tap(find.text('Test 12').first);
      await tester.pump(const Duration(milliseconds: 100));
      await tester.pump(const Duration(milliseconds: 100));
      expect(find.text('Ask anything...'), findsWidgets);

      await tester.tap(find.text('Test').first);
      await tester.pump(const Duration(milliseconds: 100));
      await tester.pump(const Duration(milliseconds: 100));

      expect(messageScrollable().position.extentAfter, lessThan(1));
    },
  );

  testWidgets(
    'restores saved scroll when switching back to cached workspace state',
    (tester) async {
      when(
        () => mockApi.getConversation(
          limit: any(named: 'limit'),
          workspaceId: any(named: 'workspaceId'),
        ),
      ).thenAnswer((invocation) async {
        final workspaceId = invocation.namedArguments[#workspaceId] as String;
        return List.generate(
          40,
          (i) => {
            'role': 'assistant',
            'content': '$workspaceId message $i',
            'timestamp': DateTime(2026, 1, 1, 0, i).toIso8601String(),
            'metadata': <String, dynamic>{},
          },
        );
      });

      await tester.pumpWidget(_buildDesktopLayout(mockWs, mockApi));
      statusCtrl.add(ConnectionStatus.connected);
      await tester.pump(const Duration(milliseconds: 100));

      await tester.tap(find.text('Test').first);
      await tester.pump(const Duration(milliseconds: 100));
      await tester.pump(const Duration(milliseconds: 100));

      final messageList = find.byKey(
        const ValueKey('desktop-chat-message-list'),
      );
      ScrollableState messageScrollable() => tester.state<ScrollableState>(
        find
            .descendant(of: messageList, matching: find.byType(Scrollable))
            .last,
      );

      await tester.drag(messageList, const Offset(0, -5000));
      await tester.pump(const Duration(milliseconds: 100));
      expect(messageScrollable().position.extentAfter, lessThan(1));

      msgCtrl.add(
        WsMessage(
          type: 'text_delta',
          data: {
            'type': 'text_delta',
            'workspace_id': 'test',
            'content': 'streaming update',
          },
        ),
      );
      await tester.pump(const Duration(milliseconds: 100));

      await tester.tap(find.text('Test 12').first);
      await tester.pump(const Duration(milliseconds: 100));
      await tester.pump(const Duration(milliseconds: 100));

      await tester.drag(messageList, const Offset(0, 5000));
      await tester.pump(const Duration(milliseconds: 100));
      expect(messageScrollable().position.pixels, lessThan(50));

      await tester.tap(find.text('Test').first);
      await tester.pump(const Duration(milliseconds: 100));
      await tester.pump(const Duration(milliseconds: 100));

      expect(messageScrollable().position.extentAfter, lessThan(1));
    },
  );
}
