import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../theme/app_theme.dart';
import '../../providers/agent_provider.dart';
import '../../providers/workspace_provider.dart';
import '../../providers/chat_tab_provider.dart';
import '../../widgets/app_input.dart';
import '../../features/chat/widgets/chat_message_list.dart';
import '../../features/chat/widgets/chat_input.dart';
import '../../features/chat/widgets/error_bar.dart';
import '../../features/chat/widgets/connection_banner.dart';
import '../../features/companion/companion_pulse.dart';
import '../../features/companion/companion_context_pill.dart';
import '../../features/companion/companion_toast.dart';
import '../../features/settings/settings_screen.dart';

enum DesktopSidebarItem {
  email(
    icon: Symbols.mail,
    activeIcon: Symbols.mail,
    label: 'Email',
    path: '/email',
  ),
  workspace(
    icon: Symbols.folder,
    activeIcon: Symbols.folder,
    label: 'Workspace',
    path: '/workspace',
  ),
  settings(
    icon: Symbols.settings,
    activeIcon: Symbols.settings,
    label: 'Settings',
    path: '/settings',
  );
  // companion(icon: ...), memory(icon: ...), skills(icon: ...), subagents(icon: ...) — hidden

  final IconData icon;
  final IconData activeIcon;
  final String label;
  final String path;

  const DesktopSidebarItem({
    required this.icon,
    required this.activeIcon,
    required this.label,
    required this.path,
  });
}

final desktopSidebarProvider = StateProvider<DesktopSidebarItem>(
  (ref) => DesktopSidebarItem.workspace,
);

class DesktopLayout extends ConsumerWidget {
  final Widget child;
  const DesktopLayout({super.key, required this.child});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    const sidebarWidth = 240.0;
    const dividerCount = 2;

    return Scaffold(
      body: Stack(
        children: [
          LayoutBuilder(
            builder: (context, constraints) {
              final totalWidth = constraints.maxWidth;
              final remainingWidth = totalWidth - sidebarWidth - dividerCount;
              final chatPanelWidth = remainingWidth * 0.6;
              final contentWidth = remainingWidth * 0.4;
              return Row(
                children: [
                  const _Sidebar(width: sidebarWidth),
                  Container(
                    width: 1,
                    color: context.tokens.colors.borderSubtle,
                  ),
                  SizedBox(width: chatPanelWidth, child: const _ChatPanel()),
                  Container(
                    width: 1,
                    color: context.tokens.colors.borderSubtle,
                  ),
                  SizedBox(width: contentWidth, child: child),
                ],
              );
            },
          ),
          const CompanionToastOverlay(),
        ],
      ),
    );
  }
}

class _Sidebar extends ConsumerWidget {
  final double width;
  const _Sidebar({required this.width});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final tokens = context.tokens;
    final currentId = ref.watch(currentWorkspaceIdProvider);
    final workspaces = ref.watch(workspaceListProvider);

    return Container(
      width: width,
      color: tokens.colors.bgCanvas,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const CompanionPulse(),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12),
            child: AppSearchField(hint: 'Search chats...'),
          ),
          const SizedBox(height: 10),
          const Divider(height: 1),
          Expanded(
            child: workspaces.when(
              data: (list) => list.isEmpty
                  ? Center(
                      child: Padding(
                        padding: const EdgeInsets.all(24),
                        child: InkWell(
                          onTap: () => _showCreateDialog(context, ref),
                          borderRadius: BorderRadius.circular(8),
                          child: Padding(
                            padding: const EdgeInsets.all(12),
                            child: Column(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Icon(
                                  Symbols.add,
                                  size: 24,
                                  color: tokens.colors.textTertiary,
                                ),
                                const SizedBox(height: 4),
                                Text(
                                  'New workspace',
                                  style: tokens.typography.textTheme.labelSmall
                                      ?.copyWith(
                                        color: tokens.colors.textTertiary,
                                      ),
                                ),
                              ],
                            ),
                          ),
                        ),
                      ),
                    )
                  : ListView(
                      padding: const EdgeInsets.only(top: 4),
                      children: [
                        ListTile(
                          dense: true,
                          leading: Icon(
                            Symbols.add,
                            size: 16,
                            color: tokens.colors.textTertiary,
                          ),
                          title: Text(
                            'New workspace',
                            style: tokens.typography.textTheme.labelSmall
                                ?.copyWith(color: tokens.colors.textTertiary),
                          ),
                          onTap: () => _showCreateDialog(context, ref),
                        ),
                        const Divider(height: 1),
                        ...list.map((ws) {
                          final id = ws['id']?.toString() ?? '';
                          final name = ws['name']?.toString() ?? '';
                          final isActive = currentId == id;
                          return Container(
                            decoration: isActive
                                ? BoxDecoration(
                                    border: Border(
                                      left: BorderSide(
                                        color: tokens.colors.accent,
                                        width: 2,
                                      ),
                                    ),
                                  )
                                : null,
                            child: ListTile(
                              dense: true,
                              contentPadding: const EdgeInsets.only(
                                left: 16,
                                right: 8,
                              ),
                              visualDensity: VisualDensity.compact,
                              title: Text(
                                name,
                                style: tokens.typography.textTheme.bodyMedium
                                    ?.copyWith(
                                      fontSize: 13,
                                      fontWeight: isActive
                                          ? FontWeight.w600
                                          : FontWeight.w400,
                                      color: isActive
                                          ? tokens.colors.textPrimary
                                          : tokens.colors.textSecondary,
                                    ),
                              ),
                              trailing: PopupMenuButton<String>(
                                icon: Icon(
                                  Symbols.more_horiz,
                                  size: 16,
                                  color: tokens.colors.textTertiary,
                                ),
                                onSelected: (value) {
                                  if (value == 'delete') {
                                    _confirmDeleteWorkspace(
                                      context,
                                      ref,
                                      id,
                                      name,
                                    );
                                  }
                                },
                                itemBuilder: (_) => [
                                  const PopupMenuItem(
                                    value: 'delete',
                                    child: Text('Delete'),
                                  ),
                                ],
                              ),
                              selected: isActive,
                              selectedTileColor: tokens.colors.bgElevated,
                              hoverColor: tokens.colors.bgElevated,
                              onTap: () => ref
                                  .read(chatTabNotifierProvider.notifier)
                                  .openWorkspace(id, name),
                            ),
                          );
                        }),
                      ],
                    ),
              loading: () => const SizedBox.shrink(),
              error: (error, stackTrace) => const SizedBox.shrink(),
            ),
          ),
          const Divider(height: 1),
          Padding(
            padding: EdgeInsets.symmetric(
              horizontal: tokens.spacing.md,
              vertical: tokens.spacing.xs,
            ),
            child: Row(
              children: [
                Expanded(
                  child: _SidebarItem(
                    item: DesktopSidebarItem.settings,
                    selected: false,
                    onTap: () => _showSettings(context),
                  ),
                ),
                IconButton(
                  icon: Icon(
                    tokens.isDark ? Symbols.light_mode : Symbols.dark_mode,
                    size: 18,
                    color: tokens.colors.textSecondary,
                  ),
                  onPressed: () =>
                      ref.read(themeModeProvider.notifier).toggle(),
                  tooltip: tokens.isDark
                      ? 'Switch to light mode'
                      : 'Switch to dark mode',
                ),
              ],
            ),
          ),
          SizedBox(height: tokens.spacing.sm),
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
        title: Text(
          'New Workspace',
          style: t.typography.textTheme.titleLarge?.copyWith(
            color: t.colors.textPrimary,
          ),
        ),
        content: TextField(
          controller: nameCtrl,
          style: t.typography.textTheme.bodyLarge?.copyWith(
            color: t.colors.textPrimary,
          ),
          decoration: const InputDecoration(hintText: 'Workspace name'),
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
                ref
                    .read(workspaceNotifierProvider.notifier)
                    .createWorkspace(name, '', '');
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

  void _confirmDeleteWorkspace(
    BuildContext context,
    WidgetRef ref,
    String id,
    String name,
  ) {
    showDialog(
      context: context,
      builder: (ctx) {
        final t = ctx.tokens;
        return AlertDialog(
          title: Text(
            'Delete workspace?',
            style: t.typography.textTheme.titleLarge?.copyWith(
              color: t.colors.textPrimary,
            ),
          ),
          content: Text(
            'Delete "$name"? This will also delete all associated conversation messages.',
            style: t.typography.textTheme.bodyMedium?.copyWith(
              color: t.colors.textPrimary,
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () {
                Navigator.pop(ctx);
                ref
                    .read(workspaceNotifierProvider.notifier)
                    .deleteWorkspace(id);
              },
              child: const Text('Delete'),
            ),
          ],
        );
      },
    );
  }
}

class _SidebarItem extends StatefulWidget {
  final DesktopSidebarItem item;
  final bool selected;
  final VoidCallback onTap;
  const _SidebarItem({
    required this.item,
    required this.selected,
    required this.onTap,
  });

  @override
  State<_SidebarItem> createState() => _SidebarItemState();
}

class _SidebarItemState extends State<_SidebarItem> {
  bool _hover = false;

  @override
  Widget build(BuildContext context) {
    final tokens = context.tokens;
    final showBg = widget.selected || _hover;
    final textColor = (widget.selected || _hover)
        ? tokens.colors.textPrimary
        : tokens.colors.textSecondary;
    return MouseRegion(
      cursor: SystemMouseCursors.click,
      onEnter: (_) => setState(() => _hover = true),
      onExit: (_) => setState(() => _hover = false),
      child: GestureDetector(
        onTap: widget.onTap,
        child: AnimatedContainer(
          duration: tokens.motion.fast,
          curve: tokens.motion.curveStandard,
          padding: EdgeInsets.symmetric(
            horizontal: tokens.spacing.md,
            vertical: tokens.spacing.sm + 2,
          ),
          decoration: BoxDecoration(
            color: showBg ? tokens.colors.bgSurface : Colors.transparent,
            borderRadius: tokens.radius.smAll,
            border: widget.selected
                ? Border(
                    left: BorderSide(
                      color: tokens.colors.accent,
                      width: 3,
                    ),
                  )
                : null,
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                widget.selected ? widget.item.activeIcon : widget.item.icon,
                size: 18,
                color: textColor,
              ),
              SizedBox(width: tokens.spacing.sm + 2),
              Flexible(
                child: Text(
                  widget.item.label,
                  style: tokens.typography.textTheme.bodyMedium?.copyWith(
                    color: textColor,
                  ),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ChatPanel extends ConsumerStatefulWidget {
  const _ChatPanel();
  @override
  ConsumerState<_ChatPanel> createState() => _ChatPanelState();
}

class _ChatPanelState extends ConsumerState<_ChatPanel> {
  final _scrollController = ScrollController();
  bool _pendingScrollToBottom = false;

  @override
  void initState() {
    super.initState();
    ref.read(agentProvider.notifier).connect();
  }

  void _scrollToBottom() {
    if (!_scrollController.hasClients) return;
    final max = _scrollController.position.maxScrollExtent;
    if (max > 0) {
      _scrollController.animateTo(
        max,
        duration: const Duration(milliseconds: 250),
        curve: Curves.easeOutCubic,
      );
    }
  }

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final tokens = context.tokens;
    final state = ref.watch(agentProvider);
    final tabs = ref.watch(chatTabNotifierProvider);
    final activeTab = ref.watch(activeChatTabProvider);

    ref.listen<String>(activeChatTabProvider, (prev, next) {
      if (prev != null && prev != next) {
        _pendingScrollToBottom = true;
        // Reset scroll to top BEFORE next frame paints, so new content
        // doesn't briefly render at the old workspace's scroll position.
        if (_scrollController.hasClients) {
          _scrollController.jumpTo(0);
        }
        _scrollToBottom();
      }
    });

    ref.listen<ChatState>(agentProvider, (prev, next) {
      if (_pendingScrollToBottom && next.messages.isNotEmpty) {
        _pendingScrollToBottom = false;
        _scrollToBottom();
        return;
      }
      if (next.messages.isNotEmpty &&
          prev?.messages.isEmpty == true &&
          next.status == ChatStatus.idle) {
        _scrollToBottom();
        return;
      }
      if (next.status == ChatStatus.streaming) {
        _scrollToBottom();
      }
    });

    return Container(
      color: tokens.colors.bgCanvas,
      child: Column(
        children: [
          SizedBox(
            height: 40,
            child: ListView(
              scrollDirection: Axis.horizontal,
              children: [
                const SizedBox(width: 8),
                ...tabs.entries.map((e) {
                  final isActive = e.key == activeTab;
                  return _ChatPanelTab(
                    workspaceId: e.key,
                    label: e.value.isNotEmpty ? e.value : e.key,
                    isActive: isActive,
                    canClose: tabs.length > 1,
                    onTap: () {
                      if (!isActive) {
                        ref
                            .read(chatTabNotifierProvider.notifier)
                            .openWorkspace(e.key, e.value);
                      }
                    },
                    onClose: () => ref
                        .read(chatTabNotifierProvider.notifier)
                        .closeTab(e.key),
                  );
                }),
                const SizedBox(width: 8),
              ],
            ),
          ),
          ConnectionBanner(
            connected: state.connected,
            isDisconnected: state.status == ChatStatus.disconnected,
            onReconnect: () => ref.read(agentProvider.notifier).connect(),
          ),
          Expanded(
            child: _PanelMessageList(
              state: state,
              scrollController: _scrollController,
            ),
          ),
          if (state.status == ChatStatus.error && state.error != null)
            ErrorBar(error: state.error!),
          const ChatInput(),
        ],
      ),
    );
  }
}

class _PanelMessageList extends ConsumerWidget {
  final ChatState state;
  final ScrollController scrollController;
  const _PanelMessageList({
    required this.state,
    required this.scrollController,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final tokens = context.tokens;
    final activeWs = ref.watch(activeChatTabProvider);
    return TweenAnimationBuilder<double>(
      key: ValueKey('chat_list_$activeWs'),
      duration: tokens.motion.base,
      curve: tokens.motion.curveStandard,
      tween: Tween(begin: 0.0, end: 1.0),
      builder: (_, t, child) => Opacity(opacity: t.clamp(0.0, 1.0), child: child),
      child: KeyedSubtree(
        key: ValueKey('chat_list_inner_$activeWs'),
        child: ChatMessageList(
          key: const ValueKey('desktop-chat-message-list'),
          messages: state.messages,
          isStreaming: state.status == ChatStatus.streaming,
          streamingText: state.streamingText,
          reasoningText: state.reasoningText,
          activeToolCalls: state.activeToolCalls,
          scrollController: scrollController,
          isLoading: state.loadingHistory,
          header: state.messages.isNotEmpty
              ? CompanionContextPill(
                  activeWorkspaceId: activeWs,
                )
              : null,
          emptyBuilder: (_) => Center(
            child: Padding(
              padding: const EdgeInsets.all(AppSpacing.screenEdge),
              child: Text(
                'Ask anything...',
                style: tokens.typography.textTheme.bodyMedium?.copyWith(
                  color: tokens.colors.textTertiary,
                ),
              ),
            ),
          ),
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.cardPadding,
            vertical: AppSpacing.itemGap,
          ),
        ),
      ),
    );
  }
}

class _ChatPanelTab extends StatefulWidget {
  final String workspaceId;
  final String label;
  final bool isActive;
  final bool canClose;
  final VoidCallback onTap;
  final VoidCallback onClose;
  const _ChatPanelTab({
    required this.workspaceId,
    required this.label,
    required this.isActive,
    required this.canClose,
    required this.onTap,
    required this.onClose,
  });

  @override
  State<_ChatPanelTab> createState() => _ChatPanelTabState();
}

class _ChatPanelTabState extends State<_ChatPanelTab> {
  bool _hover = false;

  @override
  Widget build(BuildContext context) {
    final tokens = context.tokens;
    final color = widget.isActive
        ? tokens.colors.textPrimary
        : _hover
            ? tokens.colors.textSecondary
            : tokens.colors.textTertiary;
    return MouseRegion(
      cursor: SystemMouseCursors.click,
      onEnter: (_) => setState(() => _hover = true),
      onExit: (_) => setState(() => _hover = false),
      child: GestureDetector(
        onTap: widget.onTap,
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            AnimatedContainer(
              duration: tokens.motion.base,
              curve: tokens.motion.curveStandard,
              padding: EdgeInsets.symmetric(
                horizontal: tokens.spacing.md,
                vertical: tokens.spacing.sm,
              ),
              decoration: BoxDecoration(
                border: Border(
                  bottom: BorderSide(
                    color: widget.isActive
                        ? tokens.colors.accent
                        : Colors.transparent,
                    width: 2,
                  ),
                ),
              ),
              child: Center(
                child: AnimatedDefaultTextStyle(
                  duration: tokens.motion.base,
                  curve: tokens.motion.curveStandard,
                  style: tokens.typography.textTheme.titleSmall?.copyWith(
                        fontWeight:
                            widget.isActive ? FontWeight.w600 : FontWeight.w400,
                        color: color,
                      ) ??
                      TextStyle(color: color),
                  child: Text(widget.label),
                ),
              ),
            ),
            if (widget.canClose)
              Padding(
                padding: EdgeInsets.only(right: tokens.spacing.sm),
                child: InkWell(
                  onTap: widget.onClose,
                  child: Icon(
                    Symbols.close,
                    size: 12,
                    color: color,
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
