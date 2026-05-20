import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../theme/app_theme.dart';
import '../../providers/workspace_provider.dart';
import '../../features/companion/companion_pulse.dart';
import '../../features/settings/settings_screen.dart';

class TabletRailLayout extends ConsumerWidget {
  final Widget child;

  const TabletRailLayout({super.key, required this.child});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final tokens = context.tokens;

    return Scaffold(
      body: Row(
        children: [
          // 64px rail sidebar
          _TabletRail(tokens: tokens),
          // Divider
          Container(width: 1, color: tokens.colors.borderSubtle),
          // Content area
          Expanded(child: child),
        ],
      ),
    );
  }
}

class _TabletRail extends ConsumerWidget {
  final EaTokens tokens;
  const _TabletRail({required this.tokens});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final currentId = ref.watch(currentWorkspaceIdProvider);
    final workspaces = ref.watch(workspaceListProvider);

    return Container(
      width: 64,
      color: tokens.colors.bgCanvas,
      child: Column(
        children: [
          const SizedBox(height: 8),
          // Companion pulse (compact)
          const CompanionPulse(),
          const SizedBox(height: 8),
          const Divider(height: 1),
          const SizedBox(height: 8),
          // Workspace icons (scrollable)
          Expanded(
            child: workspaces.when(
              data: (list) => ListView(
                padding: EdgeInsets.zero,
                children: [
                  // Add workspace button
                  _RailIcon(
                    icon: Icons.add,
                    tooltip: 'New workspace',
                    isActive: false,
                    onTap: () => _showCreateDialog(context, ref),
                    tokens: tokens,
                  ),
                  const SizedBox(height: 4),
                  ...list.map((ws) {
                    final id = ws['id']?.toString() ?? '';
                    final name = ws['name']?.toString() ?? '';
                    final firstLetter = name.isNotEmpty ? name[0].toUpperCase() : '?';
                    final isActive = id == currentId;

                    return _RailIcon(
                      icon: null,
                      letter: firstLetter,
                      tooltip: name,
                      isActive: isActive,
                      onTap: () {
                        ref.read(currentWorkspaceIdProvider.notifier).state = id;
                      },
                      tokens: tokens,
                    );
                  }),
                ],
              ),
              loading: () => const SizedBox.shrink(),
              error: (_, __) => const SizedBox.shrink(),
            ),
          ),
          // Bottom actions
          const Divider(height: 1),
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 8),
            child: Column(
              children: [
                _RailIcon(
                  icon: Icons.settings_outlined,
                  tooltip: 'Settings',
                  isActive: false,
                  onTap: () => _showSettings(context),
                  tokens: tokens,
                ),
                const SizedBox(height: 4),
                _RailIcon(
                  icon: tokens.isDark ? Icons.light_mode_outlined : Icons.dark_mode_outlined,
                  tooltip: tokens.isDark ? 'Switch to light mode' : 'Switch to dark mode',
                  isActive: false,
                  onTap: () => ref.read(themeModeProvider.notifier).toggle(),
                  tokens: tokens,
                ),
              ],
            ),
          ),
          const SizedBox(height: 8),
        ],
      ),
    );
  }

  void _showCreateDialog(BuildContext context, WidgetRef ref) {
    final nameCtrl = TextEditingController();
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('New Workspace'),
        content: TextField(
          controller: nameCtrl,
          decoration: const InputDecoration(
            hintText: 'Workspace name',
            border: OutlineInputBorder(),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () {
              final name = nameCtrl.text.trim();
              if (name.isNotEmpty) {
                ref.read(workspaceNotifierProvider.notifier).createWorkspace(name, '', '');
                Navigator.pop(ctx);
              }
            },
            child: const Text('Create'),
          ),
        ],
      ),
    );
  }

  void _showSettings(BuildContext context) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (_) => const SettingsScreen(),
    );
  }
}

class _RailIcon extends StatelessWidget {
  final IconData? icon;
  final String? letter;
  final String? tooltip;
  final bool isActive;
  final VoidCallback? onTap;
  final EaTokens tokens;

  const _RailIcon({
    this.icon,
    this.letter,
    this.tooltip,
    required this.isActive,
    required this.onTap,
    required this.tokens,
  });

  @override
  Widget build(BuildContext context) {
    final bg = isActive ? tokens.colors.bgElevated : Colors.transparent;
    final fg = isActive ? tokens.colors.accent : tokens.colors.textTertiary;

    final child = Tooltip(
      message: tooltip ?? '',
      waitDuration: const Duration(milliseconds: 300),
      child: Container(
        width: 48,
        height: 48,
        margin: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
        decoration: BoxDecoration(
          color: bg,
          borderRadius: tokens.radius.mdAll,
          border: isActive
              ? Border(left: BorderSide(color: tokens.colors.accent, width: 2))
              : null,
        ),
        child: Center(
          child: icon != null
              ? Icon(icon, size: 22, color: fg)
              : Text(
                  letter ?? '?',
                  style: tokens.typography.textTheme.bodyMedium?.copyWith(
                    color: fg,
                    fontWeight: FontWeight.w600,
                  ),
                ),
        ),
      ),
    );

    if (onTap != null) {
      return InkWell(
        onTap: onTap,
        borderRadius: tokens.radius.mdAll,
        child: child,
      );
    }
    return child;
  }
}
