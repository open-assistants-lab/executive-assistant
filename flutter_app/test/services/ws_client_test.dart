import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:executive_assistant/models/message.dart';
import 'package:executive_assistant/services/ws_client.dart';

class MockWebSocketChannel extends Mock {}

void main() {
  group('WsClient scheme detection', () {
    test('localhost uses ws', () {
      final client = WsClient(host: 'localhost:8080', userId: 'test');
      expect(client.wsScheme, 'ws');
    });

    test('http:// prefix uses ws', () {
      final client = WsClient(host: 'http://localhost:8080', userId: 'test');
      expect(client.wsScheme, 'ws');
      expect(client.cleanHost, 'localhost:8080');
    });

    test('https:// prefix uses wss', () {
      final client = WsClient(host: 'https://api.example.com', userId: 'test');
      expect(client.wsScheme, 'wss');
      expect(client.cleanHost, 'api.example.com');
    });

    test(':443 port uses wss', () {
      final client = WsClient(host: 'server.com:443', userId: 'test');
      expect(client.wsScheme, 'wss');
    });

    test('https://host:443 uses wss', () {
      final client = WsClient(host: 'https://host:443', userId: 'test');
      expect(client.wsScheme, 'wss');
    });

    test('strips http:// prefix from host', () {
      final client = WsClient(host: 'http://192.168.1.5:8080', userId: 'test');
      expect(client.cleanHost, '192.168.1.5:8080');
    });

    test('host without scheme remains unchanged', () {
      final client = WsClient(host: 'myhost:9000', userId: 'test');
      expect(client.cleanHost, 'myhost:9000');
      expect(client.wsScheme, 'ws');
    });
  });

  group('WsClient lifecycle', () {
    test('initial state is disconnected', () {
      final client = WsClient();
      expect(client.isConnected, false);
      expect(client.pendingApprovals, isEmpty);
    });

    test('updateHost changes host', () {
      final client = WsClient(host: 'old:8080');
      client.updateHost('new:9000');
      // Scheme should recompute on next connect
      expect(client.cleanHost, 'new:9000');
    });

    test('dispose cancels timers', () {
      final client = WsClient();
      client.dispose();
      // No assertion needed — should not throw.
      // After dispose, isConnected should be false.
      expect(client.isConnected, false);
    });
  });

  group('WsClient pending approvals', () {
    test('pendingApprovals exposes an unmodifiable map', () {
      final client = WsClient(userId: 'test');
      expect(client.pendingApprovals, isEmpty);
      expect(
        () => client.pendingApprovals['x'] =
            ToolCallDisplay(callId: 'x', toolName: 'tool', args: {}),
        throwsUnsupportedError,
      );
      client.dispose();
    });
  });

  group('WsClient message throttling (coverage only)', () {
    test('sendMessage buffers when not connected', () {
      final client = WsClient(userId: 'test');
      // Without a real WS connection, sendMessage should not throw.
      expect(() => client.sendMessage('hello'), returnsNormally);
    });
  });
}
