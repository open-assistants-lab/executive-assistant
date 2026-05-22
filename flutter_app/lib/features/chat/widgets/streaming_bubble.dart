import 'package:flutter/material.dart';
import '../../../theme/app_theme.dart';
import 'role_label.dart';

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
          return ConstrainedBox(
            constraints: BoxConstraints(maxWidth: constraints.maxWidth * 0.85),
            child: Padding(
              padding: EdgeInsets.symmetric(vertical: tokens.spacing.sm),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  RoleLabel(
                    label: 'ASSISTANT',
                    dotColor: tokens.colors.accent,
                    pulse: true,
                  ),
                  SizedBox(height: tokens.spacing.xs),
                  SelectableText(
                    text,
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
