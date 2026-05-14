import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'test_instrumentation.dart';

/// Wraps the app with test instrumentation.
///
/// Captures:
/// - All uncaught Flutter errors (via [FlutterError.onError])
/// - All pointer events (tap, drag, scroll, pointer down/up/move)
/// - Keyboard events
/// - App lifecycle changes
///
/// Usage:
/// ```dart
/// void main() {
///   runApp(
///     InstrumentedApp(
///       child: ProviderScope(child: ExecutiveAssistantApp()),
///     ),
///   );
/// }
/// ```
///
/// To temporarily disable: `TestInstrumentation().enabled = false;`
class InstrumentedApp extends StatefulWidget {
  final Widget child;

  const InstrumentedApp({super.key, required this.child});

  @override
  State<InstrumentedApp> createState() => _InstrumentedAppState();
}

class _InstrumentedAppState extends State<InstrumentedApp>
    with WidgetsBindingObserver {
  final _inst = TestInstrumentation();
  final _keyboardFocusNode = FocusNode();
  void Function(FlutterErrorDetails)? _originalOnError;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _captureFlutterErrors();
  }

  void _captureFlutterErrors() {
    _originalOnError = FlutterError.onError;
    FlutterError.onError = (details) {
      _inst.onFlutterError(details);
      _originalOnError?.call(details);
    };
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    _inst.onLifecycle(state);
  }

  @override
  Widget build(BuildContext context) {
    return NotificationListener<ScrollNotification>(
      onNotification: (notification) {
        _inst.onScroll(notification);
        return false;
      },
      child: Listener(
        behavior: HitTestBehavior.translucent,
        onPointerDown: _inst.onPointerDown,
        onPointerMove: _inst.onPointerMove,
        onPointerUp: _inst.onPointerUp,
        onPointerCancel: _inst.onPointerCancel,
        child: KeyboardListener(
          focusNode: _keyboardFocusNode,
          autofocus: true,
          onKeyEvent: (event) {
            if (event is KeyDownEvent) {
              _inst.onKeyEvent(event);
            }
          },
          child: widget.child,
        ),
      ),
    );
  }

  @override
  void dispose() {
    FlutterError.onError = _originalOnError;
    _keyboardFocusNode.dispose();
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }
}

/// A [NavigatorObserver] you add to `MaterialApp.navigatorObservers`
/// to log every route push/pop/replace.
///
/// Usage:
/// ```dart
/// MaterialApp(
///   navigatorObservers: [EaRouteObserver()],
///   ...
/// )
/// ```
class EaRouteObserver extends NavigatorObserver {
  final _inst = TestInstrumentation();

  @override
  void didPush(Route<dynamic> route, Route<dynamic>? previousRoute) {
    final from = previousRoute?.settings.name ?? previousRoute?.toString();
    final to = route.settings.name ?? route.toString();
    _inst.onRouteChange(from, to);
  }

  @override
  void didPop(Route<dynamic> route, Route<dynamic>? previousRoute) {
    final from = route.settings.name ?? route.toString();
    final to = previousRoute?.settings.name ?? '/';
    _inst.onRouteChange(from, '/pop:$to');
  }

  @override
  void didReplace({Route<dynamic>? newRoute, Route<dynamic>? oldRoute}) {
    final from = oldRoute?.settings.name ?? oldRoute?.toString();
    final to = newRoute?.settings.name ?? newRoute?.toString();
    _inst.onRouteChange(from, '/replace:$to');
  }
}
