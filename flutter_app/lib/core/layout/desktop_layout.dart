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
    icon: Icons.mail_outlined,
    activeIcon: Icons.mail,
    label: 'Email',
    path: '/email',
  ),
  workspace(
    icon: Icons.folder_outlined,
    activeIcon: Icons.folder,
    label: 'Workspace',
    path: '/workspace',
  ),
  settings(
    icon: Icons.settings_outlined,
    activeIcon: Icons.settings,
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
                  Container(width: 1, color: context.tokens.colors.borderSubtle),
                  SizedBox(width: chatPanelWidth, child: const _ChatPanel()),
                  Container(width: 1, color: context.tokens.colors.borderSubtle),
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
                                  Icons.add,
                                  size: 24,
                                  color: tokens.colors.textTertiary,
                                ),
                                const SizedBox(height: 4),
                                Text(
                                  'New workspace',
                                  style: tokens.typography.textTheme.labelSmall?.copyWith(
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
                            Icons.add,
                            size: 16,
                            color: tokens.colors.textTertiary,
                          ),
                          title: Text(
                            'New workspace',
                            style: tokens.typography.textTheme.labelSmall?.copyWith(
                              color: tokens.colors.textTertiary,
                            ),
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
                                style: tokens.typography.textTheme.bodyMedium?.copyWith(
                                  fontSize: 13,
                                  fontWeight: isActive
                                      ? FontWeight.w600
                                      : FontWeight.w400,
                                  color: isActive
                                      ? tokens.colors.textPrimary
                                      : tokens.colors.textSecondary,
                                ),
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
              error: (_, __) => const SizedBox.shrink(),
            ),
          ),
          const Divider(height: 1),
          _SidebarItem(
            item: DesktopSidebarItem.settings,
            selected: false,
            onTap: () => _showSettings(context),
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
}

class _SidebarItem extends StatelessWidget {
  final DesktopSidebarItem item;
  final bool selected;
  final VoidCallback onTap;
  const _SidebarItem({
    required this.item,
    required this.selected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final tokens = context.tokens;
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: tokens.radius.smAll,
        child: Container(
          height: 40,
          margin: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
          padding: const EdgeInsets.symmetric(horizontal: 12),
          decoration: selected
              ? BoxDecoration(
                  color: tokens.colors.bgElevated,
                  borderRadius: tokens.radius.smAll,
                  border: Border(
                    left: BorderSide(
                      color: tokens.colors.accent,
                      width: 2,
                    ),
                  ),
                )
              : null,
          child: Row(
            children: [
              Icon(
                selected ? item.activeIcon : item.icon,
                size: 20,
                color: selected ? tokens.colors.accent : tokens.colors.textSecondary,
              ),
              const SizedBox(width: 10),
              Text(
                item.label,
                style: tokens.typography.textTheme.bodyMedium?.copyWith(
                  fontSize: 13,
                  color: selected ? tokens.colors.accent : tokens.colors.textSecondary,
                  fontWeight: selected ? FontWeight.w600 : FontWeight.w400,
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
  String _activeWorkspace = 'personal';
  bool _restoringScroll = false;

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_onScroll);
    ref.read(agentProvider.notifier).connect();
  }

  void _onScroll() {
    if (_restoringScroll) return;
    if (!_scrollController.hasClients) return;
    final maxExtent = _scrollController.position.maxScrollExtent;
    if (maxExtent <= 0) return;
    final ws = ref.read(activeChatTabProvider);
    final offset = _scrollController.position.extentAfter <= 2
        ? double.infinity
        : _scrollController.offset;
    ref.read(workspaceScrollPositions.notifier).state = {
      ...ref.read(workspaceScrollPositions),
      ws: offset,
    };
    debugPrint(
      '[SCROLL-SAVE _ChatPanel] ws=$ws offset=${offset.toStringAsFixed(0)} max=$maxExtent',
    );
  }

  Future<void> _restoreScrollPosition(String workspaceId) async {
    _restoringScroll = true;
    final saved = ref.read(workspaceScrollPositions)[workspaceId];
    debugPrint(
      '[SCROLL-RESTORE _ChatPanel] ws=$workspaceId saved=$saved mounted=$mounted',
    );
    if (saved != null && mounted) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!mounted || !_scrollController.hasClients) {
          debugPrint(
            '[SCROLL-RESTORE _ChatPanel] FAIL: mounted=$mounted hasClients=${_scrollController.hasClients}',
          );
          _restoringScroll = false;
          return;
        }
        final max = _scrollController.position.maxScrollExtent;
        final target = saved.isInfinite ? max : saved.clamp(0, max).toDouble();
        debugPrint('[SCROLL-RESTORE _ChatPanel] jumping to $target max=$max');
        if (max > 0) {
          _scrollController.jumpTo(target);
        }
        WidgetsBinding.instance.addPostFrameCallback((_) {
          _restoringScroll = false;
        });
      });
    } else {
      debugPrint(
        '[SCROLL-RESTORE _ChatPanel] no saved position, scrolling to bottom',
      );
      _restoringScroll = false;
      _scrollToBottom();
    }
  }

  void _scrollToBottom() {
    if (!_scrollController.hasClients) return;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      if (_scrollController.hasClients) {
        _scrollController.jumpTo(_scrollController.position.maxScrollExtent);
      }
    });
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
        // Explicitly save the leaving workspace's scroll position RIGHT NOW,
        // before switchWorkspace's clearHistory corrupts the ListView and resets offset to 0.
        if (_scrollController.hasClients) {
          final positions = ref.read(workspaceScrollPositions);
          final existing = positions[prev];
          final offset =
              _scrollController.position.extentAfter <= 2 ||
                  existing?.isInfinite == true
              ? double.infinity
              : _scrollController.offset;
          ref.read(workspaceScrollPositions.notifier).state = {
            ...positions,
            prev: offset,
          };
          debugPrint('[SCROLL-SAVE-EXPLICIT] leaving=$prev offset=$offset');
        }
        _restoringScroll = true;
      }
      _activeWorkspace = next;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted && _activeWorkspace == next) {
          _restoreScrollPosition(next);
        }
      });
    });

    ref.listen<ChatState>(agentProvider, (prev, next) {
      if (next.messages.isNotEmpty &&
          prev?.messages.isEmpty == true &&
          next.status == ChatStatus.idle) {
        _restoreScrollPosition(_activeWorkspace);
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
                  return GestureDetector(
                    onTap: () {
                      if (!isActive) {
                        ref
                            .read(chatTabNotifierProvider.notifier)
                            .openWorkspace(e.key, e.value);
                      }
                    },
                    child: Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 10),
                          decoration: BoxDecoration(
                            border: Border(
                              bottom: BorderSide(
                                color: isActive
                                    ? tokens.colors.accent
                                    : Colors.transparent,
                                width: 2,
                              ),
                            ),
                          ),
                          child: Center(
                            child: Text(
                              e.value.isNotEmpty ? e.value : e.key,
                              style: tokens.typography.textTheme.bodySmall?.copyWith(
                                fontSize: 12,
                                fontWeight: isActive
                                    ? FontWeight.w600
                                    : FontWeight.w400,
                                color: isActive
                                    ? tokens.colors.textPrimary
                                    : tokens.colors.textTertiary,
                              ),
                            ),
                          ),
                        ),
                        if (tabs.length > 1)
                          Padding(
                            padding: const EdgeInsets.only(right: 8),
                            child: InkWell(
                              onTap: () => ref
                                  .read(chatTabNotifierProvider.notifier)
                                  .closeTab(e.key),
                              child: Icon(
                                Icons.close,
                                size: 10,
                                color: tokens.colors.textTertiary,
                              ),
                            ),
                          ),
                      ],
                    ),
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
    return ChatMessageList(
      messages: state.messages,
      isStreaming: state.status == ChatStatus.streaming,
      streamingText: state.streamingText,
      reasoningText: state.reasoningText,
      activeToolCalls: state.activeToolCalls,
      scrollController: scrollController,
      header: state.messages.isNotEmpty
          ? CompanionContextPill(
              activeWorkspaceId: ref.watch(activeChatTabProvider),
            )
          : null,
      emptyBuilder: (_) => Center(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.screenEdge),
          child: Text(
            'Ask anything...',
            style: context.tokens.typography.textTheme.bodyMedium?.copyWith(
              color: context.tokens.colors.textTertiary,
            ),
          ),
        ),
      ),
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.cardPadding,
        vertical: AppSpacing.itemGap,
      ),
    );
  }
}
