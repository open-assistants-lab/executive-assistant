import 'package:flutter/material.dart';

class EaAnimations {
  static Widget fadeIn({
    required Widget child,
    Duration duration = const Duration(milliseconds: 200),
    Curve curve = Curves.easeOutCubic,
  }) {
    return Builder(
      builder: (context) {
        final reducedMotion =
            MediaQuery.maybeOf(context)?.disableAnimations ?? false;
        return TweenAnimationBuilder<double>(
          tween: Tween(begin: reducedMotion ? 1.0 : 0.0, end: 1.0),
          duration: reducedMotion ? Duration.zero : duration,
          curve: curve,
          builder: (context, value, c) {
            return Opacity(opacity: value, child: c);
          },
          child: child,
        );
      },
    );
  }

  static Widget staggeredEntry({
    required int index,
    required Widget child,
    Duration delayPerItem = const Duration(milliseconds: 50),
  }) {
    return fadeIn(child: child);
  }
}
