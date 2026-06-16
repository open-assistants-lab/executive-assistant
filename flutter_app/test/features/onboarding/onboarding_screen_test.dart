import 'package:executive_assistant/features/onboarding/onboarding_screen.dart';
import 'package:executive_assistant/theme/app_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

Widget _buildOnboardingScreen({List<Map<String, dynamic>>? initialProviders}) {
  return ProviderScope(
    child: MaterialApp(
      theme: AppTheme.dark,
      home: OnboardingScreen(initialProviders: initialProviders),
    ),
  );
}

void main() {
  group('OnboardingScreen', () {
    testWidgets('shows loading spinner initially', (tester) async {
      SharedPreferences.setMockInitialValues({});
      await tester.pumpWidget(_buildOnboardingScreen());
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
    });

    testWidgets('renders scaffold with correct background', (tester) async {
      SharedPreferences.setMockInitialValues({});
      await tester.pumpWidget(_buildOnboardingScreen());
      expect(find.byType(Scaffold), findsOneWidget);
    });

    testWidgets('enables Test and Get Started after typing API key', (
      tester,
    ) async {
      SharedPreferences.setMockInitialValues({});
      await tester.pumpWidget(
        _buildOnboardingScreen(
          initialProviders: const [
            {
              'id': 'deepseek',
              'name': 'DeepSeek',
              'models': ['deepseek-v4-flash'],
            },
          ],
        ),
      );

      await tester.tap(find.text('DeepSeek'));
      await tester.pump();
      await tester.tap(find.text('Next'));
      await tester.pump();
      await tester.enterText(find.byType(TextField), 'sk-deepseek-test');
      await tester.pump();

      final testButton = tester.widget<OutlinedButton>(
        find.widgetWithText(OutlinedButton, 'Test'),
      );
      final getStartedButton = tester.widget<FilledButton>(
        find.widgetWithText(FilledButton, 'Get Started'),
      );

      expect(testButton.onPressed, isNotNull);
      expect(getStartedButton.onPressed, isNotNull);
    });
  });
}
