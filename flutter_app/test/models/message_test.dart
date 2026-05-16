import 'package:executive_assistant/models/message.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('WsMessage', () {
    test('fromJson parses simple message', () {
      final json = {'type': 'ai_token', 'content': 'hello'};
      final m = WsMessage.fromJson(json);
      expect(m.type, 'ai_token');
      expect(m['content'], 'hello');
    });

    test('fromJson stores full data map', () {
      final json = {'type': 'interrupt', 'call_id': 'abc', 'tool': 'email_send', 'args': {'to': 'x'}};
      final m = WsMessage.fromJson(json);
      expect(m.type, 'interrupt');
      expect(m['call_id'], 'abc');
      expect(m['args'], {'to': 'x'});
    });

    test('operator[] returns null for missing key', () {
      final m = WsMessage(type: 'pong', data: {'type': 'pong'});
      expect(m['missing'], isNull);
    });

    test('toString does not leak content', () {
      final m = WsMessage(type: 'ai_token', data: {'type': 'ai_token', 'content': 'secret'});
      expect(m.toString(), isNot(contains('secret')));
      expect(m.toString(), contains('type'));
    });
  });

  group('ChatMessage', () {
    test('constructs with defaults', () {
      final m = ChatMessage(id: '1', role: 'user', content: 'hi', timestamp: DateTime(2024));
      expect(m.content, 'hi');
      expect(m.toolCalls, isEmpty);
    });

    test('copyWith updates content', () {
      final m = ChatMessage(id: '1', role: 'assistant', content: 'hi', timestamp: DateTime(2024));
      final updated = m.copyWith(content: 'hello');
      expect(updated.content, 'hello');
      expect(updated.id, '1'); // unchanged
      expect(updated.role, 'assistant'); // unchanged
    });

    test('copyWith preserves toolCalls', () {
      final tc = ToolCallDisplay(callId: 'c1', toolName: 't', args: {});
      final m = ChatMessage(id: '1', role: 'assistant', content: '', toolCalls: [tc], timestamp: DateTime(2024));
      final updated = m.copyWith(content: 'done');
      expect(updated.toolCalls.length, 1);
      expect(updated.toolCalls.first.callId, 'c1');
    });
  });

  group('ToolCallDisplay', () {
    test('constructs with defaults', () {
      final tc = ToolCallDisplay(callId: 'c1', toolName: 'email_send', args: {'to': 'a@b.com'});
      expect(tc.resultPreview, isNull);
      expect(tc.isPending, false);
    });

    test('copyWith updates resultPreview', () {
      final tc = ToolCallDisplay(callId: 'c1', toolName: 't', args: {});
      final updated = tc.copyWith(resultPreview: 'done');
      expect(updated.resultPreview, 'done');
      expect(updated.callId, 'c1');
    });

    test('copyWith updates isPending', () {
      final tc = ToolCallDisplay(callId: 'c1', toolName: 't', args: {}, isPending: false);
      final updated = tc.copyWith(isPending: true);
      expect(updated.isPending, true);
    });
  });
}
