import 'dart:convert';
import 'dart:developer' as developer;

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

/// Lightweight test instrumentation.
///
/// Tracks:
/// - All uncaught errors (framework + Dart zone + platform)
/// - User interactions (tap, drag, scroll, pointer, keyboard shortcut)
/// - Route/navigation changes
/// - App lifecycle events
///
/// Everything is written as structured JSONL to stdout / developer log.
/// Toggle off by setting [TestInstrumentation.enabled] = false.
class TestInstrumentation {
  static final TestInstrumentation _instance = TestInstrumentation._internal();
  factory TestInstrumentation() => _instance;
  TestInstrumentation._internal();

  bool enabled = true;
  bool _captureForTests = false;
  int _sequence = 0;
  final List<Map<String, dynamic>> _eventLog = [];

  /// Exposed for test assertions against captured events.
  List<Map<String, dynamic>> get eventLog => List.unmodifiable(_eventLog);
  int get eventCount => _eventLog.length;

  /// Call before a test run to enable event capture.
  void startCapture() {
    _captureForTests = true;
    _eventLog.clear();
  }

  /// Call after a test run to disable capture and inspect [eventLog].
  void stopCapture() {
    _captureForTests = false;
  }

  void _log(String category, Map<String, dynamic> data) {
    if (!enabled) return;
    final entry = {
      'seq': ++_sequence,
      'ts': DateTime.now().toIso8601String(),
      'category': category,
      ...data,
    };
    if (_captureForTests) {
      _eventLog.add(entry);
    }
    final line = jsonEncode(entry);
    if (kDebugMode) {
      // ignore: avoid_print
      print('[TEST] $line');
    }
    developer.log(line, name: 'ea_test');
  }

  // ── Error tracking ─────────────────────────────────────────

  void onFlutterError(FlutterErrorDetails details) {
    _log('error', {
      'type': 'flutter',
      'exception': details.exception.toString(),
      'library': details.library,
      'silent': details.silent,
      if (details.stack != null)
        'stack': details.stack.toString().split('\n').take(8).join('\n'),
    });
  }

  void onZoneError(Object error, StackTrace stack) {
    _log('error', {
      'type': 'zone',
      'exception': error.toString(),
      'stack': stack.toString().split('\n').take(8).join('\n'),
    });
  }

  void onPlatformError(Object error, StackTrace stack) {
    _log('error', {
      'type': 'platform',
      'exception': error.toString(),
      'stack': stack.toString().split('\n').take(8).join('\n'),
    });
  }

  // ── Interaction tracking ───────────────────────────────────

  void onPointerDown(PointerDownEvent event) {
    _log('interaction', {
      'type': 'pointer_down',
      'pos': {'x': event.position.dx.toStringAsFixed(1), 'y': event.position.dy.toStringAsFixed(1)},
      'kind': event.kind.toString().split('.').last,
      'buttons': event.buttons,
    });
  }

  void onPointerMove(PointerMoveEvent event) {
    // Throttle: only log every 20th move event to avoid spam.
    if (_sequence % 20 != 0) return;
    _log('interaction', {
      'type': 'pointer_move',
      'pos': {'x': event.position.dx.toStringAsFixed(1), 'y': event.position.dy.toStringAsFixed(1)},
      'delta': {'dx': event.delta.dx.toStringAsFixed(1), 'dy': event.delta.dy.toStringAsFixed(1)},
    });
  }

  void onPointerUp(PointerUpEvent event) {
    _log('interaction', {
      'type': 'pointer_up',
      'pos': {'x': event.position.dx.toStringAsFixed(1), 'y': event.position.dy.toStringAsFixed(1)},
    });
  }

  void onPointerCancel(PointerCancelEvent event) {
    _log('interaction', {
      'type': 'pointer_cancel',
      'pos': {'x': event.position.dx.toStringAsFixed(1), 'y': event.position.dy.toStringAsFixed(1)},
    });
  }

  void onTapDown(TapDownDetails details) {
    _log('interaction', {
      'type': 'tap_down',
      'pos': {'x': details.globalPosition.dx.toStringAsFixed(1), 'y': details.globalPosition.dy.toStringAsFixed(1)},
      'kind': details.kind?.toString().split('.').last ?? 'touch',
    });
  }

  void onTapUp(TapUpDetails details) {
    _log('interaction', {
      'type': 'tap_up',
      'pos': {'x': details.globalPosition.dx.toStringAsFixed(1), 'y': details.globalPosition.dy.toStringAsFixed(1)},
    });
  }

  void onLongPress() {
    _log('interaction', {'type': 'long_press'});
  }

  void onDragStart(String axis, DragStartDetails details) {
    _log('interaction', {
      'type': 'drag_start',
      'axis': axis,
      'pos': {'x': details.globalPosition.dx.toStringAsFixed(1), 'y': details.globalPosition.dy.toStringAsFixed(1)},
    });
  }

  void onDragUpdate(String axis, DragUpdateDetails details) {
    if (_sequence % 10 != 0) return;
    _log('interaction', {
      'type': 'drag_update',
      'axis': axis,
      'delta': {'dx': details.delta.dx.toStringAsFixed(1), 'dy': details.delta.dy.toStringAsFixed(1)},
      'primaryDelta': details.primaryDelta?.toStringAsFixed(1),
    });
  }

  void onDragEnd(String axis, DragEndDetails details) {
    _log('interaction', {
      'type': 'drag_end',
      'axis': axis,
      'velocity': {
        'px': details.primaryVelocity?.toStringAsFixed(1) ?? '0.0',
      },
    });
  }

  void onScaleStart(ScaleStartDetails details) {
    _log('interaction', {
      'type': 'scale_start',
      'pos': {'x': details.focalPoint.dx.toStringAsFixed(1), 'y': details.focalPoint.dy.toStringAsFixed(1)},
    });
  }

  void onScaleUpdate(ScaleUpdateDetails details) {
    if (_sequence % 10 != 0) return;
    _log('interaction', {
      'type': 'scale_update',
      'scale': details.scale.toStringAsFixed(3),
      'rotation': details.rotation.toStringAsFixed(3),
    });
  }

  void onScroll(ScrollNotification notification) {
    if (_sequence % 5 != 0) return;
    _log('interaction', {
      'type': 'scroll',
      'metrics': {
        'extentBefore': notification.metrics.extentBefore.toStringAsFixed(1),
        'extentAfter': notification.metrics.extentAfter.toStringAsFixed(1),
        'pixels': notification.metrics.pixels.toStringAsFixed(1),
        'maxScrollExtent': notification.metrics.maxScrollExtent.toStringAsFixed(1),
      },
    });
  }

  void onKeyEvent(KeyEvent event) {
    _log('interaction', {
      'type': 'key',
      'character': event.character,
      'logicalKey': event.logicalKey.keyLabel,
      'physicalKey': event.physicalKey.usbHidUsage.toString(),
    });
  }

  void onTextInput(String text, {String? fieldName}) {
    _log('interaction', {
      'type': 'text_input',
      // ignore: use_null_aware_elements
      if (fieldName != null) 'field': fieldName,
      'length': text.length,
    });
  }

  // ── Navigation / Lifecycle ─────────────────────────────────

  void onRouteChange(String? from, String to) {
    _log('navigation', {
      'type': 'route',
      'from': from,
      'to': to,
    });
  }

  void onLifecycle(AppLifecycleState state) {
    _log('lifecycle', {
      'type': 'state',
      'state': state.name,
    });
  }

  void onWidgetBuilt(String widgetName, {Map<String, dynamic>? props}) {
    _log('widget', {
      'type': 'built',
      'widget': widgetName,
      // ignore: use_null_aware_elements
      if (props != null) 'props': props,
    });
  }

  void custom(String name, Map<String, dynamic> data) {
    _log('custom', {'name': name, ...data});
  }
}

// ── Global helpers for convenience ─────────────────────────

void testLog(String name, [Map<String, dynamic>? data]) {
  TestInstrumentation().custom(name, data ?? const {});
}
