import 'package:flutter/animation.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:executive_assistant/theme/tokens/motion.dart';

void main() {
  group('EaMotion.standard', () {
    test('utility tier durations', () {
      expect(EaMotion.standard.fast, const Duration(milliseconds: 120));
      expect(EaMotion.standard.base, const Duration(milliseconds: 180));
    });

    test('moment tier duration', () {
      expect(EaMotion.standard.moment, const Duration(milliseconds: 280));
    });

    test('press scale value', () {
      expect(EaMotion.standard.pressScale, closeTo(0.97, 0.001));
    });

    test('curves are defined as Cubic', () {
      expect(EaMotion.standard.curveStandard, isA<Cubic>());
      expect(EaMotion.standard.curveEntrance, isA<Cubic>());
      expect(EaMotion.standard.curveExit, isA<Cubic>());
      expect(EaMotion.standard.curveSpring, isA<Cubic>());
    });
  });
}
