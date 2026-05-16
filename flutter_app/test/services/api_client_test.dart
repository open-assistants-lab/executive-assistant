import 'dart:async';
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;

import 'package:executive_assistant/services/api_client.dart';

class FakeClient extends http.BaseClient {
  final Map<String, http.Response Function(http.BaseRequest)> handlers = {};
  final List<http.BaseRequest> requests = [];

  void on(
    String method,
    String path,
    http.Response Function(http.BaseRequest) handler,
  ) {
    handlers['$method:$path'] = handler;
  }

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    requests.add(request);
    final key = '${request.method}:${request.url.path}';
    final handler = handlers[key];
    final response =
        handler?.call(request) ?? http.Response('{"error":"not found"}', 404);
    return http.StreamedResponse(
      Stream.fromIterable([response.bodyBytes]),
      response.statusCode,
      headers: response.headers,
      reasonPhrase: response.reasonPhrase,
    );
  }
}

void main() {
  group('ApiClient URL handling', () {
    test('uses http for plain hosts', () async {
      final fake = FakeClient()
        ..on('GET', '/health', (_) => http.Response('{"ok":true}', 200));
      final client = ApiClient(host: 'localhost:8080', httpClient: fake);
      await client.healthCheck();
      expect(
        fake.requests.single.url.toString(),
        'http://localhost:8080/health',
      );
    });

    test('preserves explicit https scheme', () async {
      final fake = FakeClient()
        ..on('GET', '/health', (_) => http.Response('{"ok":true}', 200));
      final client = ApiClient(
        host: 'https://api.example.com',
        httpClient: fake,
      );
      await client.healthCheck();
      expect(
        fake.requests.single.url.toString(),
        'https://api.example.com/health',
      );
    });

    test('infers https for port 443', () async {
      final fake = FakeClient()
        ..on('GET', '/health', (_) => http.Response('{"ok":true}', 200));
      final client = ApiClient(host: 'api.example.com:443', httpClient: fake);
      await client.healthCheck();
      expect(
        fake.requests.single.url.toString(),
        'https://api.example.com/health',
      );
    });
  });

  group('ApiClient request contracts', () {
    test('listMemories sends user_id and limit query params', () async {
      final fake = FakeClient()
        ..on(
          'GET',
          '/memories',
          (_) => http.Response('{"memories":[{"id":"1"}]}', 200),
        );
      final client = ApiClient(userId: 'alice', httpClient: fake);
      final result = await client.listMemories(limit: 5);
      final uri = fake.requests.single.url;
      expect(uri.queryParameters['user_id'], 'alice');
      expect(uri.queryParameters['limit'], '5');
      expect(result, hasLength(1));
    });

    test('sendMessage posts backend MessageRequest JSON', () async {
      final fake = FakeClient()
        ..on(
          'POST',
          '/message',
          (request) => http.Response('{"response":"ok"}', 200),
        );
      final client = ApiClient(userId: 'alice', httpClient: fake);
      final result = await client.sendMessage('hello');
      expect(result['response'], 'ok');
      expect(
        fake.requests.single.headers['content-type'],
        contains('application/json'),
      );
    });

    test('returns empty list when expected list key is missing', () async {
      final fake = FakeClient()
        ..on('GET', '/skills', (_) => http.Response('{"other":[]}', 200));
      final client = ApiClient(httpClient: fake);
      expect(await client.listSkills(), isEmpty);
    });

    test('listSkills sends workspace_id when provided', () async {
      final fake = FakeClient()
        ..on(
          'GET',
          '/skills',
          (_) => http.Response('{"skills":[{"name":"triage"}]}', 200),
        );
      final client = ApiClient(userId: 'alice', httpClient: fake);

      final result = await client.listSkills(workspaceId: 'sales');

      final uri = fake.requests.single.url;
      expect(uri.queryParameters['user_id'], 'alice');
      expect(uri.queryParameters['workspace_id'], 'sales');
      expect(result.single['name'], 'triage');
    });

    test('getSkillDetail requests named skill with workspace_id', () async {
      final fake = FakeClient()
        ..on(
          'GET',
          '/skills/triage',
          (_) => http.Response('{"name":"triage","content":"body"}', 200),
        );
      final client = ApiClient(userId: 'alice', httpClient: fake);

      final result = await client.getSkillDetail(
        'triage',
        workspaceId: 'sales',
      );

      final uri = fake.requests.single.url;
      expect(uri.queryParameters['workspace_id'], 'sales');
      expect(result['content'], 'body');
    });

    test('createSkill posts body and workspace_id', () async {
      final fake = FakeClient()
        ..on('POST', '/skills', (request) => http.Response('{"ok":true}', 200));
      final client = ApiClient(userId: 'alice', httpClient: fake);

      await client.createSkill(
        'triage',
        'Sort email',
        'Use this process',
        scope: 'workspace',
        workspaceId: 'sales',
      );

      final request = fake.requests.single;
      final body =
          jsonDecode((request as http.Request).body) as Map<String, dynamic>;
      expect(request.url.queryParameters['workspace_id'], 'sales');
      expect(body['name'], 'triage');
      expect(body['description'], 'Sort email');
      expect(body['content'], 'Use this process');
      expect(body['scope'], 'workspace');
    });

    test('deleteSkill sends scope and workspace_id', () async {
      final fake = FakeClient()
        ..on(
          'DELETE',
          '/skills/triage',
          (_) => http.Response('{"ok":true}', 200),
        );
      final client = ApiClient(userId: 'alice', httpClient: fake);

      await client.deleteSkill(
        'triage',
        scope: 'workspace',
        workspaceId: 'sales',
      );

      final uri = fake.requests.single.url;
      expect(uri.queryParameters['workspace_id'], 'sales');
      expect(uri.queryParameters['scope'], 'workspace');
    });
  });

  group('ApiClient error handling', () {
    test('throws ApiException for non-2xx responses', () async {
      final fake = FakeClient()
        ..on('GET', '/health', (_) => http.Response('bad', 500));
      final client = ApiClient(httpClient: fake);
      await expectLater(client.healthCheck(), throwsA(isA<ApiException>()));
    });

    test(
      'throws ApiException when successful response is not an object',
      () async {
        final fake = FakeClient()
          ..on('GET', '/health', (_) => http.Response('[]', 200));
        final client = ApiClient(httpClient: fake);
        await expectLater(client.healthCheck(), throwsA(isA<ApiException>()));
      },
    );

    test('ApiException string contains status code and body', () {
      final ex = ApiException(500, 'Internal server error');
      expect(ex.toString(), contains('500'));
      expect(ex.toString(), contains('Internal server error'));
    });
  });
}
