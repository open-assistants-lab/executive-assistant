import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

@immutable
class EaTypography {
  final TextTheme textTheme;
  final TextTheme monoTheme;

  const EaTypography({required this.textTheme, required this.monoTheme});

  factory EaTypography.build(Brightness brightness) {
    final base = brightness == Brightness.dark ? ThemeData.dark().textTheme : ThemeData.light().textTheme;
    final inter = GoogleFonts.interTextTheme(base);
    final firaCode = GoogleFonts.firaCodeTextTheme(base);

    final textColor = brightness == Brightness.dark
        ? const Color(0xFFE6E6E6)
        : const Color(0xFF0E0F11);

    TextStyle s({
      required double size,
      required FontWeight weight,
      required double height,
      double tracking = -0.011,
      Color? color,
    }) {
      return TextStyle(
        fontSize: size,
        fontWeight: weight,
        height: height,
        letterSpacing: size * tracking,
        color: color ?? textColor,
      );
    }

    return EaTypography(
      textTheme: inter.copyWith(
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
      ),
      monoTheme: firaCode.copyWith(
        bodyLarge: firaCode.bodyLarge?.copyWith(fontSize: 13, height: 1.5, color: textColor),
        bodyMedium: firaCode.bodyMedium?.copyWith(fontSize: 12, height: 1.5, color: textColor),
        bodySmall: firaCode.bodySmall?.copyWith(fontSize: 11, height: 1.4, color: textColor),
      ),
    );
  }
}
