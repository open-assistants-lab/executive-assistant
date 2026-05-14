import 'package:flutter/material.dart';

/// EA motion system presets — snappy, fluid, intuitive.
///
/// Three principles, three durations:
///   - Snappy (200ms) — fast cuts, match-cut transitions, button presses
///   - Fluid (400ms) — organic rhythm, list entries, content flow
///   - Intuitive (600ms) — natural pace, page transitions, sheet presentations
class EaMotion {
  EaMotion._();

  // ── Durations ──

  static const Duration snappy = Duration(milliseconds: 200);
  static const Duration fluid = Duration(milliseconds: 400);
  static const Duration intuitive = Duration(milliseconds: 600);

  // ── Curves ──

  /// Button press, tap feedback — fast snap with slight bounce
  static const Curve snappyCurve = Curves.easeOutBack;

  /// List entry, content flow — organic, no bounce
  static const Curve fluidCurve = Curves.easeOutCubic;

  /// Page transitions, sheet presentation — natural finger-swipe feel
  static const Curve intuitiveCurve = Curves.easeInOutCubic;

  // ── Page Transitions ──

  /// Upwards: starting a new flow (compose, new workspace).
  /// Screen slides up from the bottom.
  static SlideTransition upwardTransition(Animation<double> animation, Widget child) {
    return SlideTransition(
      position: Tween<Offset>(
        begin: const Offset(0, 0.3),
        end: Offset.zero,
      ).chain(CurveTween(curve: intuitiveCurve)).animate(animation),
      child: child,
    );
  }

  /// Sideways: continuing within a flow (list → detail).
  /// Screen slides in from the right.
  static SlideTransition sidewaysTransition(Animation<double> animation, Widget child) {
    return SlideTransition(
      position: Tween<Offset>(
        begin: const Offset(0.15, 0),
        end: Offset.zero,
      ).chain(CurveTween(curve: intuitiveCurve)).animate(animation),
      child: FadeTransition(opacity: animation, child: child),
    );
  }

  /// Modal transition: overlay from bottom with partial slide.
  static SlideTransition modalTransition(Animation<double> animation, Widget child) {
    return SlideTransition(
      position: Tween<Offset>(
        begin: const Offset(0, 0.5),
        end: Offset.zero,
      ).chain(CurveTween(curve: intuitiveCurve)).animate(animation),
      child: child,
    );
  }

  // ── Micro-Interactions ──

  /// Button press: scale down slightly, springs back.
  static final Animatable<double> buttonPressScale = TweenSequence([
    TweenSequenceItem(tween: Tween(begin: 1.0, end: 0.97), weight: 1),
    TweenSequenceItem(tween: Tween(begin: 0.97, end: 1.0), weight: 3),
  ]);

  /// List item tap: gentle pulse with spring return.
  static Widget tapPulse(BuildContext context, Widget child, {VoidCallback? onTap}) {
    return GestureDetector(
      onTap: onTap,
      child: _TapPulse(child: child),
    );
  }

  /// Staggered entry: items slide up + fade in with delay.
  static Widget staggeredEntry(int index, Widget child) {
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0.0, end: 1.0),
      duration: fluid,
      curve: Interval(
        (index * 0.05).clamp(0.0, 0.8),
        1.0,
        curve: fluidCurve,
      ),
      builder: (context, value, child) {
        return Opacity(
          opacity: value,
          child: Transform.translate(
            offset: Offset(0, 20 * (1 - value)),
            child: child,
          ),
        );
      },
      child: child,
    );
  }

  /// Check if user prefers reduced motion.
  static bool reducedMotion(BuildContext context) {
    return MediaQuery.maybeOf(context)?.disableAnimations ?? false;
  }
}

/// Lightweight tap pulse — scales on press, springs back on release.
class _TapPulse extends StatefulWidget {
  final Widget child;
  const _TapPulse({required this.child});

  @override
  State<_TapPulse> createState() => _TapPulseState();
}

class _TapPulseState extends State<_TapPulse> with SingleTickerProviderStateMixin {
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

  void _onTapDown(TapDownDetails _) => _controller.forward();
  void _onTapUp(TapUpDetails _) => _controller.reverse();
  void _onTapCancel() => _controller.reverse();

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTapDown: _onTapDown,
      onTapUp: _onTapUp,
      onTapCancel: _onTapCancel,
      child: AnimatedBuilder(
        animation: _scale,
        builder: (context, child) => Transform.scale(scale: _scale.value, child: child),
        child: widget.child,
      ),
    );
  }
}
