import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

class EaChip extends StatefulWidget {
  final String label;
  final bool isSelected;
  final VoidCallback? onTap;
  final VoidCallback? onDismiss;

  const EaChip({
    super.key,
    required this.label,
    this.isSelected = false,
    this.onTap,
    this.onDismiss,
  });

  @override
  State<EaChip> createState() => _EaChipState();
}

class _EaChipState extends State<EaChip> {
  bool _isHovered = false;

  @override
  Widget build(BuildContext context) {
    final t = context.tokens;
    final bg = widget.isSelected
        ? t.colors.accentMuted
        : _isHovered
            ? t.colors.bgElevated
            : t.colors.bgField;
    final border =
        widget.isSelected ? t.colors.accent : t.colors.borderSubtle;
    final textColor =
        widget.isSelected ? t.colors.textPrimary : t.colors.textSecondary;

    return MouseRegion(
      onEnter: (_) => setState(() => _isHovered = true),
      onExit: (_) => setState(() => _isHovered = false),
      child: GestureDetector(
        onTap: widget.onTap,
        child: AnimatedContainer(
          duration: t.motion.instant,
          height: 28,
          padding: EdgeInsets.symmetric(horizontal: t.spacing.sm),
          decoration: BoxDecoration(
            color: bg,
            borderRadius: t.radius.mdAll,
            border: Border.all(color: border),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                widget.label,
                style: t.typography.textTheme.bodySmall
                    ?.copyWith(color: textColor),
              ),
              if (widget.onDismiss != null) ...[
                SizedBox(width: t.spacing.xs),
                GestureDetector(
                  onTap: widget.onDismiss,
                  child: Icon(Symbols.close, size: 12, color: textColor),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
