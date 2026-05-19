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
        padding: EdgeInsets.symmetric(
          horizontal: context.tokens.spacing.xl,
        ),
        children: [
          _StatusCard(
            icon: Icons.mail_outline,
            value: unreadEmails,
            label: 'Unread',
            color: context.tokens.colors.accent,
          ),
          SizedBox(width: context.tokens.spacing.xxl),
          _StatusCard(
            icon: Icons.check_circle_outline,
            value: dueTasks,
            label: 'Due',
            color: context.tokens.colors.warning,
          ),
          SizedBox(width: context.tokens.spacing.xxl),
          _StatusCard(
            icon: Icons.smart_toy_outlined,
            value: activeSubagents,
            label: 'Active',
            color: context.tokens.colors.accent,
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
      padding: EdgeInsets.all(context.tokens.spacing.md),
      decoration: BoxDecoration(
        color: context.tokens.colors.bgCanvas,
        borderRadius: BorderRadius.circular(context.tokens.radius.lg),
        border: Border.all(color: context.tokens.colors.borderDefault),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.08),
              borderRadius: BorderRadius.circular(context.tokens.radius.md),
            ),
            child: Icon(icon, size: 20, color: color),
          ),
          Row(
            crossAxisAlignment: CrossAxisAlignment.baseline,
            textBaseline: TextBaseline.alphabetic,
            children: [
              Text(
                '$value',
                style: context.tokens.typography.textTheme.headlineSmall!.copyWith(color: color),
              ),
              const SizedBox(width: 6),
              Text(
                label,
                style: context.tokens.typography.textTheme.bodySmall!.copyWith(
                  color: context.tokens.colors.textSecondary,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}