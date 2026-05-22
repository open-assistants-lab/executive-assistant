import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:executive_assistant/theme/tokens/colors.dart';

void main() {
  group('EaColors.dark', () {
    test('uses near-black canvas', () {
      expect(EaColors.dark.bgCanvas, const Color(0xFF08090A));
    });
    test('uses deep emerald accent', () {
      expect(EaColors.dark.accent, const Color(0xFF239766));
      expect(EaColors.dark.accentHover, const Color(0xFF2EAD78));
      expect(EaColors.dark.accentMuted, const Color(0xFF0D2B22));
    });
    test('borderAccent is emerald at ~40% opacity', () {
      expect(EaColors.dark.borderAccent.r, closeTo(0x23 / 255, 0.01));
      expect(EaColors.dark.borderAccent.a, closeTo(0.4, 0.05));
    });
    test('text colors set for AA contrast', () {
      expect(EaColors.dark.textPrimary, const Color(0xFFE6E6E6));
    });
  });

  group('EaColors.light', () {
    test('uses off-white canvas', () {
      expect(EaColors.light.bgCanvas, const Color(0xFFFAFAFA));
    });
    test('uses darker emerald for AA contrast on white', () {
      expect(EaColors.light.accent, const Color(0xFF1B7A52));
    });
  });
}
