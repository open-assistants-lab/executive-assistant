import 'package:executive_assistant/features/connectors/widgets/provider_card.dart';
import 'package:executive_assistant/models/provider_model.dart';
import 'package:executive_assistant/theme/app_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  group('ProviderCard', () {
    Widget buildCard({
      String providerId = 'openai',
      String providerName = 'OpenAI',
      bool hasKey = false,
      List<ProviderModel> models = const [],
      String? selectedModel,
    }) {
      return ProviderScope(
        child: MaterialApp(
          theme: AppTheme.dark,
          home: Scaffold(
            body: ProviderCard(
              providerId: providerId,
              providerName: providerName,
              hasKey: hasKey,
              models: models,
              selectedModel: selectedModel,
            ),
          ),
        ),
      );
    }

    testWidgets('shows provider name', (tester) async {
      SharedPreferences.setMockInitialValues({});
      await tester.pumpWidget(buildCard());
      expect(find.text('OpenAI'), findsOneWidget);
    });

    testWidgets('shows configured status when hasKey', (tester) async {
      SharedPreferences.setMockInitialValues({});
      await tester.pumpWidget(buildCard(hasKey: true));
      expect(find.text('🔑 Configured'), findsOneWidget);
    });

    testWidgets('shows needs key status when no key', (tester) async {
      SharedPreferences.setMockInitialValues({});
      await tester.pumpWidget(buildCard(hasKey: false));
      expect(find.text('⚠️ Needs API key'), findsOneWidget);
    });

    testWidgets('expands on tap', (tester) async {
      SharedPreferences.setMockInitialValues({});
      await tester.pumpWidget(buildCard());
      expect(find.byType(TextField), findsNothing);
      await tester.tap(find.text('OpenAI'));
      await tester.pump();
      expect(find.byType(TextField), findsOneWidget);
    });

    testWidgets('shows save button when no key', (tester) async {
      SharedPreferences.setMockInitialValues({});
      await tester.pumpWidget(buildCard());
      await tester.tap(find.text('OpenAI'));
      await tester.pump();
      expect(find.text('Save'), findsOneWidget);
    });

    testWidgets('shows change button when has key', (tester) async {
      SharedPreferences.setMockInitialValues({});
      await tester.pumpWidget(buildCard(hasKey: true));
      await tester.tap(find.text('OpenAI'));
      await tester.pump();
      expect(find.text('Change'), findsOneWidget);
    });

    testWidgets('test button disabled when key field empty', (tester) async {
      SharedPreferences.setMockInitialValues({});
      await tester.pumpWidget(buildCard());
      await tester.tap(find.text('OpenAI'));
      await tester.pump();
      final testBtn = find.widgetWithText(OutlinedButton, 'Test');
      expect(tester.widget<OutlinedButton>(testBtn).onPressed, isNull);
    });

    testWidgets('test button enabled when key has text', (tester) async {
      SharedPreferences.setMockInitialValues({});
      await tester.pumpWidget(buildCard());
      await tester.tap(find.text('OpenAI'));
      await tester.pump();
      await tester.enterText(find.byType(TextField), 'sk-test');
      await tester.pumpAndSettle();
      final testBtn = find.widgetWithText(OutlinedButton, 'Test');
      expect(tester.widget<OutlinedButton>(testBtn).onPressed, isNotNull);
      // Button should be tappable (not null)
      await tester.tap(testBtn);
      await tester.pump();
      // After tapping, should show error or result
      expect(find.byType(OutlinedButton), findsWidgets);
    });

    testWidgets('shows no models message when empty', (tester) async {
      SharedPreferences.setMockInitialValues({});
      await tester.pumpWidget(buildCard());
      await tester.tap(find.text('OpenAI'));
      await tester.pump();
      expect(find.text('No models found for this provider.'), findsOneWidget);
    });

    testWidgets('shows model list when models exist', (tester) async {
      SharedPreferences.setMockInitialValues({});
      await tester.pumpWidget(
        buildCard(
          models: [
            (id: 'gpt-4', name: 'GPT-4'),
            (id: 'gpt-3.5', name: 'GPT-3.5'),
          ],
        ),
      );
      await tester.tap(find.text('OpenAI'));
      await tester.pump();
      expect(find.text('GPT-4'), findsOneWidget);
      expect(find.text('GPT-3.5'), findsOneWidget);
    });
  });
}
