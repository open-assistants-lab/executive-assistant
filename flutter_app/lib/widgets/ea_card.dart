import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

enum EaCardVariant { static, hoverable, interactive }

class EaCard extends StatefulWidget {
  final Widget child;
  final EaCardVariant variant;
  final EdgeInsetsGeometry? padding;

  const EaCard({
    super.key,
    required this.child,
    this.variant = EaCardVariant.static,
    this.padding,
  });

  @override
  State<EaCard> createState() => _EaCardState();
}

class _EaCardState extends State<EaCard> {
  bool _isHovered = false;

  @override
  Widget build(BuildContext context) {
    final t = context.tokens;
    final bg = _isHovered && widget.variant != EaCardVariant.static
        ? t.colors.bgElevated
        : t.colors.bgSurface;
    final border = _isHovered && widget.variant != EaCardVariant.static
        ? t.colors.borderDefault
        : t.colors.borderSubtle;

    return MouseRegion(
      onEnter: widget.variant != EaCardVariant.static
          ? (_) => setState(() => _isHovered = true)
          : null,
      onExit: widget.variant != EaCardVariant.static
          ? (_) => setState(() => _isHovered = false)
          : null,
      child: AnimatedContainer(
        duration: t.motion.snappy,
        padding: widget.padding ?? EdgeInsets.all(t.spacing.md),
        decoration: BoxDecoration(
          color: bg,
          borderRadius: t.radius.lgAll,
          border: Border.all(color: border),
        ),
        child: widget.child,
      ),
    );
  }
}
