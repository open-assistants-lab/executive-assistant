import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:executive_assistant/core/layout/responsive_shell.dart';
import 'package:executive_assistant/core/constants/breakpoints.dart';

Widget _buildTestApp(Widget Function(GoRouterState) builder) {
  final router = GoRouter(
    routes: [
      ShellRoute(
        builder: (context, state, child) => builder(state),
        routes: [
          GoRoute(
            path: '/',
            pageBuilder: (context, state) => NoTransitionPage(
              child: const Text('Content'),
            ),
          ),
        ],
      ),
    ],
  );
  return ProviderScope(
    child: MaterialApp.router(
      routerConfig: router,
    ),
  );
}

void main() {
  group('ResponsiveShell', () {
    testWidgets('renders mobile layout below tablet breakpoint',
        (WidgetTester tester) async {
      tester.view.physicalSize = const Size(600, 800);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);

      await tester.pumpWidget(
        _buildTestApp((state) => ResponsiveShell(state: state, child: const Text('Content'))),
      );
      await tester.pump(); await tester.pump(const Duration(milliseconds: 100));
      expect(find.text('Content'), findsOneWidget);
    });

    testWidgets('renders desktop layout at or above desktop breakpoint',
        (WidgetTester tester) async {
      tester.view.physicalSize = const Size(1440, 900);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);

      await tester.pumpWidget(
        _buildTestApp((state) => ResponsiveShell(state: state, child: const Text('Content'))),
      );
      await tester.pump(); await tester.pump(const Duration(milliseconds: 100));
      expect(find.text('Content'), findsOneWidget);
    });

    testWidgets('switches from mobile to desktop on size change',
        (WidgetTester tester) async {
      tester.view.physicalSize = const Size(600, 800);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);

      await tester.pumpWidget(
        _buildTestApp((state) => ResponsiveShell(state: state, child: const Text('Content'))),
      );
      await tester.pump(); await tester.pump(const Duration(milliseconds: 100));
      expect(find.text('Content'), findsOneWidget);

      tester.view.physicalSize = const Size(1440, 900);
      await tester.pump(); await tester.pump(const Duration(milliseconds: 100));
      expect(find.text('Content'), findsOneWidget);
    });

    testWidgets('exact breakpoint width of 1024 renders desktop',
        (WidgetTester tester) async {
      tester.view.physicalSize = const Size(Breakpoints.desktop, 768);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);

      await tester.pumpWidget(
        _buildTestApp((state) => ResponsiveShell(state: state, child: const Text('Content'))),
      );
      await tester.pump(); await tester.pump(const Duration(milliseconds: 100));
      expect(find.text('Content'), findsOneWidget);
    });
  });
}
