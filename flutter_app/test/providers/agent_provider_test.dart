import 'dart:async';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:executive_assistant/models/message.dart';
import 'package:executive_assistant/services/ws_client.dart';
import 'package:executive_assistant/services/api_client.dart';
import 'package:executive_assistant/providers/agent_provider.dart';

class MockWsClient extends Mock implements WsClient {}

class MockApiClient extends Mock implements ApiClient {}

void _registerFallbacks() {
  registerFallbackValue(StreamController<WsMessage>.broadcast());
  registerFallbackValue(StreamController<ConnectionStatus>.broadcast());
}

void main() {
  _registerFallbacks();

  group('AgentNotifier constructor', () {
    test('initial state is disconnected', () {
      final ws = MockWsClient();
      final api = MockApiClient();
      when(() => ws.status).thenAnswer((_) => Stream.empty());
      when(() => ws.messages).thenAnswer((_) => Stream.empty());

      final notifier = AgentNotifier(ws, api);
      expect(notifier.state.status, ChatStatus.disconnected);
      expect(notifier.state.messages, isEmpty);
      expect(notifier.state.connected, false);
      notifier.dispose();
    });
  });

  group('AgentNotifier connection state changes', () {
    late MockWsClient mockWs;
    late MockApiClient mockApi;
    late AgentNotifier notifier;

    setUp(() {
      mockWs = MockWsClient();
      mockApi = MockApiClient();
      when(() => mockWs.status).thenAnswer((_) => Stream.empty());
      when(() => mockWs.messages).thenAnswer((_) => Stream.empty());
      notifier = AgentNotifier(mockWs, mockApi);
    });

    tearDown(() {
      notifier.dispose();
    });

    test('connect invokes wsClient.connect', () {
      when(() => mockWs.connect()).thenReturn(null);
      notifier.connect();
      verify(() => mockWs.connect()).called(1);
    });

    test('sendMessage shows error when not connected', () {
      notifier.sendMessage('hello');
      expect(notifier.state.status, ChatStatus.error);
      expect(notifier.state.error, contains('Not connected'));
    });

    test('clearError resets to disconnected when offline', () {
      notifier.clearError();
      expect(notifier.state.status, ChatStatus.disconnected);
      expect(notifier.state.error, isNull);
    });

    test('sendMessage does nothing for empty content', () {
      final before = notifier.state.messages.length;
      notifier.sendMessage('   ');
      expect(notifier.state.messages.length, before);
    });
  });

  group('AgentNotifier tool approval', () {
    late MockWsClient mockWs;
    late MockApiClient mockApi;
    late AgentNotifier notifier;

    setUp(() {
      mockWs = MockWsClient();
      mockApi = MockApiClient();
      when(() => mockWs.status).thenAnswer((_) => Stream.empty());
      when(() => mockWs.messages).thenAnswer((_) => Stream.empty());
      notifier = AgentNotifier(mockWs, mockApi);
    });

    tearDown(() {
      notifier.dispose();
    });

    test('approveToolCall delegates to wsClient', () {
      when(() => mockWs.approveToolCall(any())).thenReturn(null);
      notifier.approveToolCall('c1');
      verify(() => mockWs.approveToolCall('c1')).called(1);
    });

    test('rejectToolCall delegates to wsClient', () {
      when(
        () => mockWs.rejectToolCall(any(), reason: any(named: 'reason')),
      ).thenReturn(null);
      notifier.rejectToolCall('c2', reason: 'nope');
      verify(() => mockWs.rejectToolCall('c2', reason: 'nope')).called(1);
    });

    test('rejectToolCall sets idle when no pending remain', () {
      when(
        () => mockWs.rejectToolCall(any(), reason: any(named: 'reason')),
      ).thenReturn(null);
      notifier.rejectToolCall('x');
      expect(notifier.state.status, ChatStatus.idle);
    });
  });

  group('AgentNotifier host/userId updates', () {
    late MockWsClient mockWs;
    late MockApiClient mockApi;
    late AgentNotifier notifier;

    setUp(() {
      mockWs = MockWsClient();
      mockApi = MockApiClient();
      when(() => mockWs.status).thenAnswer((_) => Stream.empty());
      when(() => mockWs.messages).thenAnswer((_) => Stream.empty());
      notifier = AgentNotifier(mockWs, mockApi);
    });

    tearDown(() {
      notifier.dispose();
    });

    test('updateHost delegates to both clients', () {
      when(() => mockWs.updateHost(any())).thenReturn(null);
      when(() => mockApi.updateHost(any())).thenReturn(null);
      notifier.updateHost('newhost:9000');
      verify(() => mockWs.updateHost('newhost:9000')).called(1);
      verify(() => mockApi.updateHost('newhost:9000')).called(1);
    });

    test('updateUserId delegates to both clients', () {
      when(() => mockWs.updateUserId(any())).thenReturn(null);
      when(() => mockApi.updateUserId(any())).thenReturn(null);
      notifier.updateUserId('alice');
      verify(() => mockWs.updateUserId('alice')).called(1);
      verify(() => mockApi.updateUserId('alice')).called(1);
    });
  });

  group('AgentNotifier message stream handling', () {
    late MockWsClient mockWs;
    late MockApiClient mockApi;
    late AgentNotifier notifier;
    late StreamController<WsMessage> msgCtrl;
    late StreamController<ConnectionStatus> statusCtrl;

    setUp(() {
      msgCtrl = StreamController<WsMessage>.broadcast();
      statusCtrl = StreamController<ConnectionStatus>.broadcast();
      mockWs = MockWsClient();
      mockApi = MockApiClient();
      when(() => mockWs.status).thenAnswer((_) => statusCtrl.stream);
      when(() => mockWs.messages).thenAnswer((_) => msgCtrl.stream);
      when(
        () => mockApi.getConversation(
          limit: any(named: 'limit'),
          workspaceId: any(named: 'workspaceId'),
        ),
      ).thenAnswer((_) async => []);
      notifier = AgentNotifier(mockWs, mockApi);
    });

    tearDown(() {
      notifier.dispose();
      msgCtrl.close();
      statusCtrl.close();
    });

    test('text_delta accumulates streamingText', () async {
      statusCtrl.add(ConnectionStatus.connected);
      await Future.delayed(Duration.zero);

      msgCtrl.add(
        WsMessage(
          type: 'text_delta',
          data: {'type': 'text_delta', 'content': 'Hello'},
        ),
      );
      await Future.delayed(Duration.zero);
      expect(notifier.state.streamingText, 'Hello');

      msgCtrl.add(
        WsMessage(
          type: 'text_delta',
          data: {'type': 'text_delta', 'content': ' world'},
        ),
      );
      await Future.delayed(Duration.zero);
      expect(notifier.state.streamingText, 'Hello world');
    });

    test('tool_input_delta content updates active tool args', () async {
      statusCtrl.add(ConnectionStatus.connected);
      await Future.delayed(Duration.zero);

      msgCtrl.add(
        WsMessage(
          type: 'tool_input_start',
          data: {
            'type': 'tool_input_start',
            'tool': 'email_send',
            'call_id': 'c1',
            'args': {},
          },
        ),
      );
      msgCtrl.add(
        WsMessage(
          type: 'tool_input_delta',
          data: {
            'type': 'tool_input_delta',
            'call_id': 'c1',
            'content': '{"to":"boss@example.com"}',
          },
        ),
      );
      msgCtrl.add(
        WsMessage(
          type: 'tool_input_end',
          data: {
            'type': 'tool_input_end',
            'call_id': 'c1',
            'tool': 'email_send',
          },
        ),
      );
      await Future.delayed(Duration.zero);

      expect(notifier.state.activeToolCalls, hasLength(1));
      expect(notifier.state.activeToolCalls.single.args, {
        'to': 'boss@example.com',
      });
    });

    test(
      'ignores stream events from previous workspace after switching',
      () async {
        when(
          () =>
              mockWs.sendMessage(any(), workspaceId: any(named: 'workspaceId')),
        ).thenReturn(null);
        when(
          () => mockApi.getConversation(
            limit: any(named: 'limit'),
            workspaceId: any(named: 'workspaceId'),
          ),
        ).thenAnswer((_) async => []);
        statusCtrl.add(ConnectionStatus.connected);
        await Future.delayed(Duration.zero);

        notifier.setWorkspaceId('test-12');
        notifier.sendMessage('how is the weather today');
        notifier.setWorkspaceId('test');
        notifier.clearHistory();

        msgCtrl.add(
          WsMessage(
            type: 'tool_input_start',
            data: {
              'type': 'tool_input_start',
              'tool': 'web_search',
              'call_id': 'weather-call',
              'args': {'query': 'weather today'},
            },
          ),
        );
        await Future.delayed(Duration.zero);

        expect(notifier.state.activeToolCalls, isEmpty);
        expect(notifier.state.status, ChatStatus.idle);
      },
    );

    test('clearHistory marks history as loading', () async {
      notifier.clearHistory(loading: true);

      expect(notifier.state.loadingHistory, isTrue);
    });

    test(
      'restores in-progress tool calls after switching away and back',
      () async {
        when(
          () =>
              mockWs.sendMessage(any(), workspaceId: any(named: 'workspaceId')),
        ).thenReturn(null);
        when(
          () => mockApi.getConversation(
            limit: any(named: 'limit'),
            workspaceId: any(named: 'workspaceId'),
          ),
        ).thenAnswer((_) async => []);
        statusCtrl.add(ConnectionStatus.connected);
        await Future.delayed(Duration.zero);

        notifier.setWorkspaceId('test-12');
        notifier.sendMessage('are you sure');
        msgCtrl.add(
          WsMessage(
            type: 'tool_input_start',
            data: {
              'type': 'tool_input_start',
              'workspace_id': 'test-12',
              'tool': 'web_search',
              'call_id': 'search-1',
              'args': {'query': 'weather'},
            },
          ),
        );
        await Future.delayed(Duration.zero);
        expect(notifier.state.activeToolCalls, hasLength(1));

        notifier.setWorkspaceId('test');
        notifier.clearHistory(loading: true);
        expect(notifier.state.activeToolCalls, isEmpty);

        notifier.setWorkspaceId('test-12');

        expect(notifier.state.activeToolCalls, hasLength(1));
        expect(notifier.state.activeToolCalls.single.toolName, 'web_search');
      },
    );

    test(
      'ignores history response after switching to another workspace',
      () async {
        final oldWorkspaceResponse = Completer<List<Map<String, dynamic>>>();
        final currentWorkspaceResponse =
            Completer<List<Map<String, dynamic>>>();
        when(
          () => mockApi.getConversation(
            limit: any(named: 'limit'),
            workspaceId: 'test2',
          ),
        ).thenAnswer((_) => oldWorkspaceResponse.future);
        when(
          () => mockApi.getConversation(
            limit: any(named: 'limit'),
            workspaceId: 'test12345',
          ),
        ).thenAnswer((_) => currentWorkspaceResponse.future);

        notifier.setWorkspaceId('test2');
        final oldLoad = notifier.loadHistory();
        notifier.setWorkspaceId('test12345');
        notifier.clearHistory(loading: true);
        final currentLoad = notifier.loadHistory();

        currentWorkspaceResponse.complete([
          {
            'role': 'user',
            'content': 'message from test12345',
            'timestamp': DateTime.now().toIso8601String(),
            'metadata': {'workspace_id': 'test12345'},
          },
        ]);
        await currentLoad;

        oldWorkspaceResponse.complete([
          {
            'role': 'user',
            'content': 'message from test2',
            'timestamp': DateTime.now().toIso8601String(),
            'metadata': {'workspace_id': 'test2'},
          },
          {
            'role': 'assistant',
            'content': 'second message from test2',
            'timestamp': DateTime.now().toIso8601String(),
            'metadata': {'workspace_id': 'test2'},
          },
        ]);
        await oldLoad;

        expect(notifier.state.messages.map((m) => m.content), [
          'message from test12345',
        ]);
        expect(notifier.state.loadingHistory, isFalse);
      },
    );

    test(
      'restored cached workspace inherits current connection status',
      () async {
        when(
          () => mockApi.getConversation(
            limit: any(named: 'limit'),
            workspaceId: any(named: 'workspaceId'),
          ),
        ).thenAnswer((_) async => []);

        notifier.setWorkspaceId('test');
        statusCtrl.add(ConnectionStatus.connected);
        await Future.delayed(Duration.zero);

        notifier.setWorkspaceId('personal');

        expect(notifier.state.connected, isTrue);
        expect(notifier.state.status, ChatStatus.idle);
      },
    );

    test(
      'splits assistant text into separate bubbles around tool calls',
      () async {
        statusCtrl.add(ConnectionStatus.connected);
        await Future.delayed(Duration.zero);

        msgCtrl.add(
          WsMessage(
            type: 'text_delta',
            data: {'type': 'text_delta', 'content': 'First segment.'},
          ),
        );
        msgCtrl.add(
          WsMessage(
            type: 'tool_input_start',
            data: {
              'type': 'tool_input_start',
              'tool': 'web_search',
              'call_id': 'search-1',
              'args': {'query': 'weather'},
            },
          ),
        );
        msgCtrl.add(
          WsMessage(
            type: 'tool_result',
            data: {
              'type': 'tool_result',
              'tool': 'web_search',
              'call_id': 'search-1',
              'result_preview': 'Sunny',
            },
          ),
        );
        msgCtrl.add(
          WsMessage(
            type: 'text_delta',
            data: {'type': 'text_delta', 'content': 'Second segment.'},
          ),
        );
        msgCtrl.add(
          WsMessage(
            type: 'done',
            data: {'type': 'done', 'response': 'First segment.Second segment.'},
          ),
        );
        await Future.delayed(Duration.zero);

        expect(notifier.state.messages.map((m) => m.role), [
          'assistant',
          'tool',
          'assistant',
        ]);
        expect(notifier.state.messages[0].content, 'First segment.');
        expect(notifier.state.messages[2].content, 'Second segment.');
      },
    );

    test('done event finalizes message', () async {
      statusCtrl.add(ConnectionStatus.connected);
      msgCtrl.add(
        WsMessage(
          type: 'text_delta',
          data: {'type': 'text_delta', 'content': 'Result'},
        ),
      );
      msgCtrl.add(
        WsMessage(type: 'done', data: {'type': 'done', 'response': ''}),
      );
      await Future.delayed(Duration.zero);

      final last = notifier.state.messages.last;
      expect(last.role, 'assistant');
      expect(last.content, 'Result');
      expect(notifier.state.status, ChatStatus.idle);
      expect(notifier.state.streamingText, isEmpty);
    });

    test('error event sets error state', () async {
      statusCtrl.add(ConnectionStatus.connected);
      msgCtrl.add(
        WsMessage(
          type: 'error',
          data: {'type': 'error', 'message': 'Something broke'},
        ),
      );
      await Future.delayed(Duration.zero);
      expect(notifier.state.status, ChatStatus.error);
      expect(notifier.state.error, 'Something broke');
    });

    test('connected status sets idle when no activity', () async {
      statusCtrl.add(ConnectionStatus.connected);
      await Future.delayed(Duration.zero);
      expect(notifier.state.connected, true);
      expect(notifier.state.status, ChatStatus.idle);
    });

    test('disconnected status sets offline', () async {
      statusCtrl.add(ConnectionStatus.connected);
      await Future.delayed(Duration.zero);
      statusCtrl.add(ConnectionStatus.disconnected);
      await Future.delayed(Duration.zero);
      expect(notifier.state.connected, false);
      expect(notifier.state.status, ChatStatus.disconnected);
    });
  });

  group('AgentNotifier interrupt handling', () {
    late MockWsClient mockWs;
    late MockApiClient mockApi;
    late AgentNotifier notifier;
    late StreamController<WsMessage> msgCtrl;
    late StreamController<ConnectionStatus> statusCtrl;

    setUp(() {
      msgCtrl = StreamController<WsMessage>.broadcast();
      statusCtrl = StreamController<ConnectionStatus>.broadcast();
      mockWs = MockWsClient();
      mockApi = MockApiClient();
      when(() => mockWs.status).thenAnswer((_) => statusCtrl.stream);
      when(() => mockWs.messages).thenAnswer((_) => msgCtrl.stream);
      when(
        () => mockApi.getConversation(
          limit: any(named: 'limit'),
          workspaceId: any(named: 'workspaceId'),
        ),
      ).thenAnswer((_) async => []);
      notifier = AgentNotifier(mockWs, mockApi);
    });

    tearDown(() {
      notifier.dispose();
      msgCtrl.close();
      statusCtrl.close();
    });

    test('interrupt populates pendingApprovals', () async {
      statusCtrl.add(ConnectionStatus.connected);
      msgCtrl.add(
        WsMessage(
          type: 'interrupt',
          data: {
            'type': 'interrupt',
            'call_id': 'c99',
            'tool': 'email_send',
            'args': {'to': 'boss@example.com'},
          },
        ),
      );
      await Future.delayed(Duration.zero);
      expect(notifier.state.status, ChatStatus.awaitingApproval);
      expect(notifier.state.pendingApprovals.containsKey('c99'), isTrue);
      expect(notifier.state.pendingApprovals['c99']!.toolName, 'email_send');
    });

    test('text_delta after interrupt preserves awaitingApproval', () async {
      statusCtrl.add(ConnectionStatus.connected);
      msgCtrl.add(
        WsMessage(
          type: 'interrupt',
          data: {
            'type': 'interrupt',
            'call_id': 'c1',
            'tool': 'subagent_create',
            'args': {'name': 'test'},
          },
        ),
      );
      msgCtrl.add(
        WsMessage(
          type: 'text_delta',
          data: {'type': 'text_delta', 'content': 'Approval needed...'},
        ),
      );
      await Future.delayed(Duration.zero);
      expect(notifier.state.status, ChatStatus.awaitingApproval);
    });

    test('tool_start after interrupt preserves awaitingApproval', () async {
      statusCtrl.add(ConnectionStatus.connected);
      msgCtrl.add(
        WsMessage(
          type: 'interrupt',
          data: {
            'type': 'interrupt',
            'call_id': 'c1',
            'tool': 'subagent_create',
            'args': {'name': 'test'},
          },
        ),
      );
      msgCtrl.add(
        WsMessage(
          type: 'tool_start',
          data: {
            'type': 'tool_start',
            'call_id': 'c2',
            'tool': 'subagent_list',
            'args': {},
          },
        ),
      );
      await Future.delayed(Duration.zero);
      expect(notifier.state.status, ChatStatus.awaitingApproval);
    });

    test('reasoning after interrupt preserves awaitingApproval', () async {
      statusCtrl.add(ConnectionStatus.connected);
      msgCtrl.add(
        WsMessage(
          type: 'interrupt',
          data: {
            'type': 'interrupt',
            'call_id': 'c1',
            'tool': 'subagent_create',
            'args': {'name': 'test'},
          },
        ),
      );
      msgCtrl.add(
        WsMessage(
          type: 'reasoning',
          data: {'type': 'reasoning', 'content': 'thinking...'},
        ),
      );
      await Future.delayed(Duration.zero);
      expect(notifier.state.status, ChatStatus.awaitingApproval);
    });

    test('tool_call after interrupt preserves awaitingApproval', () async {
      statusCtrl.add(ConnectionStatus.connected);
      msgCtrl.add(
        WsMessage(
          type: 'interrupt',
          data: {
            'type': 'interrupt',
            'call_id': 'c1',
            'tool': 'subagent_create',
            'args': {'name': 'test'},
          },
        ),
      );
      msgCtrl.add(
        WsMessage(
          type: 'tool_call',
          data: {
            'type': 'tool_call',
            'call_id': 'c2',
            'tool': 'subagent_list',
            'args': {},
          },
        ),
      );
      await Future.delayed(Duration.zero);
      expect(notifier.state.status, ChatStatus.awaitingApproval);
    });

    test(
      'done after interrupt preserves awaitingApproval and pendingApprovals',
      () async {
        statusCtrl.add(ConnectionStatus.connected);
        msgCtrl.add(
          WsMessage(
            type: 'interrupt',
            data: {
              'type': 'interrupt',
              'call_id': 'c1',
              'tool': 'shell_execute',
              'args': {'command': 'rm -rf'},
            },
          ),
        );
        msgCtrl.add(
          WsMessage(
            type: 'text_delta',
            data: {
              'type': 'text_delta',
              'content': 'I need your approval for this...',
            },
          ),
        );
        msgCtrl.add(
          WsMessage(type: 'done', data: {'type': 'done', 'response': ''}),
        );
        await Future.delayed(Duration.zero);

        expect(notifier.state.status, ChatStatus.awaitingApproval);
        expect(notifier.state.pendingApprovals.containsKey('c1'), isTrue);
        expect(
          notifier.state.pendingApprovals['c1']!.toolName,
          'shell_execute',
        );
      },
    );
  });
}
