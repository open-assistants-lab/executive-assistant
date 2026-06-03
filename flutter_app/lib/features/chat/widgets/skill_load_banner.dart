import 'package:flutter/material.dart';
import '../../../theme/app_theme.dart';

class SkillLoadBanner extends StatelessWidget {
  final String name;
  const SkillLoadBanner({super.key, required this.name});

  @override
  Widget build(BuildContext context) {
    final tokens = context.tokens;
    return Padding(
      padding: EdgeInsets.symmetric(
        vertical: tokens.spacing.xs,
        horizontal: tokens.spacing.md,
      ),
      child: Container(
        padding: EdgeInsets.symmetric(
          horizontal: tokens.spacing.sm + 2,
          vertical: tokens.spacing.xs + 2,
        ),
        decoration: BoxDecoration(
          color: tokens.colors.accent.withAlpha(18),
          borderRadius: tokens.radius.smAll,
          border: Border.all(
            color: tokens.colors.accent.withAlpha(80),
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Symbols.psychology, size: 14, color: tokens.colors.accent),
            SizedBox(width: tokens.spacing.xs + 2),
            Text(
              'Loaded: $name',
              style: tokens.typography.textTheme.labelSmall?.copyWith(
                color: tokens.colors.accent,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
