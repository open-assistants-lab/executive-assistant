import 'package:flutter/material.dart';
import '../../../theme/app_theme.dart';

class StatusCards extends StatelessWidget {
  final int unreadEmails;
  final int dueTasks;
  final int activeSubagents;

  const StatusCards({
    super.key,
    this.unreadEmails = 0,
    this.dueTasks = 0,
    this.activeSubagents = 0,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 110,
      child: ListView(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.screenEdge,
        ),
        children: [
          _StatusCard(
            icon: Icons.mail_outline,
            value: unreadEmails,
            label: 'Unread',
            color: AppColors.accent,
          ),
          const SizedBox(width: AppSpacing.betweenCards),
          _StatusCard(
            icon: Icons.check_circle_outline,
            value: dueTasks,
            label: 'Due',
            color: AppColors.warning,
          ),
          const SizedBox(width: AppSpacing.betweenCards),
          _StatusCard(
            icon: Icons.smart_toy_outlined,
            value: activeSubagents,
            label: 'Active',
            color: AppColors.primary,
          ),
        ],
      ),
    );
  }
}

class _StatusCard extends StatelessWidget {
  final IconData icon;
  final int value;
  final String label;
  final Color color;

  const _StatusCard({
    required this.icon,
    required this.value,
    required this.label,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 140,
      padding: const EdgeInsets.all(AppSpacing.cardPadding),
      decoration: BoxDecoration(
        color: AppColors.background,
        borderRadius: BorderRadius.circular(AppRadius.card),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.08),
              borderRadius: BorderRadius.circular(AppRadius.chip),
            ),
            child: Icon(icon, size: 20, color: color),
          ),
          Row(
            crossAxisAlignment: CrossAxisAlignment.baseline,
            textBaseline: TextBaseline.alphabetic,
            children: [
              Text(
                '$value',
                style: AppTypography.metric.copyWith(color: color),
              ),
              const SizedBox(width: 6),
              Text(
                label,
                style: AppTypography.caption.copyWith(
                  color: AppColors.textSecondary,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}