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
    return Align(
      alignment: Alignment.centerLeft,
      child: LayoutBuilder(
        builder: (context, constraints) {
          return ConstrainedBox(
            constraints: BoxConstraints(maxWidth: constraints.maxWidth * 0.85),
            child: Container(
              margin: EdgeInsets.symmetric(vertical: tokens.spacing.sm),
              decoration: BoxDecoration(
                color: tokens.colors.bgSurface,
                border: Border.all(color: tokens.colors.borderSubtle, width: 1),
                borderRadius: tokens.radius.mdAll,
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Material(
                    color: Colors.transparent,
                    child: InkWell(
                      onTap: () => setState(() => _expanded = !_expanded),
                      borderRadius: tokens.radius.mdAll,
                      child: Padding(
                        padding: EdgeInsets.symmetric(
                          horizontal: tokens.spacing.md,
                          vertical: tokens.spacing.md - 2,
                        ),
                        child: Row(
                          children: [
                            Icon(
                              Symbols.psychology,
                              size: 14,
                              color: tokens.colors.textTertiary,
                            ),
                            SizedBox(width: tokens.spacing.sm),
                            Text(
                              'REASONING',
                              style: tokens.typography.textTheme.labelSmall?.copyWith(
                                color: tokens.colors.textTertiary,
                              ),
                            ),
                            const Spacer(),
                            AnimatedRotation(
                              turns: _expanded ? 0.5 : 0,
                              duration: tokens.motion.base,
                              curve: tokens.motion.curveStandard,
                              child: Icon(
                                Symbols.expand_more,
                                size: 16,
                                color: tokens.colors.textTertiary,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                  AnimatedSize(
                    duration: tokens.motion.base,
                    curve: tokens.motion.curveStandard,
                    alignment: Alignment.topCenter,
                    child: _expanded
                        ? Padding(
                            padding: EdgeInsets.fromLTRB(
                              tokens.spacing.md,
                              0,
                              tokens.spacing.md,
                              tokens.spacing.md,
                            ),
                            child: SelectableText(
                              widget.content,
                              style: tokens.typography.monoTheme.bodySmall?.copyWith(
                                color: tokens.colors.textSecondary,
                              ),
                            ),
                          )
                        : const SizedBox.shrink(),
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
