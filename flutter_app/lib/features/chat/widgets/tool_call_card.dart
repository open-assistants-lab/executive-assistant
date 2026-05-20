import 'package:flutter/material.dart';
import '../../../theme/app_theme.dart';
import '../../../models/message.dart';

class ToolCallCard extends StatelessWidget {
  final ToolCallDisplay toolCall;

  const ToolCallCard({super.key, required this.toolCall});

  @override
  Widget build(BuildContext context) {
    final tokens = context.tokens;
    final hasResult = toolCall.resultPreview != null;
    final statusColor = hasResult ? tokens.colors.success : tokens.colors.accent;
    return Container(
      margin: EdgeInsets.symmetric(vertical: tokens.spacing.xs),
      padding: EdgeInsets.all(tokens.spacing.sm + 2),
      decoration: BoxDecoration(
        color: tokens.colors.bgField,
        borderRadius: BorderRadius.circular(tokens.radius.md),
        border: Border(
          left: BorderSide(
            color: hasResult
                ? tokens.colors.success
                : toolCall.args.isNotEmpty
                    ? tokens.colors.accent
                    : tokens.colors.textTertiary,
            width: 3,
          ),
        ),
      ),
      child: Row(
        children: [
          Icon(
            hasResult ? Symbols.check_circle : Symbols.sync,
            size: 16,
            color: statusColor,
          ),
          SizedBox(width: tokens.spacing.sm),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  toolCall.toolName,
                  style: tokens.typography.monoTheme.bodyMedium?.copyWith(
                    color: tokens.colors.textPrimary,
                  ),
                ),
                if (toolCall.args.isNotEmpty)
                  Text(
                    _formatArgs(toolCall.args),
                    style: tokens.typography.textTheme.bodySmall?.copyWith(
                      color: tokens.colors.textSecondary,
                    ),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
              ],
            ),
          ),
          if (hasResult)
            Icon(Symbols.expand_more, size: 16, color: tokens.colors.textTertiary),
        ],
      ),
    );
  }

  String _formatArgs(Map<String, dynamic> args) {
    var entries = args.entries.take(3).map((e) => '${e.key}: ${e.value}').join(', ');
    if (args.length > 3) entries = '$entries...';
    return entries;
  }
}