import 'package:flutter/material.dart';
import '../../../theme/app_theme.dart';

class StreamingBubble extends StatelessWidget {
  final String text;

  const StreamingBubble({super.key, required this.text});

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.centerLeft,
      child: LayoutBuilder(
        builder: (context, constraints) {
          return Container(
            margin: const EdgeInsets.symmetric(vertical: 4),
            padding: const EdgeInsets.all(12),
            constraints: BoxConstraints(
              maxWidth: constraints.maxWidth * 0.85,
            ),
            decoration: const BoxDecoration(
              color: AppColors.assistantBubble,
              borderRadius: BorderRadius.only(
                topLeft: Radius.circular(AppRadius.messageBubbleTop),
                topRight: Radius.circular(AppRadius.messageBubbleTop),
                bottomLeft: Radius.circular(AppRadius.messageBubbleBottom),
                bottomRight: Radius.circular(AppRadius.messageBubbleTop),
              ),
            ),
            child: Row(
              children: [
                Expanded(
                  child: SelectableText(
                    text,
                    style: AppTypography.body.copyWith(
                      color: AppColors.assistantBubbleText,
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                SizedBox(
                  width: 14,
                  height: 14,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    color: AppColors.accent,
                  ),
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}