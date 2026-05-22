import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

enum EaButtonVariant { primary, secondary, ghost }

class EaButton extends StatefulWidget {
  final String label;
  final VoidCallback? onPressed;
  final EaButtonVariant variant;
  final IconData? icon;

  const EaButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.variant = EaButtonVariant.primary,
    this.icon,
  });

  const EaButton.primary({
    Key? key,
    required String label,
    required VoidCallback? onPressed,
    IconData? icon,
  }) : this(
          key: key,
          label: label,
          onPressed: onPressed,
          icon: icon,
          variant: EaButtonVariant.primary,
        );

  const EaButton.secondary({
    Key? key,
    required String label,
    required VoidCallback? onPressed,
    IconData? icon,
  }) : this(
          key: key,
          label: label,
          onPressed: onPressed,
          icon: icon,
          variant: EaButtonVariant.secondary,
        );

  const EaButton.ghost({
    Key? key,
    required String label,
    required VoidCallback? onPressed,
    IconData? icon,
  }) : this(
          key: key,
          label: label,
          onPressed: onPressed,
          icon: icon,
          variant: EaButtonVariant.ghost,
        );

  @override
  State<EaButton> createState() => _EaButtonState();
}

class _EaButtonState extends State<EaButton> {
  bool _pressed = false;

  @override
  Widget build(BuildContext context) {
    final tokens = context.tokens;
    final enabled = widget.onPressed != null;

    final (bg, fg, border) = switch (widget.variant) {
      EaButtonVariant.primary => (
          tokens.colors.accent,
          tokens.colors.textInverse,
          null as Color?,
        ),
      EaButtonVariant.secondary => (
          Colors.transparent,
          tokens.colors.textPrimary,
          tokens.colors.borderDefault as Color?,
        ),
      EaButtonVariant.ghost => (
          Colors.transparent,
          tokens.colors.textPrimary,
          null as Color?,
        ),
    };

    return Opacity(
      opacity: enabled ? 1.0 : 0.4,
      child: GestureDetector(
        onTapDown: (_) => setState(() => _pressed = true),
        onTapCancel: () => setState(() => _pressed = false),
        onTapUp: (_) => setState(() => _pressed = false),
        child: AnimatedScale(
          scale: _pressed ? tokens.motion.pressScale : 1.0,
          duration: const Duration(milliseconds: 100),
          curve: tokens.motion.curveStandard,
          child: Material(
            color: bg,
            borderRadius: tokens.radius.smAll,
            child: InkWell(
              onTap: enabled ? widget.onPressed : null,
              borderRadius: tokens.radius.smAll,
              hoverColor: widget.variant == EaButtonVariant.primary
                  ? tokens.colors.accentHover
                  : tokens.colors.bgSurface,
              child: Container(
                padding: EdgeInsets.symmetric(
                  horizontal: tokens.spacing.md + 2,
                  vertical: tokens.spacing.sm,
                ),
                decoration: BoxDecoration(
                  borderRadius: tokens.radius.smAll,
                  border: border != null
                      ? Border.all(color: border, width: 1)
                      : null,
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    if (widget.icon != null) ...[
                      Icon(widget.icon, size: 14, color: fg),
                      SizedBox(width: tokens.spacing.xs + 2),
                    ],
                    Text(
                      widget.label,
                      style: tokens.typography.textTheme.labelLarge
                          ?.copyWith(color: fg),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
