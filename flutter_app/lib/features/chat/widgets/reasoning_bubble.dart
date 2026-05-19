import 'package:flutter/material.dart';
import '../../../theme/app_theme.dart';

class ReasoningBubble extends StatefulWidget {
  final String content;

  const ReasoningBubble({super.key, required this.content});

  @override
  State<ReasoningBubble> createState() => _ReasoningBubbleState();
}

class _ReasoningBubbleState extends State<ReasoningBubble> {
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
    if (widget.content.trim().isEmpty) return const SizedBox.shrink();
    final tokens = context.tokens;

    return Padding(
      padding: EdgeInsets.symmetric(vertical: tokens.spacing.xs),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: () => setState(() => _expanded = !_expanded),
          borderRadius: BorderRadius.circular(tokens.radius.md),
          child: Container(
            padding: EdgeInsets.symmetric(horizontal: tokens.spacing.md, vertical: tokens.spacing.sm + 2),
            decoration: BoxDecoration(
              color: tokens.colors.bgSurface.withAlpha(180),
              borderRadius: BorderRadius.circular(tokens.radius.md),
              border: Border.all(
                color: tokens.colors.borderSubtle.withAlpha(150),
              ),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(Icons.psychology_outlined,
                        size: 16, color: tokens.colors.textTertiary),
                    SizedBox(width: tokens.spacing.sm),
                    Text(
                      'Agent reasoning',
                      style: tokens.typography.textTheme.bodySmall?.copyWith(
                        color: tokens.colors.textTertiary,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const Spacer(),
                    AnimatedRotation(
                      turns: _expanded ? 0.5 : 0.0,
                      duration: const Duration(milliseconds: 200),
                      child: Icon(Icons.expand_more,
                          size: 18, color: tokens.colors.textTertiary),
                    ),
                  ],
                ),
                if (_expanded) ...[
                  SizedBox(height: tokens.spacing.sm),
                  Text(
                    widget.content,
                    style: tokens.typography.textTheme.bodySmall?.copyWith(
                      color: tokens.colors.textSecondary,
                      height: 1.5,
                    ),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}
