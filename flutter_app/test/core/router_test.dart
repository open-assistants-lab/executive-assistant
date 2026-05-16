import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

void main() {
  group('AppRouter', () {
    testWidgets('initial route is home', (WidgetTester tester) async {
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp.router(
            routerConfig: GoRouter(
              routes: [
                ShellRoute(
                  builder: (context, state, child) => child,
                  routes: [
                    GoRoute(
                      path: '/',
                      builder: (context, state) => const Text('Home'),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      );
      await tester.pump(); await tester.pump(const Duration(milliseconds: 100));
      expect(find.text('Home'), findsOneWidget);
    });

    testWidgets('can navigate to /chat', (WidgetTester tester) async {
      final router = GoRouter(
        initialLocation: '/',
        routes: [
          GoRoute(
            path: '/',
            builder: (context, state) => const Scaffold(
              body: Center(child: Text('Home')),
            ),
          ),
          GoRoute(
            path: '/chat',
            builder: (context, state) => const Scaffold(
              body: Center(child: Text('Chat')),
            ),
          ),
        ],
      );

      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp.router(
            routerConfig: router,
          ),
        ),
      );
      await tester.pump(); await tester.pump(const Duration(milliseconds: 100));
      expect(find.text('Home'), findsOneWidget);

      router.go('/chat');
      await tester.pump(); await tester.pump(const Duration(milliseconds: 100));
      expect(find.text('Chat'), findsOneWidget);
    });

    testWidgets('can navigate to /tasks', (WidgetTester tester) async {
      final router = GoRouter(
        initialLocation: '/',
        routes: [
          GoRoute(
            path: '/',
            builder: (context, state) => const Scaffold(
              body: Center(child: Text('Home')),
            ),
          ),
          GoRoute(
            path: '/tasks',
            builder: (context, state) => const Scaffold(
              body: Center(child: Text('Tasks')),
            ),
          ),
        ],
      );

      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp.router(
            routerConfig: router,
          ),
        ),
      );
      await tester.pump(); await tester.pump(const Duration(milliseconds: 100));

      router.go('/tasks');
      await tester.pump(); await tester.pump(const Duration(milliseconds: 100));
      expect(find.text('Tasks'), findsOneWidget);
    });

    testWidgets('can pop back to previous route', (WidgetTester tester) async {
      final router = GoRouter(
        initialLocation: '/',
        routes: [
          GoRoute(
            path: '/',
            builder: (context, state) => const Scaffold(
              body: Center(child: Text('Home')),
            ),
          ),
          GoRoute(
            path: '/chat',
            builder: (context, state) => const Scaffold(
              body: Center(child: Text('Chat')),
            ),
          ),
        ],
      );

      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp.router(
            routerConfig: router,
          ),
        ),
      );
      await tester.pump(); await tester.pump(const Duration(milliseconds: 100));

      router.push('/chat');
      await tester.pump(); await tester.pump(const Duration(milliseconds: 100));
      expect(find.text('Chat'), findsOneWidget);

      router.pop();
      await tester.pump(); await tester.pump(const Duration(milliseconds: 100));
      expect(find.text('Home'), findsOneWidget);
    });
  });
}
