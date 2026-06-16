import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../theme/app_theme.dart';
import '../../providers/agent_provider.dart';
import '../../core/constants/breakpoints.dart';
import '../chat/widgets/message_bubble.dart';
import '../chat/widgets/streaming_bubble.dart';
import '../chat/widgets/tool_call_card.dart';
import '../chat/widgets/chat_input.dart';
import '../chat/widgets/error_bar.dart';
import '../chat/widgets/connection_banner.dart';
import 'widgets/smart_greeting.dart';
import 'widgets/status_cards.dart';
import 'widgets/quick_actions.dart';

class HomeScreen extends ConsumerStatefulWidget {
  const HomeScreen({super.key});

  @override
  ConsumerState<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends ConsumerState<HomeScreen> {
  final _scrollController = ScrollController();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      ref.read(agentProvider.notifier).connect();
    });
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
    final state = ref.watch(agentProvider);
    final screenWidth = MediaQuery.of(context).size.width;
    final isDesktop = screenWidth >= Breakpoints.desktop;

    ref.listen<ChatState>(agentProvider, (prev, next) {
      if (next.messages.length != prev?.messages.length ||
          next.streamingText != prev?.streamingText) {
        if (!isDesktop) _scrollToBottom();
      }
    });

    if (isDesktop) {
      return _DesktopHome(state: state);
    }
    return _buildMobileHome(state);
  }

  Widget _buildMobileHome(ChatState state) {
    final hasMessages = state.messages.isNotEmpty ||
        state.streamingText.isNotEmpty;

    return Scaffold(
      body: Column(
        children: [
          ConnectionBanner(
            connected: state.connected,
            isDisconnected: state.status == ChatStatus.disconnected,
            onReconnect: () =>
                ref.read(agentProvider.notifier).connect(),
            backendStatus: state.backendStatus,
          ),
          Expanded(
            child: CustomScrollView(
              controller: _scrollController,
              slivers: [
                SliverToBoxAdapter(
                  child: Column(
                    children: [
                      const SmartGreeting(),
                      const StatusCards(
                        unreadEmails: 3,
                        dueTasks: 2,
                        activeSubagents: 1,
                      ),
                      SizedBox(height: context.tokens.spacing.lg),
                      QuickActions(
                        onDraftReply: () => ref
                            .read(agentProvider.notifier)
                            .sendMessage('Draft a reply to my latest email'),
                        onSummarize: () => ref
                            .read(agentProvider.notifier)
                            .sendMessage('Summarize my recent emails'),
                        onSchedule: () => ref
                            .read(agentProvider.notifier)
                            .sendMessage('What\'s on my schedule today?'),
                      ),
                      SizedBox(height: context.tokens.spacing.xxxl),
                    ],
                  ),
                ),
                if (hasMessages) ...[
                  SliverToBoxAdapter(
                    child: Padding(
                      padding: EdgeInsets.symmetric(
                        horizontal: context.tokens.spacing.xl,
                      ),
                      child: Text(
                        'Conversation',
                        style: context.tokens.typography.textTheme.headlineMedium!.copyWith(fontSize: 16, color: context.tokens.colors.textPrimary),
                      ),
                    ),
                  ),
                  SliverToBoxAdapter(
                    child: SizedBox(height: context.tokens.spacing.sm),
                  ),
                  _buildMessageSliver(state),
                ] else
                  const SliverFillRemaining(
                    hasScrollBody: false,
                    child: _EmptyState(),
                  ),
              ],
            ),
          ),
          if (state.status == ChatStatus.error && state.error != null)
            ErrorBar(error: state.error!),
          const ChatInput(),
        ],
      ),
    );
  }

  Widget _buildMessageSliver(ChatState state) {
    final items = <Widget>[];

    for (final msg in state.messages) {
      items.add(MessageBubble(message: msg));
    }
    if (state.status == ChatStatus.streaming &&
        state.streamingText.isNotEmpty) {
      items.add(StreamingBubble(text: state.streamingText));
    }
    for (final tc in state.activeToolCalls) {
      if (tc.resultPreview == null) {
        items.add(ToolCallCard(toolCall: tc));
      }
    }

    return SliverPadding(
      padding: EdgeInsets.symmetric(
        horizontal: context.tokens.spacing.xl,
      ),
      sliver: SliverList(delegate: SliverChildListDelegate(items)),
    );
  }
}

class _DesktopHome extends StatelessWidget {
  final ChatState state;

  const _DesktopHome({required this.state});

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: EdgeInsets.all(context.tokens.spacing.xl),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SmartGreeting(),
          SizedBox(height: context.tokens.spacing.lg),
          const StatusCards(
            unreadEmails: 3,
            dueTasks: 2,
            activeSubagents: 1,
          ),
          SizedBox(height: context.tokens.spacing.lg),
          const QuickActions(),
          SizedBox(height: context.tokens.spacing.xxxl),
          Text(
            'Recent Activity',
            style: context.tokens.typography.textTheme.headlineMedium!.copyWith(fontSize: 16, color: context.tokens.colors.textPrimary),
          ),
          SizedBox(height: context.tokens.spacing.lg),
          if (state.messages.isEmpty)
            Center(
              child: Padding(
                padding: const EdgeInsets.all(48),
                child: Column(
                  children: [
                    Icon(Symbols.chat_bubble,
                        size: 48, color: context.tokens.colors.textTertiary),
                    const SizedBox(height: 16),
                    Text(
                      'Use the chat panel to get started',
                      style:
                          context.tokens.typography.textTheme.bodyLarge!.copyWith(color: context.tokens.colors.textTertiary),
                    ),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(48),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Symbols.auto_awesome, size: 48, color: context.tokens.colors.textTertiary),
            const SizedBox(height: 16),
            Text(
              'How can I help you today?',
              style: context.tokens.typography.textTheme.headlineMedium!.copyWith(
                color: context.tokens.colors.textTertiary,
                fontSize: 18,
              ),
            ),
          ],
        ),
      ),
    );
  }
}