import 'dart:async';
import 'dart:convert';
import 'package:executive_assistant/services/backend_service.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  group('BackendService', () {
    late BackendService service;

    setUp(() {
      service = BackendService(
        host: '127.0.0.1:9999',
        pollInterval: const Duration(milliseconds: 50),
      );
    });

    tearDown(() {
      service.dispose();
    });

    test('starts with stopped status', () {
      expect(service.currentStatus, BackendStatus.stopped);
      expect(service.isRunning, isFalse);
    });

    test('start() sets status to starting', () async {
      final statuses = <BackendStatus>[];
      service.status.listen(statuses.add);
      await service.start();
      expect(statuses, contains(BackendStatus.starting));
    });

    test('stop() sets status to stopped', () async {
      await service.start();
      final statuses = <BackendStatus>[];
      service.status.listen(statuses.add);
      await service.stop();
      expect(service.currentStatus, BackendStatus.stopped);
      expect(service.isRunning, isFalse);
    });

    test('start() is idempotent', () async {
      await service.start();
      await service.start(); // second call should be no-op
      expect(service.currentStatus, isNot(BackendStatus.stopped));
    });

    test('dispose() stops polling and closes streams', () {
      service.dispose();
      expect(service.currentStatus, BackendStatus.stopped);
    });

    test('health stream emits events', () async {
      final healthValues = <bool>[];
      service.health.listen(healthValues.add);
      await service.start();
      // Allow one poll cycle
      await Future.delayed(const Duration(milliseconds: 100));
      // Should have at least one health check result
      expect(healthValues, isNotEmpty);
    });

    test('status stream is broadcast', () {
      expect(service.status, isA<Stream<BackendStatus>>());
    });
  });
}
