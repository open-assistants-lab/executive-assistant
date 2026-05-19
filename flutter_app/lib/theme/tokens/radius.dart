import 'package:flutter/material.dart';

@immutable
class EaRadius {
  final double sm;
  final double md;
  final double lg;
  final double xl;

  const EaRadius({required this.sm, required this.md, required this.lg, required this.xl});

  static const standard = EaRadius(sm: 6, md: 10, lg: 14, xl: 20);

  BorderRadius get smAll => BorderRadius.circular(sm);
  BorderRadius get mdAll => BorderRadius.circular(md);
  BorderRadius get lgAll => BorderRadius.circular(lg);
  BorderRadius get xlAll => BorderRadius.circular(xl);
}
