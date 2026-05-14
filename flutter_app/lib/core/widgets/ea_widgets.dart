import 'package:flutter/material.dart';
import 'package:executive_assistant/core/motion/motion.dart';

/// Button with press animation — scales 0.97 on press, springs back on release.
class EaButton extends StatefulWidget {
  final VoidCallback? onPressed;
  final Widget child;
  final ButtonStyle? style;

  const EaButton({
    super.key,
    required this.onPressed,
    required this.child,
    this.style,
  });

  @override
  State<EaButton> createState() => _EaButtonState();
}

class _EaButtonState extends State<EaButton>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  late final Animation<double> _scale;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(vsync: this, duration: EaMotion.snappy);
    _scale = EaMotion.buttonPressScale.animate(
      CurvedAnimation(parent: _controller, curve: EaMotion.snappyCurve),
    );
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (EaMotion.reducedMotion(context)) {
      return ElevatedButton(
        onPressed: widget.onPressed,
        style: widget.style,
        child: widget.child,
      );
    }
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, child) => Transform.scale(
        scale: _scale.value,
        child: ElevatedButton(
          onPressed: () {
            _controller.forward().then((_) => _controller.reverse());
            widget.onPressed?.call();
          },
          style: widget.style,
          child: widget.child,
        ),
      ),
    );
  }
}

/// ListTile with spring tap feedback.
class EaListTile extends StatelessWidget {
  final Widget? leading;
  final Widget title;
  final Widget? subtitle;
  final VoidCallback? onTap;
  final bool dense;

  const EaListTile({
    super.key,
    this.leading,
    required this.title,
    this.subtitle,
    this.onTap,
    this.dense = false,
  });

  @override
  Widget build(BuildContext context) {
    if (EaMotion.reducedMotion(context) || onTap == null) {
      return ListTile(
        leading: leading,
        title: title,
        subtitle: subtitle,
        onTap: onTap,
        dense: dense,
      );
    }
    return EaMotion.tapPulse(
      context,
      ListTile(
        leading: leading,
        title: title,
        subtitle: subtitle,
        dense: dense,
      ),
      onTap: onTap,
    );
  }
}

/// Card with hover elevation animation (desktop) and press feedback.
class EaCard extends StatefulWidget {
  final Widget child;
  final VoidCallback? onTap;

  const EaCard({super.key, required this.child, this.onTap});

  @override
  State<EaCard> createState() => _EaCardState();
}

class _EaCardState extends State<EaCard>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  late final Animation<double> _elevation;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(vsync: this, duration: EaMotion.snappy);
    _elevation = Tween(begin: 1.0, end: 4.0).animate(
      CurvedAnimation(parent: _controller, curve: EaMotion.snappyCurve),
    );
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (EaMotion.reducedMotion(context)) {
      return Card(child: widget.child);
    }
    return MouseRegion(
      onEnter: (_) => _controller.forward(),
      onExit: (_) => _controller.reverse(),
      child: GestureDetector(
        onTap: widget.onTap,
        onTapDown: widget.onTap != null ? (_) => _controller.forward() : null,
        onTapUp: widget.onTap != null ? (_) => _controller.reverse() : null,
        onTapCancel: () => _controller.reverse(),
        child: AnimatedBuilder(
          animation: _elevation,
          builder: (context, child) => Card(
            elevation: _elevation.value,
            child: child,
          ),
          child: widget.child,
        ),
      ),
    );
  }
}

/// Progress bar with smooth determinate fill animation.
/// Indeterminate version uses continuous loop animation.
class EaProgress extends StatelessWidget {
  final double? value; // null = indeterminate
  final Color? color;

  const EaProgress({super.key, this.value, this.color});

  @override
  Widget build(BuildContext context) {
    if (value != null) {
      return TweenAnimationBuilder<double>(
        tween: Tween(begin: 0, end: value!.clamp(0.0, 1.0)),
        duration: EaMotion.fluid,
        curve: EaMotion.fluidCurve,
        builder: (context, val, _) {
          return LinearProgressIndicator(
            value: val,
            color: color ?? Theme.of(context).colorScheme.primary,
            backgroundColor: Theme.of(context).colorScheme.surfaceContainerHighest,
          );
        },
      );
    }
    return LinearProgressIndicator(
      color: color ?? Theme.of(context).colorScheme.primary,
      backgroundColor: Theme.of(context).colorScheme.surfaceContainerHighest,
    );
  }
}
