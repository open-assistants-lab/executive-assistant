import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

enum EaStatus { success, warning, error, info }

class EaStatusBadge extends StatelessWidget {
  final EaStatus status;
  final String label;

  const EaStatusBadge({super.key, required this.status, required this.label});

  @override
  Widget build(BuildContext context) {
    final t = context.tokens;
    final (bg, text, dot) = switch (status) {
      EaStatus.success => (t.colors.success, t.colors.success, t.colors.success),
      EaStatus.warning => (t.colors.warning, t.colors.warning, t.colors.warning),
      EaStatus.error => (t.colors.error, t.colors.error, t.colors.error),
      EaStatus.info => (t.colors.info, t.colors.info, t.colors.info),
    };

    return Container(
      height: 22,
      padding: EdgeInsets.symmetric(horizontal: t.spacing.xs),
      decoration: BoxDecoration(
        color: bg.withValues(alpha: 0.12),
        borderRadius: t.radius.smAll,
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 6,
            height: 6,
            decoration: BoxDecoration(color: dot, shape: BoxShape.circle),
          ),
          SizedBox(width: t.spacing.xs),
          Text(
            label,
            style: t.typography.textTheme.labelSmall
                ?.copyWith(color: text),
          ),
        ],
      ),
    );
  }
}
