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

    // Linear-style tracking: -0.011em on body, tighter on display, looser on tiny labels.
    TextStyle s({required double size, required FontWeight weight, required double height, double tracking = -0.011}) {
      return TextStyle(
        fontSize: size,
        fontWeight: weight,
        height: height,
        letterSpacing: size * tracking,
      );
    }

    final base = inter.copyWith(
      displayLarge: inter.displayLarge?.merge(s(size: 28, weight: FontWeight.w600, height: 1.2, tracking: -0.02)),
      displayMedium: inter.displayMedium?.merge(s(size: 22, weight: FontWeight.w600, height: 1.25, tracking: -0.015)),
      titleLarge: inter.titleLarge?.merge(s(size: 17, weight: FontWeight.w600, height: 1.3, tracking: -0.012)),
      titleMedium: inter.titleMedium?.merge(s(size: 15, weight: FontWeight.w500, height: 1.4)),
      titleSmall: inter.titleSmall?.merge(s(size: 13, weight: FontWeight.w500, height: 1.4, tracking: -0.005)),
      bodyLarge: inter.bodyLarge?.merge(s(size: 14, weight: FontWeight.w400, height: 1.6)),
      bodyMedium: inter.bodyMedium?.merge(s(size: 13, weight: FontWeight.w400, height: 1.55, tracking: -0.005)),
      bodySmall: inter.bodySmall?.merge(s(size: 12, weight: FontWeight.w400, height: 1.5, tracking: 0)),
      labelLarge: inter.labelLarge?.merge(s(size: 13, weight: FontWeight.w500, height: 1.4, tracking: -0.005)),
      labelMedium: inter.labelMedium?.merge(s(size: 11, weight: FontWeight.w600, height: 1.3, tracking: 0.04)),
      labelSmall: inter.labelSmall?.merge(s(size: 10, weight: FontWeight.w600, height: 1.3, tracking: 0.1)),
    );

    return EaTypography(
      textTheme: base,
      monoTheme: firaCode.copyWith(
        bodyLarge: firaCode.bodyLarge?.copyWith(fontSize: 13, height: 1.5),
        bodyMedium: firaCode.bodyMedium?.copyWith(fontSize: 12, height: 1.5),
        bodySmall: firaCode.bodySmall?.copyWith(fontSize: 11, height: 1.4),
      ),
    );
  }
}
