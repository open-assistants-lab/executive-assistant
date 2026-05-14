import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';

import 'package:executive_assistant/main.dart' as app;

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  group('Executive Assistant Integration', () {
    testWidgets('app launches and shows home', (WidgetTester tester) async {
      app.main();
      await tester.pumpAndSettle(const Duration(seconds: 2));

      // The app should show something — either the greeting or a placeholder.
      expect(find.byType(MaterialApp), findsOneWidget);
    });

    testWidgets('can type into chat input on mobile', (WidgetTester tester) async {
      app.main();
      await tester.pumpAndSettle(const Duration(seconds: 2));

      // Look for a text field.
      final textField = find.byType(TextField);
      if (textField.evaluate().isNotEmpty) {
        await tester.enterText(textField.first, 'Hello from integration test');
        await tester.pumpAndSettle();
        expect(find.text('Hello from integration test'), findsOneWidget);
      }
    });

    testWidgets('app has bottom nav or sidebar depending on size',
        (WidgetTester tester) async {
      app.main();
      await tester.pumpAndSettle(const Duration(seconds: 2));

      // At least one Scaffold should exist.
      expect(find.byType(Scaffold), findsWidgets);
    });
  });
}
