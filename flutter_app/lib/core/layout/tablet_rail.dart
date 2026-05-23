import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../theme/app_theme.dart';
import '../../providers/workspace_provider.dart';
import '../../features/companion/companion_pulse.dart';
import '../../features/settings/settings_screen.dart';
import '../../features/connectors/connectors_modal.dart';

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
                    icon: Symbols.add,
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
                      onLongPress: () => _confirmDeleteWorkspace(context, ref, id, name),
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
                  icon: Symbols.cable,
                  tooltip: 'Conectors',
                  isActive: false,
                  onTap: () => _showConnectors(context),
                  tokens: tokens,
                ),
                const SizedBox(height: 4),
                _RailIcon(
                  icon: Symbols.settings,
                  tooltip: 'Ajustes',
                  isActive: false,
                  onTap: () => _showSettings(context),
                  tokens: tokens,
                ),
                const SizedBox(height: 4),
                _RailIcon(
                  icon: tokens.isDark ? Symbols.light_mode : Symbols.dark_mode,
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
    final t = context.tokens;
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text('New Workspace', style: t.typography.textTheme.titleLarge?.copyWith(color: t.colors.textPrimary)),
        content: TextField(
          controller: nameCtrl,
          style: t.typography.textTheme.bodyLarge?.copyWith(color: t.colors.textPrimary),
          decoration: const InputDecoration(
            hintText: 'Workspace name',
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

  void _confirmDeleteWorkspace(BuildContext context, WidgetRef ref, String id, String name) {
    showDialog(
      context: context,
      builder: (ctx) {
        final t = ctx.tokens;
        return AlertDialog(
          title: Text('Delete workspace?', style: t.typography.textTheme.titleLarge?.copyWith(color: t.colors.textPrimary)),
          content: Text(
            'Delete "$name"? This will also delete all associated conversation messages.',
            style: t.typography.textTheme.bodyMedium?.copyWith(color: t.colors.textPrimary),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () {
                Navigator.pop(ctx);
                ref.read(workspaceNotifierProvider.notifier).deleteWorkspace(id);
              },
              child: const Text('Delete'),
            ),
          ],
        );
      },
    );
  }

  void _showSettings(BuildContext context) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (_) => SettingsScreen(
        onManageProviders: () {
          // ignore: use_build_context_synchronously
          Navigator.of(context).pop();
          Future.delayed(const Duration(milliseconds: 300), () {
            // ignore: use_build_context_synchronously
            _showConnectors(context);
          });
        },
      ),
    );
  }

  void _showConnectors(BuildContext context, {int tab = 0}) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (_) => ConnectorsModal(initialTab: tab),
    );
  }
}

class _RailIcon extends StatelessWidget {
  final IconData? icon;
  final String? letter;
  final String? tooltip;
  final bool isActive;
  final VoidCallback? onTap;
  final VoidCallback? onLongPress;
  final EaTokens tokens;

  const _RailIcon({
    this.icon,
    this.letter,
    this.tooltip,
    required this.isActive,
    required this.onTap,
    this.onLongPress,
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
        onLongPress: onLongPress,
        borderRadius: tokens.radius.mdAll,
        child: child,
      );
    }
    return child;
  }
}
