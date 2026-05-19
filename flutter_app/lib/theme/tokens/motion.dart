import 'package:flutter/foundation.dart';

@immutable
class EaMotion {
  final Duration snappy;
  final Duration fluid;
  final Duration intuitive;
  final Duration instant;
  final Duration graceful;

  const EaMotion({
    required this.snappy,
    required this.fluid,
    required this.intuitive,
    required this.instant,
    required this.graceful,
  });

  static const standard = EaMotion(
    snappy: Duration(milliseconds: 200),
    fluid: Duration(milliseconds: 300),
    intuitive: Duration(milliseconds: 400),
    instant: Duration(milliseconds: 100),
    graceful: Duration(milliseconds: 600),
  );
}
