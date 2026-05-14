import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../features/chat/chat_screen.dart';
import '../../features/email/email_list_screen.dart';
import '../../features/workspace/workspace_panel.dart';
import '../layout/responsive_shell.dart';
import '../motion/motion.dart';
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
            pageBuilder: (context, state) => const NoTransitionPage(
              child: WorkspacePanel(),
            ),
          ),
          GoRoute(
            path: '/email',
            name: 'email',
            pageBuilder: (context, state) => CustomTransitionPage(
              key: state.pageKey,
              child: const EmailListScreen(),
              transitionsBuilder: (context, animation, secondaryAnimation, child) {
                return EaMotion.sidewaysTransition(animation, child);
              },
              transitionDuration: EaMotion.intuitive,
            ),
          ),
          GoRoute(
            path: '/tasks',
            name: 'tasks',
            pageBuilder: (context, state) => NoTransitionPage(
              child: _PlaceholderScreen(title: 'Tasks', icon: Icons.check_circle_outline),
            ),
          ),
          GoRoute(
            path: '/contacts',
            name: 'contacts',
            pageBuilder: (context, state) => NoTransitionPage(
              child: _PlaceholderScreen(title: 'Contacts', icon: Icons.contacts_outlined),
            ),
          ),
          GoRoute(
            path: '/more',
            name: 'more',
            pageBuilder: (context, state) => NoTransitionPage(
              child: _PlaceholderScreen(title: 'More', icon: Icons.more_horiz),
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
  const _PlaceholderScreen({required this.title, this.icon = Icons.construction});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            icon,
            size: 48,
            color: AppColors.textDim,
          ),
          const SizedBox(height: 16),
          Text(
            '$title — Coming Soon',
            style: AppTypography.sectionTitle.copyWith(
              color: AppColors.textDim,
            ),
          ),
        ],
      ),
    );
  }
}