import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

enum EaDividerVariant { subtle, accent }

class EaDivider extends StatelessWidget {
  final EaDividerVariant variant;
  final EdgeInsetsGeometry? margin;

  const EaDivider({
    super.key,
    this.variant = EaDividerVariant.subtle,
    this.margin,
  });

  @override
  Widget build(BuildContext context) {
    final t = context.tokens;
    final color = variant == EaDividerVariant.accent
        ? t.colors.borderAccent
        : t.colors.borderSubtle;
    return Container(
      margin: margin ?? EdgeInsets.symmetric(vertical: t.spacing.sm),
      height: 1,
      color: color,
    );
  }
}
