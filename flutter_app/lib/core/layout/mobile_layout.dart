import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

enum AppTab { home, email, tasks, more }

final appTabProvider = StateProvider<AppTab>((ref) => AppTab.home);

final _tabPaths = ['/', '/email', '/tasks', '/more'];

class MobileLayout extends ConsumerWidget {
  final Widget child;

  const MobileLayout({super.key, required this.child});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final currentRoute = GoRouterState.of(context).uri.path;
    final matchIndex = _tabPaths.indexWhere((p) {
      if (p == '/') return currentRoute == '/';
      return currentRoute.startsWith(p);
    });
    // Only update selected tab when the route actually matches a known tab
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
        onTap: (index) {
          ref.read(appTabProvider.notifier).state = AppTab.values[index];
          context.go(_tabPaths[index]);
        },
        items: const [
          BottomNavigationBarItem(
            icon: Icon(Icons.chat_outlined),
            activeIcon: Icon(Icons.chat),
            label: 'Home',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.mail_outlined),
            activeIcon: Icon(Icons.mail),
            label: 'Email',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.check_circle_outline),
            activeIcon: Icon(Icons.check_circle),
            label: 'Tasks',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.more_horiz),
            activeIcon: Icon(Icons.more_horiz),
            label: 'More',
          ),
        ],
      ),
    );
  }
}