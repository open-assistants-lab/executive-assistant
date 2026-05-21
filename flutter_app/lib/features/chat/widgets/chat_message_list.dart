import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import '../../../core/animations.dart';
import '../../../theme/app_theme.dart';
import '../../../models/message.dart';
import 'message_bubble.dart';
import 'streaming_bubble.dart';
import 'reasoning_bubble.dart';
import 'tool_call_card.dart';

const _kScrollBottom = '__bottom__';

class ChatMessageList extends StatefulWidget {
  final List<ChatMessage> messages;
  final bool isStreaming;
  final String streamingText;
  final String reasoningText;
  final List<ToolCallDisplay> activeToolCalls;
  final ScrollController scrollController;
  final Widget? header;
  final bool isLoading;
  final WidgetBuilder? emptyBuilder;
  final EdgeInsetsGeometry? padding;
  final Map<String, GlobalKey>? messageKeys;

  const ChatMessageList({
    super.key,
    required this.messages,
    this.isStreaming = false,
    this.streamingText = '',
    this.reasoningText = '',
    this.activeToolCalls = const [],
    required this.scrollController,
    this.header,
    this.isLoading = false,
    this.emptyBuilder,
    this.padding,
    this.messageKeys,
  });

  @override
  State<ChatMessageList> createState() => ChatMessageListState();

  static String get bottomSentinel => _kScrollBottom;
}

class ChatMessageListState extends State<ChatMessageList> {
  @override
  void initState() {
    super.initState();
    _ensureKeys();
  }

  @override
  void didUpdateWidget(covariant ChatMessageList oldWidget) {
    super.didUpdateWidget(oldWidget);
    _ensureKeys();
  }

  void _ensureKeys() {
    if (widget.messageKeys == null) return;
    for (final msg in widget.messages) {
      widget.messageKeys!.putIfAbsent(msg.id, () => GlobalKey());
    }
  }

  String? getVisibleAnchorMessage() {
    if (!widget.scrollController.hasClients) return null;
    if (widget.messageKeys == null) return null;

    final position = widget.scrollController.position;
    if (position.extentAfter == 0.0) return _kScrollBottom;

    final viewportTop = position.pixels;
    final viewportBottom = position.pixels + position.viewportDimension;

    String? lastVisible;
    for (final msg in widget.messages) {
      final key = widget.messageKeys![msg.id];
      if (key == null) continue;
      final ctx = key.currentContext;
      if (ctx == null) continue;
      final box = ctx.findRenderObject() as RenderBox?;
      if (box == null || !box.hasSize) continue;
      final vp = RenderAbstractViewport.of(box);
      final revealed = vp.getOffsetToReveal(box, 0.0).offset;
      final msgTop = revealed;
      final msgBottom = msgTop + box.size.height;
      if (msgBottom > viewportTop && msgTop < viewportBottom) {
        lastVisible = msg.id;
      }
    }
    return lastVisible;
  }

  Future<void> scrollToMessage(String messageId) async {
    if (messageId == _kScrollBottom) {
      if (widget.scrollController.hasClients) {
        widget.scrollController.jumpTo(
          widget.scrollController.position.maxScrollExtent,
        );
      }
      return;
    }
    final key = widget.messageKeys?[messageId];
    if (key?.currentContext == null) return;
    await Scrollable.ensureVisible(
      key!.currentContext!,
      alignment: 1.0,
      duration: const Duration(milliseconds: 50),
    );
  }

  @override
  Widget build(BuildContext context) {
    final items = _buildItems(context);

    if (items.isEmpty && widget.isLoading) {
      return const Center(child: CircularProgressIndicator(strokeWidth: 2));
    }

    if (items.isEmpty) {
      if (widget.emptyBuilder != null) {
        return widget.emptyBuilder!(context);
      }
      return const SizedBox.shrink();
    }

    return ListView(
      controller: widget.scrollController,
      padding: widget.padding ??
          const EdgeInsets.symmetric(
            horizontal: AppSpacing.screenEdge,
            vertical: AppSpacing.cardPadding,
          ),
      children: items,
    );
  }

  List<Widget> _buildItems(BuildContext context) {
    final items = <Widget>[];

    if (widget.header != null) {
      items.add(widget.header!);
    }

    for (var i = 0; i < widget.messages.length; i++) {
      final msg = widget.messages[i];
      final gKey = widget.messageKeys?[msg.id];
      items.add(
        KeyedSubtree(
          key: ValueKey('msg_${msg.id}_${msg.content.hashCode}'),
          child: EaAnimations.staggeredEntry(
            index: i,
            child: _keyedWrapper(
              gKey,
              MessageBubble(message: msg),
            ),
          ),
        ),
      );
    }

    if (widget.reasoningText.isNotEmpty) {
      items.add(ReasoningBubble(content: widget.reasoningText));
    }

    if (widget.isStreaming && widget.streamingText.isNotEmpty) {
      items.add(StreamingBubble(text: widget.streamingText));
    }

    for (final tc in widget.activeToolCalls) {
      if (tc.resultPreview == null) {
        items.add(ToolCallCard(toolCall: tc));
      }
    }

    return items;
  }

  Widget _keyedWrapper(GlobalKey? key, Widget child) {
    return key != null ? KeyedSubtree(key: key, child: child) : child;
  }
}
