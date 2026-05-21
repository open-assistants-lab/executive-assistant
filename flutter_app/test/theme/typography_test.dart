import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:executive_assistant/theme/tokens/typography.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  // Prevent google_fonts from attempting a network fetch during tests.
  GoogleFonts.config.allowRuntimeFetching = false;

  /// Runs [body] in an error-tolerant zone so google_fonts' deferred
  /// "asset not found" errors don't fail the test. The TextStyle merge
  /// values we care about (size/weight/height/letterSpacing) are applied
  /// synchronously before the font load is even attempted.
  Future<void> runIgnoringFontErrors(Future<void> Function() body) {
    final completer = Completer<void>();
    runZonedGuarded(() async {
      try {
        await body();
        if (!completer.isCompleted) completer.complete();
      } catch (e, st) {
        if (!completer.isCompleted) completer.completeError(e, st);
      }
    }, (error, stack) {
      // Swallow google_fonts deferred load errors.
      if (error is Exception &&
          error.toString().contains('GoogleFonts.config.allowRuntimeFetching')) {
        return;
      }
      if (!completer.isCompleted) completer.completeError(error, stack);
    });
    return completer.future;
  }

  group('EaTypography', () {
    test('bodyLarge is 14px with tight letter-spacing', () async {
      await runIgnoringFontErrors(() async {
        final typo = EaTypography.build(Brightness.dark);
        final style = typo.textTheme.bodyLarge!;
        expect(style.fontSize, 14);
        expect(style.fontWeight, FontWeight.w400);
        expect(style.height, closeTo(1.6, 0.01));
        expect(style.letterSpacing, closeTo(-0.011 * 14, 0.05));
      });
    });

    test('labelSmall is 10px uppercase-ready with 0.1em tracking', () async {
      await runIgnoringFontErrors(() async {
        final typo = EaTypography.build(Brightness.dark);
        final style = typo.textTheme.labelSmall!;
        expect(style.fontSize, 10);
        expect(style.fontWeight, FontWeight.w600);
        expect(style.letterSpacing, closeTo(0.1 * 10, 0.05));
      });
    });

    test('titleLarge is 17px semibold', () async {
      await runIgnoringFontErrors(() async {
        final typo = EaTypography.build(Brightness.dark);
        final style = typo.textTheme.titleLarge!;
        expect(style.fontSize, 17);
        expect(style.fontWeight, FontWeight.w600);
      });
    });
  });
}
