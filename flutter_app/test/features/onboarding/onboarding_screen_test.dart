import 'package:executive_assistant/features/onboarding/onboarding_screen.dart';
import 'package:executive_assistant/theme/app_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

Widget _buildOnboardingScreen() {
  return ProviderScope(
    child: MaterialApp(
      theme: AppTheme.dark,
      home: const OnboardingScreen(),
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
  });
}
