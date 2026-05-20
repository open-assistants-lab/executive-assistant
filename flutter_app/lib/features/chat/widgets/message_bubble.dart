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

    final tokens = context.tokens;
    final isUser = message.role == 'user';
    final userBubbleColor = tokens.isDark ? const Color(0xFF3A3A3A) : const Color(0xFF2A2A2A);
    final userBubbleTextColor = const Color(0xFFFFFFFF);
    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: LayoutBuilder(
        builder: (context, constraints) {
          return Container(
            margin: EdgeInsets.symmetric(vertical: tokens.spacing.xs),
            padding: EdgeInsets.all(tokens.spacing.md),
            constraints: BoxConstraints(
              maxWidth: constraints.maxWidth * 0.85,
            ),
            decoration: BoxDecoration(
              color: isUser ? userBubbleColor : tokens.colors.bgSurface,
              borderRadius: BorderRadius.only(
                topLeft: Radius.circular(tokens.radius.xl),
                topRight: Radius.circular(tokens.radius.xl),
                bottomLeft: Radius.circular(
                    isUser ? tokens.radius.xl : tokens.radius.sm),
                bottomRight: Radius.circular(
                    isUser ? tokens.radius.sm : tokens.radius.xl),
              ),
            ),
            child: SelectableText(
              message.content,
              style: tokens.typography.textTheme.bodyLarge?.copyWith(
                color: isUser ? userBubbleTextColor : tokens.colors.textPrimary,
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
    final tokens = context.tokens;
    return Padding(
      padding: EdgeInsets.symmetric(vertical: tokens.spacing.xs),
      child: Align(
        alignment: Alignment.centerLeft,
        child: Container(
          padding: EdgeInsets.symmetric(horizontal: tokens.spacing.sm, vertical: tokens.spacing.xs),
          decoration: BoxDecoration(
            color: tokens.colors.bgField.withAlpha(100),
            borderRadius: BorderRadius.circular(tokens.radius.md / 2),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Symbols.build, size: 12, color: tokens.colors.textTertiary),
              SizedBox(width: tokens.spacing.xs),
              Text(
                toolName,
                style: tokens.typography.textTheme.labelSmall?.copyWith(
                  color: tokens.colors.textTertiary,
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
    final tokens = context.tokens;
    final hasResult = toolCall.resultPreview != null;
    return Container(
      margin: EdgeInsets.only(top: tokens.spacing.xs),
      padding: EdgeInsets.symmetric(horizontal: tokens.spacing.sm + 2, vertical: 6),
      decoration: BoxDecoration(
        color: tokens.colors.bgField,
        borderRadius: BorderRadius.circular(tokens.radius.md),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            hasResult ? Symbols.check_circle : Symbols.build,
            size: 14,
            color: tokens.colors.textPrimary,
          ),
          SizedBox(width: tokens.spacing.sm),
          Flexible(
            child: Text(
              toolCall.toolName,
              style: tokens.typography.textTheme.labelSmall?.copyWith(
                color: tokens.colors.textPrimary,
              ),
            ),
          ),
          if (hasResult) ...[
            SizedBox(width: tokens.spacing.sm),
            Flexible(
              child: Text(
                toolCall.resultPreview!,
                style: tokens.typography.textTheme.bodySmall?.copyWith(
                  color: tokens.colors.textSecondary,
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