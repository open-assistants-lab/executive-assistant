import 'package:flutter/material.dart';
import '../../../theme/app_theme.dart';
import '../../../models/message.dart';
import 'reasoning_bubble.dart';

class MessageBubble extends StatelessWidget {
  final ChatMessage message;

  const MessageBubble({super.key, required this.message});

  @override
  Widget build(BuildContext context) {
    final content = message.content.trim();
    if (content.isEmpty) return const SizedBox.shrink();
    if (message.role == 'tool') {
      return _InlineToolBadge(toolName: content);
    }
    if (message.role == 'reasoning') {
      return ReasoningBubble(content: content);
    }

    final isUser = message.role == 'user';
    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: LayoutBuilder(
        builder: (context, constraints) {
          return Container(
            margin: const EdgeInsets.symmetric(vertical: 4),
            padding: const EdgeInsets.all(12),
            constraints: BoxConstraints(
              maxWidth: constraints.maxWidth * 0.85,
            ),
            decoration: BoxDecoration(
              color: isUser ? AppColors.userBubble : AppColors.assistantBubble,
              borderRadius: BorderRadius.only(
                topLeft: const Radius.circular(AppRadius.messageBubbleTop),
                topRight: const Radius.circular(AppRadius.messageBubbleTop),
                bottomLeft: Radius.circular(
                    isUser ? AppRadius.messageBubbleTop : AppRadius.messageBubbleBottom),
                bottomRight: Radius.circular(
                    isUser ? AppRadius.messageBubbleBottom : AppRadius.messageBubbleTop),
              ),
            ),
            child: SelectableText(
              message.content,
              style: AppTypography.body.copyWith(
                color: isUser ? AppColors.userBubbleText : AppColors.assistantBubbleText,
              ),
            ),
          );
        },
      ),
    );
  }
}

class _InlineToolBadge extends StatelessWidget {
  final String toolName;
  const _InlineToolBadge({required this.toolName});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Align(
        alignment: Alignment.centerLeft,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          decoration: BoxDecoration(
            color: AppColors.toolChipBg.withAlpha(100),
            borderRadius: BorderRadius.circular(AppRadius.chip / 2),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.build_outlined, size: 12, color: AppColors.textDim),
              const SizedBox(width: 5),
              Text(
                toolName,
                style: AppTypography.toolLabel.copyWith(
                  color: AppColors.textDim,
                  fontSize: 11,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class ToolCallChip extends StatelessWidget {
  final ToolCallDisplay toolCall;

  const ToolCallChip({super.key, required this.toolCall});

  @override
  Widget build(BuildContext context) {
    final hasResult = toolCall.resultPreview != null;
    return Container(
      margin: const EdgeInsets.only(top: 4),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: AppColors.toolChipBg,
        borderRadius: BorderRadius.circular(AppRadius.chip),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            hasResult ? Icons.check_circle : Icons.build,
            size: 14,
            color: AppColors.toolChipText,
          ),
          const SizedBox(width: 6),
          Flexible(
            child: Text(
              toolCall.toolName,
              style: AppTypography.toolLabel.copyWith(
                color: AppColors.toolChipText,
              ),
            ),
          ),
          if (hasResult) ...[
            const SizedBox(width: 6),
            Flexible(
              child: Text(
                toolCall.resultPreview!,
                style: AppTypography.caption.copyWith(
                  color: AppColors.textSecondary,
                ),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ],
      ),
    );
  }
}