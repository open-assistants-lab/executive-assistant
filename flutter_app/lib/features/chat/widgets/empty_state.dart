import 'package:flutter/material.dart';
import '../../../theme/app_theme.dart';

class ChatEmptyState extends StatelessWidget {
  final void Function(String)? onSuggestionTap;
  final List<String> suggestions;

  const ChatEmptyState({
    super.key,
    this.onSuggestionTap,
    this.suggestions = const [
      'Summarize my emails',
      "What's on my calendar?",
      'Add a todo',
    ],
  });

  @override
  Widget build(BuildContext context) {
    final tokens = context.tokens;
    return Center(
      child: Padding(
        padding: EdgeInsets.symmetric(horizontal: tokens.spacing.lg),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 12,
              height: 12,
              decoration: BoxDecoration(
                color: tokens.colors.accent.withValues(alpha: 0.6),
                borderRadius: tokens.radius.fullAll,
              ),
            ),
            SizedBox(height: tokens.spacing.lg),
            Text(
              "Ask anything. I'm here to help.",
              textAlign: TextAlign.center,
              style: tokens.typography.textTheme.bodyLarge?.copyWith(
                color: tokens.colors.textSecondary,
              ),
            ),
            SizedBox(height: tokens.spacing.xl),
            Wrap(
              spacing: tokens.spacing.sm,
              runSpacing: tokens.spacing.sm,
              alignment: WrapAlignment.center,
              children: suggestions
                  .map((s) => _SuggestionChip(
                        label: s,
                        onTap: () => onSuggestionTap?.call(s),
                      ))
                  .toList(),
            ),
          ],
        ),
      ),
    );
  }
}

class _SuggestionChip extends StatefulWidget {
  final String label;
  final VoidCallback onTap;
  const _SuggestionChip({required this.label, required this.onTap});

  @override
  State<_SuggestionChip> createState() => _SuggestionChipState();
}

class _SuggestionChipState extends State<_SuggestionChip> {
  bool _hover = false;

  @override
  Widget build(BuildContext context) {
    final tokens = context.tokens;
    return MouseRegion(
      cursor: SystemMouseCursors.click,
      onEnter: (_) => setState(() => _hover = true),
      onExit: (_) => setState(() => _hover = false),
      child: GestureDetector(
        onTap: widget.onTap,
        child: AnimatedContainer(
          duration: tokens.motion.fast,
          curve: tokens.motion.curveStandard,
          padding: EdgeInsets.symmetric(
            horizontal: tokens.spacing.md,
            vertical: tokens.spacing.sm,
          ),
          decoration: BoxDecoration(
            color: tokens.colors.bgSurface,
            border: Border.all(
              color: _hover ? tokens.colors.borderAccent : tokens.colors.borderSubtle,
              width: 1,
            ),
            borderRadius: tokens.radius.smAll,
          ),
          child: Text(
            widget.label,
            style: tokens.typography.textTheme.bodySmall?.copyWith(
              color: tokens.colors.textPrimary,
            ),
          ),
        ),
      ),
    );
  }
}
