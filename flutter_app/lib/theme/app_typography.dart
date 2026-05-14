import 'package:flutter/material.dart';

class AppTypography {
  AppTypography._();

  static const String fontFamily = 'Inter';

  // ── MD3 Type Scale ──
  // displayLarge  57/64 · w400 · -0.25
  // displayMedium 45/52 · w400 · 0
  // displaySmall  36/44 · w400 · 0
  // headlineLarge 32/40 · w400 · 0
  // headlineMedium 28/36 · w400 · 0
  // headlineSmall 24/32 · w400 · 0
  // titleLarge    22/28 · w400 · 0
  // titleMedium   16/24 · w500 · 0.15
  // titleSmall    14/20 · w500 · 0.1
  // bodyLarge     16/24 · w400 · 0.5
  // bodyMedium    14/20 · w400 · 0.25
  // bodySmall     12/16 · w400 · 0.4
  // labelLarge    14/20 · w500 · 0.1
  // labelMedium   12/16 · w500 · 0.5
  // labelSmall    11/16 · w500 · 0.5

  // MD3 headlineLarge: 32px (used for screen titles)
  static const TextStyle screenTitle = TextStyle(
    fontFamily: fontFamily, fontSize: 32, fontWeight: FontWeight.w400,
    height: 1.25, letterSpacing: 0,
  );

  // MD3 headlineMedium: 28px (used for section titles)
  static const TextStyle sectionTitle = TextStyle(
    fontFamily: fontFamily, fontSize: 28, fontWeight: FontWeight.w400,
    height: 1.28, letterSpacing: 0,
  );

  // MD3 bodyLarge: 16px (primary body text)
  static const TextStyle body = TextStyle(
    fontFamily: fontFamily, fontSize: 16, fontWeight: FontWeight.w400,
    height: 1.5, letterSpacing: 0.5,
  );

  // MD3 bodySmall: 12px (captions)
  static const TextStyle caption = TextStyle(
    fontFamily: fontFamily, fontSize: 12, fontWeight: FontWeight.w400,
    height: 1.33, letterSpacing: 0.4,
  );

  // MD3 labelMedium: 12px (tool labels, chips)
  static const TextStyle toolLabel = TextStyle(
    fontFamily: fontFamily, fontSize: 12, fontWeight: FontWeight.w500,
    height: 1.33, letterSpacing: 0.5,
  );

  // MD3 headlineSmall: 24px (metrics)
  static const TextStyle metric = TextStyle(
    fontFamily: fontFamily, fontSize: 24, fontWeight: FontWeight.w400,
    height: 1.33, letterSpacing: 0,
  );

  // MD3 labelLarge: 14px (buttons)
  static const TextStyle button = TextStyle(
    fontFamily: fontFamily, fontSize: 14, fontWeight: FontWeight.w500,
    height: 1.43, letterSpacing: 0.1,
  );

  // MD3 labelSmall: 11px (chips, small labels)
  static const TextStyle chip = TextStyle(
    fontFamily: fontFamily, fontSize: 11, fontWeight: FontWeight.w500,
    height: 1.45, letterSpacing: 0.5,
  );
}