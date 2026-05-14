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
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.screenEdge,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Quick Actions',
            style: AppTypography.sectionTitle.copyWith(fontSize: 16),
          ),
          const SizedBox(height: AppSpacing.itemGap),
          Wrap(
            spacing: AppSpacing.itemGap,
            runSpacing: AppSpacing.itemGap,
            children: [
              _ActionChip(
                icon: Icons.reply,
                label: 'Draft reply',
                onTap: onDraftReply,
              ),
              _ActionChip(
                icon: Icons.summarize,
                label: 'Summarize',
                onTap: onSummarize,
              ),
              _ActionChip(
                icon: Icons.calendar_today,
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
      avatar: Icon(icon, size: 16, color: AppColors.accent),
      label: Text(label),
      labelStyle: AppTypography.chip.copyWith(color: AppColors.primary),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(AppRadius.chip),
        side: const BorderSide(color: AppColors.border),
      ),
      backgroundColor: AppColors.background,
    );
  }
}