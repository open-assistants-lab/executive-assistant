import 'package:flutter/animation.dart';
import 'package:flutter/foundation.dart';

@immutable
class EaMotion {
  // Utility tier — high-frequency UI changes (180ms or less).
  final Duration instant;
  final Duration fast;
  final Duration base;

  // Moment tier — intentional moments deserving delight (280ms).
  final Duration moment;
  final Duration slow;

  // Press-state scale value.
  final double pressScale;

  // Curves.
  final Cubic curveStandard; // default ease-out (Linear's curve)
  final Cubic curveEntrance; // springy entrance
  final Cubic curveExit;     // sharp exit
  final Cubic curveSpring;   // slight overshoot

  const EaMotion({
    required this.instant,
    required this.fast,
    required this.base,
    required this.moment,
    required this.slow,
    required this.pressScale,
    required this.curveStandard,
    required this.curveEntrance,
    required this.curveExit,
    required this.curveSpring,
  });

  static const standard = EaMotion(
    instant: Duration.zero,
    fast: Duration(milliseconds: 120),
    base: Duration(milliseconds: 180),
    moment: Duration(milliseconds: 280),
    slow: Duration(milliseconds: 320),
    pressScale: 0.97,
    curveStandard: Cubic(0.2, 0, 0, 1),
    curveEntrance: Cubic(0.16, 1, 0.3, 1),
    curveExit: Cubic(0.4, 0, 1, 1),
    curveSpring: Cubic(0.34, 1.56, 0.64, 1),
  );

  // Backward-compatibility aliases. Remove once all call sites migrated.
  @Deprecated('Use base instead')
  Duration get snappy => base;
  @Deprecated('Use moment instead')
  Duration get fluid => moment;
  @Deprecated('Use slow instead')
  Duration get intuitive => slow;
  @Deprecated('Use slow instead')
  Duration get graceful => slow;
}
