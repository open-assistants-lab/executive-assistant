import 'package:flutter/material.dart';

@immutable
class EaRadius {
  final double none;
  final double xs;
  final double sm;
  final double md;
  final double lg;
  final double xl;
  final double full;

  const EaRadius({
    required this.none,
    required this.xs,
    required this.sm,
    required this.md,
    required this.lg,
    required this.xl,
    required this.full,
  });

  static const standard = EaRadius(
    none: 0,
    xs: 4,
    sm: 6,
    md: 8,
    lg: 10,
    xl: 12,
    full: 999,
  );

  BorderRadius get xsAll => BorderRadius.circular(xs);
  BorderRadius get smAll => BorderRadius.circular(sm);
  BorderRadius get mdAll => BorderRadius.circular(md);
  BorderRadius get lgAll => BorderRadius.circular(lg);
  BorderRadius get xlAll => BorderRadius.circular(xl);
  BorderRadius get fullAll => BorderRadius.circular(full);
}
