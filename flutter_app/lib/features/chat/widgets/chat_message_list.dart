import 'package:flutter/material.dart';
import '../../../theme/app_theme.dart';
import '../../../models/message.dart';
import 'message_bubble.dart';
import 'streaming_bubble.dart';
import 'reasoning_bubble.dart';
import 'tool_call_card.dart';

class ChatMessageList extends StatelessWidget {
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
  });

  @override
  Widget build(BuildContext context) {
    final items = _buildItems(context);

    if (items.isEmpty && isLoading) {
      return const Center(child: CircularProgressIndicator(strokeWidth: 2));
    }

    if (items.isEmpty) {
      if (emptyBuilder != null) {
        return emptyBuilder!(context);
      }
      return const SizedBox.shrink();
    }

    return ListView(
      controller: scrollController,
      padding: padding ??
          const EdgeInsets.symmetric(
            horizontal: AppSpacing.screenEdge,
            vertical: AppSpacing.cardPadding,
          ),
      children: items,
    );
  }

  List<Widget> _buildItems(BuildContext context) {
    final items = <Widget>[];

    if (header != null) {
      items.add(header!);
    }

    for (final msg in messages) {
      items.add(MessageBubble(message: msg));
    }

    if (reasoningText.isNotEmpty) {
      items.add(ReasoningBubble(content: reasoningText));
    }

    if (isStreaming && streamingText.isNotEmpty) {
      items.add(StreamingBubble(text: streamingText));
    }

    for (final tc in activeToolCalls) {
      if (tc.resultPreview == null) {
        items.add(ToolCallCard(toolCall: tc));
      }
    }

    return items;
  }
}
