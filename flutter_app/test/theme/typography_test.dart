import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:executive_assistant/theme/tokens/typography.dart';

void main() {
  // Three pieces of test infrastructure are all required to test a
  // GoogleFonts-backed TextTheme without bundling .ttf assets:
  //
  // 1. `ensureInitialized()` — GoogleFonts touches ServicesBinding.instance
  //    when constructing a TextTheme, which requires a binding.
  // 2. `allowRuntimeFetching = false` — prevents an HTTP fetch that would
  //    otherwise throw "There is no current invoker" outside a test zone.
  // 3. `runIgnoringFontErrors` — with fetching disabled, google_fonts still
  //    schedules an unawaited Future that throws "asset not found" after the
  //    assertions complete, tripping the "test failed after it had already
  //    completed" guard. We swallow only that specific error. The TextStyle
  //    merge values we assert on (size/weight/height/letterSpacing/fontFamily)
  //    are applied synchronously before any font load is attempted, so this
  //    is safe.
  //
  // If Inter/Fira Code are ever bundled as local assets, all three can go.
  TestWidgetsFlutterBinding.ensureInitialized();
  GoogleFonts.config.allowRuntimeFetching = false;

  Future<void> runIgnoringFontErrors(FutureOr<void> Function() body) {
    final completer = Completer<void>();
    runZonedGuarded(() async {
      try {
        await body();
        if (!completer.isCompleted) completer.complete();
      } catch (e, st) {
        if (!completer.isCompleted) completer.completeError(e, st);
      }
    }, (error, stack) {
      if (error is Exception &&
          error.toString().contains(
            'GoogleFonts.config.allowRuntimeFetching',
          )) {
        return;
      }
      if (!completer.isCompleted) completer.completeError(error, stack);
    });
    return completer.future;
  }

  group('EaTypography', () {
    test('bodyLarge is 14px with tight letter-spacing', () async {
      await runIgnoringFontErrors(() {
        final typo = EaTypography.build(Brightness.dark);
        final style = typo.textTheme.bodyLarge!;
        expect(style.fontSize, 14);
        expect(style.fontWeight, FontWeight.w400);
        expect(style.height, closeTo(1.6, 0.01));
        expect(style.letterSpacing, closeTo(-0.011 * 14, 0.05));
      });
    });

    test('labelSmall is 10px uppercase-ready with 0.1em tracking', () async {
      await runIgnoringFontErrors(() {
        final typo = EaTypography.build(Brightness.dark);
        final style = typo.textTheme.labelSmall!;
        expect(style.fontSize, 10);
        expect(style.fontWeight, FontWeight.w600);
        expect(style.letterSpacing, closeTo(0.1 * 10, 0.05));
      });
    });

    test('titleLarge is 17px semibold', () async {
      await runIgnoringFontErrors(() {
        final typo = EaTypography.build(Brightness.dark);
        final style = typo.textTheme.titleLarge!;
        expect(style.fontSize, 17);
        expect(style.fontWeight, FontWeight.w600);
      });
    });

    test('bodyMedium is 13px with tight letter-spacing', () async {
      await runIgnoringFontErrors(() {
        final typo = EaTypography.build(Brightness.dark);
        final style = typo.textTheme.bodyMedium!;
        expect(style.fontSize, 13);
        expect(style.fontWeight, FontWeight.w400);
        expect(style.letterSpacing, closeTo(-0.005 * 13, 0.05));
      });
    });

    test('labelMedium is 11px semibold with 0.04em tracking', () async {
      await runIgnoringFontErrors(() {
        final typo = EaTypography.build(Brightness.dark);
        final style = typo.textTheme.labelMedium!;
        expect(style.fontSize, 11);
        expect(style.fontWeight, FontWeight.w600);
        expect(style.letterSpacing, closeTo(0.04 * 11, 0.05));
      });
    });

    test('uses Inter font family', () async {
      await runIgnoringFontErrors(() {
        final typo = EaTypography.build(Brightness.dark);
        final style = typo.textTheme.bodyLarge!;
        expect(style.fontFamily, contains('Inter'));
      });
    });
  });
}
