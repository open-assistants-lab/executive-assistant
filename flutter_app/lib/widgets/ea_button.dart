import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

class EaPrimaryButton extends StatelessWidget {
  final VoidCallback? onPressed;
  final String label;
  final Widget? icon;
  final bool isDisabled;
  final bool isLoading;

  const EaPrimaryButton({
    super.key,
    required this.onPressed,
    required this.label,
    this.icon,
    this.isDisabled = false,
    this.isLoading = false,
  });

  @override
  Widget build(BuildContext context) {
    final t = context.tokens;
    final enabled = onPressed != null && !isDisabled && !isLoading;

    return GestureDetector(
      onTap: enabled ? onPressed : null,
      child: AnimatedContainer(
        duration: t.motion.snappy,
        height: 40,
        padding: EdgeInsets.symmetric(horizontal: t.spacing.md),
        decoration: BoxDecoration(
          color: enabled ? t.colors.accent : t.colors.accent.withValues(alpha: 0.4),
          borderRadius: t.radius.mdAll,
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (isLoading)
              Padding(
                padding: EdgeInsets.only(right: t.spacing.sm),
                child: SizedBox(
                  width: 14,
                  height: 14,
                  child: CircularProgressIndicator(
                    strokeWidth: 1.5,
                    color: t.colors.textInverse,
                  ),
                ),
              )
            else if (icon != null)
              Padding(
                padding: EdgeInsets.only(right: t.spacing.sm),
                child: IconTheme(
                  data: IconThemeData(color: t.colors.textInverse, size: 18),
                  child: icon!,
                ),
              ),
            Text(
              label,
              style: t.typography.textTheme.bodyMedium
                  ?.copyWith(color: t.colors.textInverse),
            ),
          ],
        ),
      ),
    );
  }
}

class EaSecondaryButton extends StatelessWidget {
  final VoidCallback? onPressed;
  final String label;
  final Widget? icon;
  final bool isDisabled;
  final bool isLoading;

  const EaSecondaryButton({
    super.key,
    required this.onPressed,
    required this.label,
    this.icon,
    this.isDisabled = false,
    this.isLoading = false,
  });

  @override
  Widget build(BuildContext context) {
    final t = context.tokens;
    final enabled = onPressed != null && !isDisabled && !isLoading;

    return GestureDetector(
      onTap: enabled ? onPressed : null,
      child: AnimatedContainer(
        duration: t.motion.snappy,
        height: 40,
        padding: EdgeInsets.symmetric(horizontal: t.spacing.md),
        decoration: BoxDecoration(
          border: Border.all(
            color: enabled
                ? t.colors.borderDefault
                : t.colors.borderDefault.withValues(alpha: 0.4),
          ),
          borderRadius: t.radius.mdAll,
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (icon != null)
              Padding(
                padding: EdgeInsets.only(right: t.spacing.sm),
                child: IconTheme(
                  data: IconThemeData(
                    color: t.colors.textPrimary,
                    size: 18,
                  ),
                  child: icon!,
                ),
              ),
            Text(
              label,
              style: t.typography.textTheme.bodyMedium?.copyWith(
                color: enabled ? t.colors.textPrimary : t.colors.textTertiary,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class EaGhostButton extends StatelessWidget {
  final VoidCallback? onPressed;
  final String label;
  final Widget? icon;
  final bool isDisabled;

  const EaGhostButton({
    super.key,
    required this.onPressed,
    required this.label,
    this.icon,
    this.isDisabled = false,
  });

  @override
  Widget build(BuildContext context) {
    final t = context.tokens;
    final enabled = onPressed != null && !isDisabled;

    return GestureDetector(
      onTap: enabled ? onPressed : null,
      child: Padding(
        padding: EdgeInsets.symmetric(
          horizontal: t.spacing.sm,
          vertical: t.spacing.xs,
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (icon != null)
              Padding(
                padding: EdgeInsets.only(right: t.spacing.sm),
                child: IconTheme(
                  data: IconThemeData(
                    color: enabled
                        ? t.colors.textSecondary
                        : t.colors.textTertiary,
                    size: 18,
                  ),
                  child: icon!,
                ),
              ),
            Text(
              label,
              style: t.typography.textTheme.bodyMedium?.copyWith(
                color: enabled
                    ? t.colors.textSecondary
                    : t.colors.textTertiary,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class EaDangerButton extends StatelessWidget {
  final VoidCallback? onPressed;
  final String label;
  final bool isDisabled;
  final bool isLoading;

  const EaDangerButton({
    super.key,
    required this.onPressed,
    required this.label,
    this.isDisabled = false,
    this.isLoading = false,
  });

  @override
  Widget build(BuildContext context) {
    final t = context.tokens;
    final enabled = onPressed != null && !isDisabled && !isLoading;

    return GestureDetector(
      onTap: enabled ? onPressed : null,
      child: AnimatedContainer(
        duration: t.motion.snappy,
        height: 40,
        padding: EdgeInsets.symmetric(horizontal: t.spacing.md),
        decoration: BoxDecoration(
          color: enabled
              ? t.colors.error
              : t.colors.error.withValues(alpha: 0.4),
          borderRadius: t.radius.mdAll,
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (isLoading)
              Padding(
                padding: EdgeInsets.only(right: t.spacing.sm),
                child: SizedBox(
                  width: 14,
                  height: 14,
                  child: CircularProgressIndicator(
                    strokeWidth: 1.5,
                    color: Colors.white,
                  ),
                ),
              ),
            Text(
              label,
              style: t.typography.textTheme.bodyMedium
                  ?.copyWith(color: Colors.white),
            ),
          ],
        ),
      ),
    );
  }
}
