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
                                  Symbols.add,
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
                            Symbols.add,
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
                              trailing: PopupMenuButton<String>(
                                icon: Icon(Symbols.more_horiz,
                                  size: 16,
                                  color: tokens.colors.textTertiary,
                                ),
                                onSelected: (value) {
                                  if (value == 'delete') {
                                    _confirmDeleteWorkspace(context, ref, id, name);
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
              error: (_, __) => const SizedBox.shrink(),
            ),
          ),
          const Divider(height: 1),
          Padding(
            padding: EdgeInsets.symmetric(horizontal: tokens.spacing.md, vertical: tokens.spacing.xs),
            child: Row(
              children: [
                _SidebarItem(
                  item: DesktopSidebarItem.settings,
                  selected: false,
                  onTap: () => _showSettings(context),
                ),
                const Spacer(),
                IconButton(
                  icon: Icon(
                    tokens.isDark ? Symbols.light_mode : Symbols.dark_mode,
                    size: 18,
                    color: tokens.colors.textSecondary,
                  ),
                  onPressed: () => ref.read(themeModeProvider.notifier).toggle(),
                  tooltip: tokens.isDark ? 'Switch to light mode' : 'Switch to dark mode',
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
    if (_restoringScroll) {
      debugPrint('[SCROLL-BLOCKED] restoring=$_restoringScroll');
      return;
    }
    if (!_scrollController.hasClients) return;
    final maxExtent = _scrollController.position.maxScrollExtent;
    if (maxExtent <= 0) return;
    final ws = ref.read(activeChatTabProvider);
    final extentAfter = _scrollController.position.extentAfter;
    final offset = extentAfter == 0.0
        ? -1.0
        : _scrollController.offset;
    final currentState = ref.read(workspaceScrollPositions);
    if (currentState[ws] == offset) return;
    ref.read(workspaceScrollPositions.notifier).state = {
      ...currentState,
      ws: offset,
    };
    debugPrint(
      '[SCROLL-SAVE _ChatPanel] ws=$ws extentAfter=$extentAfter offset=$offset max=$maxExtent',
    );
  }

  Future<void> _restoreScrollPosition(String workspaceId) async {
    _restoringScroll = true;
    final saved = ref.read(workspaceScrollPositions)[workspaceId];
    debugPrint(
      '[SCROLL-RESTORE _ChatPanel] ws=$workspaceId saved=$saved mounted=$mounted hasClients=${_scrollController.hasClients}',
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
        final offset = _scrollController.offset;
        final target = saved == -1.0 ? max : saved.clamp(0, max).toDouble();
        debugPrint('[SCROLL-RESTORE _ChatPanel] jumping to $target max=$max currentOffset=$offset');
        if (max > 0) {
          _scrollController.jumpTo(target);
          // Position may have changed since saved was written (stale SharedPreferences value).
          // Write the actual position we landed at so _onScroll being blocked doesn't leave
          // a stale position that could be read on the next restore cycle.
          final newOffset = _scrollController.position.extentAfter == 0.0
              ? -1.0
              : _scrollController.offset;
          final ws = ref.read(activeChatTabProvider);
          ref.read(workspaceScrollPositions.notifier).state = {
            ...ref.read(workspaceScrollPositions),
            ws: newOffset,
          };
          debugPrint('[SCROLL-RESTORE _ChatPanel] post-jump save ws=$ws newOffset=$newOffset');
        } else {
          debugPrint('[SCROLL-RESTORE _ChatPanel] SKIP jump: max=$max');
        }
        WidgetsBinding.instance.addPostFrameCallback((_) {
          _restoringScroll = false;
          debugPrint('[SCROLL-RESTORE _ChatPanel] done restoring, saving enabled');
        });
      });
    } else {
      debugPrint(
        '[SCROLL-RESTORE _ChatPanel] no saved position, scrolling to bottom. restoring=$_restoringScroll',
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
      debugPrint('[TAB-SWITCH] prev=$prev next=$next hasClients=${_scrollController.hasClients} restoring=$_restoringScroll');
      if (prev != null && prev != next) {
        if (_scrollController.hasClients) {
          final extentAfter = _scrollController.position.extentAfter;
          final currentOffset = _scrollController.offset;
          final maxExt = _scrollController.position.maxScrollExtent;
          final positions = ref.read(workspaceScrollPositions);
          final existing = positions[prev];
          final atBottom = extentAfter == 0.0;
          final offset = atBottom || existing == -1.0
              ? -1.0
              : currentOffset;
          debugPrint('[SCROLL-SAVE-EXPLICIT] leaving=$prev extentAfter=$extentAfter offset=$currentOffset max=$maxExt existing=$existing atBottom=$atBottom saving=$offset');
          ref.read(workspaceScrollPositions.notifier).state = {
            ...positions,
            prev: offset,
          };
        } else {
          debugPrint('[SCROLL-SAVE-EXPLICIT] SKIP leaving=$prev no clients');
        }
        _restoringScroll = true;
      }
      _activeWorkspace = next;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        debugPrint('[TAB-RESTORE-FRAME] ws=$next hasClients=${_scrollController.hasClients} _activeWorkspace=$_activeWorkspace mounted=$mounted');
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
                                Symbols.close,
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
