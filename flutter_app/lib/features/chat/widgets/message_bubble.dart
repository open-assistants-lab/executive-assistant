import 'package:flutter/material.dart';
import '../../../models/message.dart';
import '../../../theme/app_theme.dart';
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
    return isUser
        ? _UserBubble(content: message.content)
        : _AssistantMessage(content: message.content);
  }
}

class _UserBubble extends StatelessWidget {
  final String content;
  const _UserBubble({required this.content});

  @override
  Widget build(BuildContext context) {
    final tokens = context.tokens;
    return Align(
      alignment: Alignment.centerRight,
      child: LayoutBuilder(
        builder: (context, constraints) {
          return Container(
            margin: EdgeInsets.symmetric(vertical: tokens.spacing.sm),
            padding: EdgeInsets.symmetric(
              horizontal: tokens.spacing.md + 4,
              vertical: tokens.spacing.md,
            ),
            constraints: BoxConstraints(maxWidth: constraints.maxWidth * 0.75),
            decoration: BoxDecoration(
              color: tokens.colors.accentMuted,
              borderRadius: tokens.radius.mdAll,
              border: Border.all(color: tokens.colors.borderAccent, width: 1),
            ),
            child: SelectableText(
              content,
              style: tokens.typography.textTheme.bodyLarge?.copyWith(
                color: tokens.colors.textPrimary,
              ),
            ),
          );
        },
      ),
    );
  }
}

class _AssistantMessage extends StatelessWidget {
  final String content;
  const _AssistantMessage({required this.content});

  @override
  Widget build(BuildContext context) {
    final tokens = context.tokens;
    return Align(
      alignment: Alignment.centerLeft,
      child: LayoutBuilder(
        builder: (context, constraints) {
          return ConstrainedBox(
            constraints: BoxConstraints(maxWidth: constraints.maxWidth * 0.85),
            child: Padding(
              padding: EdgeInsets.symmetric(vertical: tokens.spacing.sm),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _RoleLabel(label: 'ASSISTANT', dotColor: tokens.colors.accent),
                  SizedBox(height: tokens.spacing.xs),
                  SelectableText(
                    content,
                    style: tokens.typography.textTheme.bodyLarge?.copyWith(
                      color: tokens.colors.textPrimary,
                    ),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }
}

class _RoleLabel extends StatelessWidget {
  final String label;
  final Color dotColor;
  const _RoleLabel({required this.label, required this.dotColor});

  @override
  Widget build(BuildContext context) {
    final tokens = context.tokens;
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 6,
          height: 6,
          decoration: BoxDecoration(
            color: dotColor,
            borderRadius: tokens.radius.fullAll,
          ),
        ),
        SizedBox(width: tokens.spacing.sm - 2),
        Text(
          label,
          style: tokens.typography.textTheme.labelSmall?.copyWith(
            color: tokens.colors.textTertiary,
          ),
        ),
      ],
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
            borderRadius: tokens.radius.xsAll,
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
        borderRadius: tokens.radius.mdAll,
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
