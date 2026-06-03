import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../theme/app_theme.dart';
import '../../features/companion/companion_toast.dart';

/// Two-column layout: fixed-width sidebar + full-width utility panel.
/// Used for routes that should occupy the full content width
/// (tools, skills, subagents, connectors, settings).
class DesktopUtilityLayout extends ConsumerWidget {
  final Widget sidebar;
  final Widget child;
  const DesktopUtilityLayout({
    super.key,
    required this.sidebar,
    required this.child,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    const dividerWidth = 1.0;
    return Scaffold(
      body: Stack(
        children: [
          Row(
            children: [
              sidebar,
              Container(
                width: dividerWidth,
                color: context.tokens.colors.borderSubtle,
              ),
              Expanded(child: child),
            ],
          ),
          const CompanionToastOverlay(),
        ],
      ),
    );
  }
}
