import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../features/chat/chat_screen.dart';
import '../../features/email/email_list_screen.dart';
import '../../features/workspace/workspace_panel.dart';
import '../../features/tools/tools_panel.dart';
import '../../features/skills/skills_sidebar_panel.dart';
import '../../features/subagents/subagents_sidebar_panel.dart';
import '../layout/responsive_shell.dart';
import '../../theme/tokens/motion.dart';
import '../../theme/app_theme.dart';
import '../../services/instrumented_app.dart';

final _rootNavigatorKey = GlobalKey<NavigatorState>();
final _shellNavigatorKey = GlobalKey<NavigatorState>();

final appRouterProvider = Provider<GoRouter>((ref) {
  return GoRouter(
    navigatorKey: _rootNavigatorKey,
    observers: [EaRouteObserver()],
    initialLocation: '/workspace',
    routes: [
      // Redirect root to workspace
      GoRoute(
        path: '/',
        redirect: (_, __) => '/workspace',
      ),
      ShellRoute(
        navigatorKey: _shellNavigatorKey,
        builder: (context, state, child) {
          return ResponsiveShell(child: child);
        },
        routes: [
          GoRoute(
            path: '/workspace',
            name: 'files',
            pageBuilder: (context, state) => CustomTransitionPage(
              key: state.pageKey,
              child: const WorkspacePanel(),
              transitionsBuilder: (context, animation, secondaryAnimation, child) {
                return FadeTransition(opacity: animation, child: child);
              },
              transitionDuration: EaMotion.standard.fluid,
            ),
          ),
          GoRoute(
            path: '/tools',
            name: 'tools',
            pageBuilder: (context, state) => CustomTransitionPage(
              key: state.pageKey,
              child: const ToolsPanel(),
              transitionsBuilder: (context, animation, secondaryAnimation, child) {
                return FadeTransition(opacity: animation, child: child);
              },
              transitionDuration: EaMotion.standard.fluid,
            ),
          ),
          GoRoute(
            path: '/skills',
            name: 'skills',
            pageBuilder: (context, state) => CustomTransitionPage(
              key: state.pageKey,
              child: const SkillsSidebarPanel(),
              transitionsBuilder: (context, animation, secondaryAnimation, child) {
                return FadeTransition(opacity: animation, child: child);
              },
              transitionDuration: EaMotion.standard.fluid,
            ),
          ),
          GoRoute(
            path: '/subagents',
            name: 'subagents',
            pageBuilder: (context, state) => CustomTransitionPage(
              key: state.pageKey,
              child: const SubagentsSidebarPanel(),
              transitionsBuilder: (context, animation, secondaryAnimation, child) {
                return FadeTransition(opacity: animation, child: child);
              },
              transitionDuration: EaMotion.standard.fluid,
            ),
          ),
          GoRoute(
            path: '/email',
            name: 'email',
            pageBuilder: (context, state) => CustomTransitionPage(
              key: state.pageKey,
              child: const EmailListScreen(),
              transitionsBuilder: (context, animation, secondaryAnimation, child) {
                return FadeTransition(opacity: animation, child: child);
              },
              transitionDuration: EaMotion.standard.fluid,
            ),
          ),
          GoRoute(
            path: '/tasks',
            name: 'tasks',
            pageBuilder: (context, state) => CustomTransitionPage(
              key: state.pageKey,
              child: _PlaceholderScreen(title: 'Tasks', icon: Symbols.check_circle),
              transitionsBuilder: (context, animation, secondaryAnimation, child) {
                return FadeTransition(opacity: animation, child: child);
              },
              transitionDuration: EaMotion.standard.fluid,
            ),
          ),
          GoRoute(
            path: '/contacts',
            name: 'contacts',
            pageBuilder: (context, state) => CustomTransitionPage(
              key: state.pageKey,
              child: _PlaceholderScreen(title: 'Contacts', icon: Symbols.contacts),
              transitionsBuilder: (context, animation, secondaryAnimation, child) {
                return FadeTransition(opacity: animation, child: child);
              },
              transitionDuration: EaMotion.standard.fluid,
            ),
          ),
          GoRoute(
            path: '/more',
            name: 'more',
            pageBuilder: (context, state) => CustomTransitionPage(
              key: state.pageKey,
              child: _PlaceholderScreen(title: 'More', icon: Symbols.more_horiz),
              transitionsBuilder: (context, animation, secondaryAnimation, child) {
                return FadeTransition(opacity: animation, child: child);
              },
              transitionDuration: EaMotion.standard.fluid,
            ),
          ),
        ],
      ),
      GoRoute(
        path: '/chat',
        name: 'chat',
        builder: (context, state) => const ChatScreen(),
      ),
    ],
  );
});

class _PlaceholderScreen extends StatelessWidget {
  final String title;
  final IconData icon;
  const _PlaceholderScreen({required this.title, this.icon = Symbols.construction});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            icon,
            size: 48,
            color: context.tokens.colors.textTertiary,
          ),
          const SizedBox(height: 16),
          Text(
            '$title — Coming Soon',
            style: context.tokens.typography.textTheme.headlineMedium!.copyWith(
              color: context.tokens.colors.textTertiary,
            ),
          ),
        ],
      ),
    );
  }
}