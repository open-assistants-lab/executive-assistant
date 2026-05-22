import 'package:flutter/material.dart';

class EaAnimations {
  EaAnimations._();

  /// Fades a child in over 200ms. Respects reduced-motion (instant if enabled).
  static Widget fadeIn({
    required Widget child,
    Duration duration = const Duration(milliseconds: 200),
    Curve curve = const Cubic(0.2, 0, 0, 1),
  }) {
    return _FadeIn(duration: duration, curve: curve, child: child);
  }

  @Deprecated('Use EaAnimations.fadeIn instead')
  static Widget staggeredEntry({required int index, required Widget child}) {
    return fadeIn(child: child);
  }
}

class _FadeIn extends StatefulWidget {
  final Widget child;
  final Duration duration;
  final Curve curve;
  const _FadeIn({required this.child, required this.duration, required this.curve});

  @override
  State<_FadeIn> createState() => _FadeInState();
}

class _FadeInState extends State<_FadeIn> with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(vsync: this, duration: widget.duration);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      final reducedMotion = MediaQuery.of(context).disableAnimations;
      if (reducedMotion) {
        _controller.value = 1.0;
      } else {
        _controller.forward();
      }
    });
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (_, child) => Opacity(
        opacity: widget.curve.transform(_controller.value),
        child: child,
      ),
      child: widget.child,
    );
  }
}
