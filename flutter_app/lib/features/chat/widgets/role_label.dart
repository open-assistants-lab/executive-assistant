import 'package:flutter/material.dart';
import '../../../theme/app_theme.dart';

class RoleLabel extends StatefulWidget {
  final String label;
  final Color dotColor;
  final bool pulse;

  const RoleLabel({
    super.key,
    required this.label,
    required this.dotColor,
    this.pulse = false,
  });

  @override
  State<RoleLabel> createState() => _RoleLabelState();
}

class _RoleLabelState extends State<RoleLabel> with SingleTickerProviderStateMixin {
  AnimationController? _pulseController;

  @override
  void initState() {
    super.initState();
    if (widget.pulse) {
      _pulseController = AnimationController(
        vsync: this,
        duration: const Duration(milliseconds: 1200),
      )..repeat(reverse: true);
    }
  }

  @override
  void didUpdateWidget(covariant RoleLabel oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.pulse && _pulseController == null) {
      _pulseController = AnimationController(
        vsync: this,
        duration: const Duration(milliseconds: 1200),
      )..repeat(reverse: true);
    } else if (!widget.pulse && _pulseController != null) {
      _pulseController?.dispose();
      _pulseController = null;
    }
  }

  @override
  void dispose() {
    _pulseController?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final tokens = context.tokens;
    final reducedMotion = MediaQuery.of(context).disableAnimations;
    final shouldPulse = widget.pulse && !reducedMotion && _pulseController != null;

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        shouldPulse
            ? AnimatedBuilder(
                animation: _pulseController!,
                builder: (context, _) {
                  final opacity = 0.4 + 0.6 * _pulseController!.value;
                  return _Dot(
                    color: widget.dotColor.withValues(alpha: opacity),
                    radius: tokens.radius.fullAll,
                  );
                },
              )
            : _Dot(color: widget.dotColor, radius: tokens.radius.fullAll),
        SizedBox(width: tokens.spacing.sm - 2),
        Text(
          widget.label,
          style: tokens.typography.textTheme.labelSmall?.copyWith(
            color: tokens.colors.textTertiary,
          ),
        ),
      ],
    );
  }
}

class _Dot extends StatelessWidget {
  final Color color;
  final BorderRadius radius;
  const _Dot({required this.color, required this.radius});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 6,
      height: 6,
      decoration: BoxDecoration(color: color, borderRadius: radius),
    );
  }
}
