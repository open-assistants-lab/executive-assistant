import 'package:executive_assistant/core/layout/desktop_layout.dart';
import 'package:executive_assistant/core/layout/desktop_utility_layout.dart';
import 'package:executive_assistant/core/layout/responsive_shell.dart';
import 'package:executive_assistant/theme/app_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';

Widget _buildTestApp(String location, Widget child) {
  final router = GoRouter(
    initialLocation: location,
    routes: [
      ShellRoute(
        builder: (context, state, child) =>
            ResponsiveShell(state: state, child: child),
        routes: [
          GoRoute(
            path: '/',
            pageBuilder: (context, state) =>
                NoTransitionPage(child: child),
          ),
          GoRoute(
            path: '/workspace',
            pageBuilder: (context, state) =>
                NoTransitionPage(child: child),
          ),
          GoRoute(
            path: '/email',
            pageBuilder: (context, state) =>
                NoTransitionPage(child: child),
          ),
          GoRoute(
            path: '/tools',
            pageBuilder: (context, state) =>
                NoTransitionPage(child: child),
          ),
          GoRoute(
            path: '/skills',
            pageBuilder: (context, state) =>
                NoTransitionPage(child: child),
          ),
          GoRoute(
            path: '/subagents',
            pageBuilder: (context, state) =>
                NoTransitionPage(child: child),
          ),
          GoRoute(
            path: '/connectors',
            pageBuilder: (context, state) =>
                NoTransitionPage(child: child),
          ),
          GoRoute(
            path: '/settings',
            pageBuilder: (context, state) =>
                NoTransitionPage(child: child),
          ),
        ],
      ),
    ],
  );
  return ProviderScope(
    child: MaterialApp.router(
      theme: AppTheme.light,
      routerConfig: router,
    ),
  );
}

void main() {
  group('ResponsiveShell route layout selection', () {
    testWidgets('utility routes render DesktopUtilityLayout', (tester) async {
      tester.view.physicalSize = const Size(1440, 900);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);

      for (final path in const [
        '/tools', '/skills', '/subagents', '/connectors', '/settings',
      ]) {
        await tester.pumpWidget(_buildTestApp(path, const SizedBox()));
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 100));

        expect(
          find.byType(DesktopUtilityLayout),
          findsOneWidget,
          reason: 'Expected DesktopUtilityLayout for $path',
        );
      }
    });

    testWidgets('non-utility routes render DesktopLayout', (tester) async {
      tester.view.physicalSize = const Size(1440, 900);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);

      for (final path in const ['/workspace', '/email']) {
        await tester.pumpWidget(_buildTestApp(path, const SizedBox()));
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 100));

        expect(
          find.byType(DesktopLayout),
          findsOneWidget,
          reason: 'Expected DesktopLayout for $path',
        );
      }
    });
  });
}
