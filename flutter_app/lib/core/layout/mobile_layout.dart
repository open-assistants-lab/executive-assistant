import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../theme/app_theme.dart';

enum AppTab { home, email, tasks, more }

final appTabProvider = StateProvider<AppTab>((ref) => AppTab.home);

final _tabPaths = ['/', '/email', '/tasks', '/more'];

class MobileLayout extends ConsumerWidget {
  final Widget child;

  const MobileLayout({super.key, required this.child});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final tokens = context.tokens;
    final currentRoute = GoRouterState.of(context).uri.path;
    final matchIndex = _tabPaths.indexWhere((p) {
      if (p == '/') return currentRoute == '/';
      return currentRoute.startsWith(p);
    });
    if (matchIndex >= 0) {
      ref.read(appTabProvider.notifier).state = AppTab.values[matchIndex];
    }
    final selectedIndex = matchIndex >= 0
        ? matchIndex
        : ref.watch(appTabProvider).index;

    return Scaffold(
      body: child,
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: selectedIndex,
        backgroundColor: tokens.colors.bgSurface,
        selectedItemColor: tokens.colors.accent,
        unselectedItemColor: tokens.colors.textTertiary,
        onTap: (index) {
          ref.read(appTabProvider.notifier).state = AppTab.values[index];
          context.go(_tabPaths[index]);
        },
        items: const [
          BottomNavigationBarItem(
            icon: Icon(Symbols.chat),
            activeIcon: Icon(Symbols.chat),
            label: 'Home',
          ),
          BottomNavigationBarItem(
            icon: Icon(Symbols.mail),
            activeIcon: Icon(Symbols.mail),
            label: 'Email',
          ),
          BottomNavigationBarItem(
            icon: Icon(Symbols.check_circle),
            activeIcon: Icon(Symbols.check_circle),
            label: 'Tasks',
          ),
          BottomNavigationBarItem(
            icon: Icon(Symbols.more_horiz),
            activeIcon: Icon(Symbols.more_horiz),
            label: 'More',
          ),
        ],
      ),
    );
  }
}