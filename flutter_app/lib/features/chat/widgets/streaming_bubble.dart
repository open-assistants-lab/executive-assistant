import 'package:flutter/material.dart';
import '../../../theme/app_theme.dart';

class StreamingBubble extends StatelessWidget {
  final String text;

  const StreamingBubble({super.key, required this.text});

  @override
  Widget build(BuildContext context) {
    final tokens = context.tokens;
    return Align(
      alignment: Alignment.centerLeft,
      child: LayoutBuilder(
        builder: (context, constraints) {
          return Container(
            margin: EdgeInsets.symmetric(vertical: tokens.spacing.xs),
            padding: EdgeInsets.all(tokens.spacing.md),
            constraints: BoxConstraints(
              maxWidth: constraints.maxWidth * 0.85,
            ),
            decoration: BoxDecoration(
              color: tokens.colors.bgSurface,
              borderRadius: BorderRadius.only(
                topLeft: Radius.circular(tokens.radius.xl),
                topRight: Radius.circular(tokens.radius.xl),
                bottomLeft: Radius.circular(tokens.radius.sm),
                bottomRight: Radius.circular(tokens.radius.xl),
              ),
            ),
            child: Row(
              children: [
                Expanded(
                  child: SelectableText(
                    text,
                    style: tokens.typography.textTheme.bodyLarge?.copyWith(
                      color: tokens.colors.textPrimary,
                    ),
                  ),
                ),
                SizedBox(width: tokens.spacing.sm),
                SizedBox(
                  width: 14,
                  height: 14,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    color: tokens.colors.accent,
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