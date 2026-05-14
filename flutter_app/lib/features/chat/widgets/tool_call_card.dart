import 'package:flutter/material.dart';
import '../../../theme/app_theme.dart';
import '../../../models/message.dart';

class ToolCallCard extends StatelessWidget {
  final ToolCallDisplay toolCall;

  const ToolCallCard({super.key, required this.toolCall});

  @override
  Widget build(BuildContext context) {
    final hasResult = toolCall.resultPreview != null;
    return Container(
      margin: const EdgeInsets.symmetric(vertical: 4),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: AppColors.toolChipBg,
        borderRadius: BorderRadius.circular(AppRadius.chip),
      ),
      child: Row(
        children: [
          Icon(
            hasResult ? Icons.check_circle : Icons.sync,
            size: 16,
            color: hasResult ? AppColors.success : AppColors.accent,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  toolCall.toolName,
                  style: AppTypography.toolLabel.copyWith(
                    color: AppColors.toolChipText,
                  ),
                ),
                if (toolCall.args.isNotEmpty)
                  Text(
                    _formatArgs(toolCall.args),
                    style: AppTypography.caption.copyWith(
                      color: AppColors.textSecondary,
                    ),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
              ],
            ),
          ),
          if (hasResult)
            Icon(Icons.expand_more, size: 16, color: AppColors.textDim),
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