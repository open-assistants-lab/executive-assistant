import 'package:flutter/material.dart';
import '../../../theme/app_theme.dart';

class QuickActions extends StatelessWidget {
  final VoidCallback? onDraftReply;
  final VoidCallback? onSummarize;
  final VoidCallback? onSchedule;

  const QuickActions({
    super.key,
    this.onDraftReply,
    this.onSummarize,
    this.onSchedule,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.symmetric(
        horizontal: context.tokens.spacing.xl,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Quick Actions',
            style: context.tokens.typography.textTheme.headlineMedium!.copyWith(fontSize: 16, color: context.tokens.colors.textPrimary),
          ),
          SizedBox(height: context.tokens.spacing.sm),
          Wrap(
            spacing: context.tokens.spacing.sm,
            runSpacing: context.tokens.spacing.sm,
            children: [
              _ActionChip(
                icon: Symbols.reply,
                label: 'Draft reply',
                onTap: onDraftReply,
              ),
              _ActionChip(
                icon: Symbols.summarize,
                label: 'Summarize',
                onTap: onSummarize,
              ),
              _ActionChip(
                icon: Symbols.calendar_today,
                label: 'Schedule',
                onTap: onSchedule,
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _ActionChip extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback? onTap;

  const _ActionChip({
    required this.icon,
    required this.label,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return ActionChip(
      onPressed: onTap,
      avatar: Icon(icon, size: 16, color: context.tokens.colors.accent),
      label: Text(label),
      labelStyle: context.tokens.typography.textTheme.labelSmall!.copyWith(color: context.tokens.colors.accent),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(context.tokens.radius.md),
        side: BorderSide(color: context.tokens.colors.borderDefault),
      ),
      backgroundColor: context.tokens.colors.bgCanvas,
    );
  }
}