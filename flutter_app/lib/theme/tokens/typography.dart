import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

@immutable
class EaTypography {
  final TextTheme textTheme;
  final TextTheme monoTheme;

  const EaTypography({
    required this.textTheme,
    required this.monoTheme,
  });

  factory EaTypography.build(Brightness brightness) {
    final inter = GoogleFonts.interTextTheme();
    final firaCode = GoogleFonts.firaCodeTextTheme();
    return EaTypography(
      textTheme: inter.copyWith(
        displayLarge: inter.displayLarge?.copyWith(
          fontSize: 32, fontWeight: FontWeight.w600, height: 1.2, letterSpacing: -0.5,
        ),
        headlineLarge: inter.headlineLarge?.copyWith(
          fontSize: 24, fontWeight: FontWeight.w600, height: 1.3, letterSpacing: -0.3,
        ),
        headlineMedium: inter.headlineMedium?.copyWith(
          fontSize: 18, fontWeight: FontWeight.w600, height: 1.3, letterSpacing: -0.2,
        ),
        bodyLarge: inter.bodyLarge?.copyWith(
          fontSize: 16, fontWeight: FontWeight.w400, height: 1.5,
        ),
        bodyMedium: inter.bodyMedium?.copyWith(
          fontSize: 14, fontWeight: FontWeight.w400, height: 1.5,
        ),
        bodySmall: inter.bodySmall?.copyWith(
          fontSize: 13, fontWeight: FontWeight.w400, height: 1.4, letterSpacing: 0.1,
        ),
        labelSmall: inter.labelSmall?.copyWith(
          fontSize: 11, fontWeight: FontWeight.w500, height: 1.3, letterSpacing: 0.2,
        ),
      ),
      monoTheme: firaCode.copyWith(
        bodyLarge: firaCode.bodyLarge?.copyWith(
          fontSize: 14, fontWeight: FontWeight.w400, height: 1.6,
        ),
        bodyMedium: firaCode.bodyMedium?.copyWith(
          fontSize: 13, fontWeight: FontWeight.w400, height: 1.5,
        ),
        bodySmall: firaCode.bodySmall?.copyWith(
          fontSize: 11, fontWeight: FontWeight.w400, height: 1.4,
        ),
      ),
    );
  }
}
