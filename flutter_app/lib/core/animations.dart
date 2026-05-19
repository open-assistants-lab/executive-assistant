import 'package:flutter/material.dart';

class EaAnimations {
  static Widget staggeredEntry({
    required int index,
    required Widget child,
    Duration delayPerItem = const Duration(milliseconds: 50),
  }) {
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0.0, end: 1.0),
      duration: const Duration(milliseconds: 300),
      curve: Curves.easeOutCubic,
      builder: (context, value, c) {
        return Opacity(
          opacity: value,
          child: Transform.translate(
            offset: Offset(0, (1 - value) * 20),
            child: c,
          ),
        );
      },
      child: child,
    );
  }
}
