import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../theme/app_theme.dart';
import '../../providers/agent_provider.dart';
import '../../providers/workspace_provider.dart';
import 'widgets/chat_message_list.dart';
import 'widgets/chat_input.dart';
import 'widgets/error_bar.dart';
import 'widgets/connection_banner.dart';

class ChatScreen extends ConsumerStatefulWidget {
  const ChatScreen({super.key});

  @override
  ConsumerState<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends ConsumerState<ChatScreen> {
  final _scrollController = ScrollController();
  bool _restoringScroll = false;

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_onScroll);
    _connect();
  }

  void _onScroll() {
    if (_restoringScroll) return;
    if (!_scrollController.hasClients) return;
    if (_scrollController.position.maxScrollExtent <= 0) return;
    final ws = ref.read(currentWorkspaceIdProvider);
    final offset = _scrollController.position.extentAfter <= 2
        ? double.infinity
        : _scrollController.offset;
    ref.read(workspaceScrollPositions.notifier).state = {
      ...ref.read(workspaceScrollPositions),
      ws: offset,
    };
  }

  void _connect() {
    ref.read(agentProvider.notifier).connect();
  }

  Future<void> _restoreScrollPosition(String workspaceId) async {
    _restoringScroll = true;
    final saved = ref.read(workspaceScrollPositions)[workspaceId];
    if (saved != null && mounted) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!mounted || !_scrollController.hasClients) {
          _restoringScroll = false;
          return;
        }
        final max = _scrollController.position.maxScrollExtent;
        final target = saved.isInfinite ? max : saved.clamp(0, max).toDouble();
        if (max > 0) {
          _scrollController.jumpTo(target);
        }
        WidgetsBinding.instance.addPostFrameCallback((_) {
          _restoringScroll = false;
        });
      });
    } else {
      _restoringScroll = false;
      _scrollToBottom();
    }
  }

  void _scrollToBottom() {
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
    final wsId = ref.watch(currentWorkspaceIdProvider);

    ref.listen<ChatState>(agentProvider, (prev, next) {
      if (!mounted) return;
      if (next.messages.isNotEmpty &&
          prev?.messages.isEmpty == true &&
          next.status == ChatStatus.idle) {
        _restoreScrollPosition(wsId);
        return;
      }
      if (next.status == ChatStatus.streaming) {
        _scrollToBottom();
      }
    });

    ref.listen<String>(currentWorkspaceIdProvider, (prev, next) {
      if (prev == next) return;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) {
          _restoreScrollPosition(next);
        }
      });
    });

    final isConnected = state.connected;
    final statusIcon = isConnected
        ? Icons.cloud_done
        : state.status == ChatStatus.disconnected
        ? Icons.cloud_off
        : Icons.cloud_sync;
    final statusColor = isConnected
        ? AppColors.success
        : state.status == ChatStatus.disconnected
        ? AppColors.danger
        : AppColors.warning;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Executive Assistant'),
        actions: [
          IconButton(
            icon: Icon(statusIcon, color: statusColor, size: 20),
            tooltip: isConnected ? 'Connected' : 'Reconnect',
            onPressed: _connect,
          ),
        ],
      ),
      body: Column(
        children: [
          ConnectionBanner(
            connected: isConnected,
            isDisconnected: state.status == ChatStatus.disconnected,
            onReconnect: _connect,
          ),
          Expanded(
            child: _MessageList(
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

class _MessageList extends StatelessWidget {
  final ChatState state;
  final ScrollController scrollController;

  const _MessageList({required this.state, required this.scrollController});

  @override
  Widget build(BuildContext context) {
    return ChatMessageList(
      messages: state.messages,
      isStreaming: state.status == ChatStatus.streaming,
      streamingText: state.streamingText,
      reasoningText: state.reasoningText,
      activeToolCalls: state.activeToolCalls,
      scrollController: scrollController,
      isLoading: state.loadingHistory,
      emptyBuilder: (_) => Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.chat_bubble_outline, size: 48, color: AppColors.textDim),
            const SizedBox(height: 16),
            Text(
              'Send a message to start',
              style: AppTypography.body.copyWith(color: AppColors.textDim),
            ),
          ],
        ),
      ),
    );
  }
}
