import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:executive_assistant/theme/app_theme.dart';

void main() {
  testWidgets('EaTokens registers on ThemeData for dark mode', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        child: MaterialApp(
          theme: AppTheme.dark,
          home: Builder(builder: (context) {
            final tokens = context.tokens;
            expect(tokens.isDark, true);
            expect(tokens.colors.bgCanvas, const Color(0xFF0A0A0F));
            expect(tokens.colors.accent, const Color(0xFF6C5CE7));
            expect(tokens.typography.textTheme.bodyLarge?.fontSize, 16);
            expect(tokens.spacing.lg, 16);
            expect(tokens.radius.md, 10);
            expect(tokens.motion.snappy, const Duration(milliseconds: 200));
            return const SizedBox();
          }),
        ),
      ),
    );
    await tester.pump();
  });

  testWidgets('EaTokens registers on ThemeData for light mode', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        child: MaterialApp(
          theme: AppTheme.light,
          home: Builder(builder: (context) {
            final tokens = context.tokens;
            expect(tokens.isDark, false);
            expect(tokens.colors.bgCanvas, const Color(0xFFF8F8FA));
            expect(tokens.colors.accent, const Color(0xFF5E4ED6));
            return const SizedBox();
          }),
        ),
      ),
    );
    await tester.pump();
  });

  testWidgets('AppTheme.dark has EaTokens extension registered', (tester) async {
    final theme = AppTheme.dark;
    final tokens = theme.extensions[EaTokens] as EaTokens?;
    expect(tokens, isNotNull);
    expect(tokens!.isDark, true);
  });

  testWidgets('AppTheme.light has EaTokens extension registered', (tester) async {
    final theme = AppTheme.light;
    final tokens = theme.extensions[EaTokens] as EaTokens?;
    expect(tokens, isNotNull);
    expect(tokens!.isDark, false);
  });
}
