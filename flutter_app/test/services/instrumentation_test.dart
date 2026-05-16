import 'package:flutter/material.dart';
import 'package:flutter/gestures.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:executive_assistant/services/test_instrumentation.dart';

void main() {
  group('TestInstrumentation singleton and defaults', () {
    test('singleton returns same instance', () {
      final a = TestInstrumentation();
      final b = TestInstrumentation();
      expect(identical(a, b), isTrue);
    });

    test('defaults to enabled', () {
      final inst = TestInstrumentation();
      expect(inst.enabled, isTrue);
    });

    test('initial eventLog is empty', () {
      final inst = TestInstrumentation();
      inst.startCapture();
      expect(inst.eventLog, isEmpty);
      inst.stopCapture();
    });

    test('initial eventCount is zero', () {
      final inst = TestInstrumentation();
      inst.startCapture();
      expect(inst.eventCount, 0);
      inst.stopCapture();
    });
  });

  group('startCapture / stopCapture lifecycle', () {
    late TestInstrumentation inst;

    setUp(() {
      inst = TestInstrumentation();
      inst.startCapture();
    });

    tearDown(() {
      inst.stopCapture();
      inst.enabled = true;
    });

    test('eventLog remains empty when no events fired', () {
      expect(inst.eventLog, isEmpty);
      expect(inst.eventCount, 0);
    });

    test('startCapture clears previous events', () {
      inst.custom('first', {});
      expect(inst.eventCount, greaterThan(0));
      inst.startCapture();
      expect(inst.eventCount, 0);
    });

    test('stopCapture prevents further accumulation', () {
      inst.custom('before', {});
      expect(inst.eventCount, greaterThan(0));
      final countBefore = inst.eventCount;
      inst.stopCapture();
      inst.custom('after', {});
      // After stopCapture, internal _captureForTests is false,
      // so eventLog should not grow.
      expect(inst.eventCount, countBefore);
    });
  });

  group('eventLog population after interactions', () {
    late TestInstrumentation inst;

    setUp(() {
      inst = TestInstrumentation();
      inst.startCapture();
    });

    tearDown(() {
      inst.stopCapture();
    });

    test('custom events appear in eventLog', () {
      inst.custom('test_event', {'key': 'value'});
      expect(inst.eventCount, 1);
      expect(inst.eventLog.first['category'], 'custom');
      expect(inst.eventLog.first['name'], 'test_event');
      expect(inst.eventLog.first['key'], 'value');
    });

    test('multiple events accumulate', () {
      inst.custom('event_1', {});
      inst.custom('event_2', {});
      inst.custom('event_3', {});
      expect(inst.eventCount, 3);
      expect(inst.eventLog.last['name'], 'event_3');
    });

    test('onRouteChange logs navigation event', () {
      inst.onRouteChange('/home', '/chat');
      expect(inst.eventLog.any((e) => e['category'] == 'navigation'), isTrue);
      expect(inst.eventLog.any((e) => e['to'] == '/chat'), isTrue);
    });

    test('onWidgetBuilt logs widget event', () {
      inst.onWidgetBuilt('ChatScreen', props: {'hasMessages': true});
      expect(inst.eventLog.any((e) => e['category'] == 'widget'), isTrue);
      expect(inst.eventLog.any((e) => e['widget'] == 'ChatScreen'), isTrue);
    });

    test('onTapDown logs interaction event', () {
      inst.onTapDown(
        TapDownDetails(
          globalPosition: const Offset(100, 200),
          kind: PointerDeviceKind.touch,
        ),
      );
      expect(inst.eventLog.any((e) => e['category'] == 'interaction'), isTrue);
      expect(inst.eventLog.any((e) => e['type'] == 'tap_down'), isTrue);
    });

    test('eventLog is unmodifiable', () {
      inst.custom('immutable_test', {});
      final log = inst.eventLog;
      expect(() => log.add({}), throwsUnsupportedError);
    });

    test('events contain sequence and timestamp', () {
      inst.custom('seq_test', {});
      final event = inst.eventLog.first;
      expect(event.containsKey('seq'), isTrue);
      expect(event['seq'], isA<int>());
      expect(event.containsKey('ts'), isTrue);
      expect(event['ts'], isA<String>());
    });
  });

  group('error tracking', () {
    late TestInstrumentation inst;

    setUp(() {
      inst = TestInstrumentation();
      inst.startCapture();
    });

    tearDown(() {
      inst.stopCapture();
    });

    test('onFlutterError captures error details', () {
      final details = FlutterErrorDetails(
        exception: Exception('boom'),
        library: 'test',
        silent: true,
      );
      inst.onFlutterError(details);
      expect(inst.eventLog.any((e) => e['category'] == 'error'), isTrue);
      expect(inst.eventLog.any((e) => e['type'] == 'flutter'), isTrue);
      expect(
        inst.eventLog.any((e) => (e['exception'] as String).contains('boom')),
        isTrue,
      );
    });

    test('onZoneError captures zone error', () {
      inst.onZoneError('zone error', StackTrace.current);
      expect(inst.eventLog.any((e) => e['type'] == 'zone'), isTrue);
      expect(
        inst.eventLog.any((e) => (e['exception'] as String).contains('zone error')),
        isTrue,
      );
    });

    test('onPlatformError captures platform error', () {
      inst.onPlatformError('platform error', StackTrace.current);
      expect(inst.eventLog.any((e) => e['type'] == 'platform'), isTrue);
      expect(
        inst.eventLog.any((e) => (e['exception'] as String).contains('platform error')),
        isTrue,
      );
    });
  });

  group('disabled instrumentation', () {
    test('does not log when enabled is false', () {
      final inst = TestInstrumentation();
      inst.startCapture();
      inst.enabled = false;
      inst.custom('should_not_log', {});
      expect(inst.eventCount, 0);
      inst.stopCapture();
    });
  });
}
