import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:executive_assistant/theme/app_theme.dart';
import 'package:executive_assistant/features/workspace/canvas_tab.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  group('Canvas Tab', () {
    testWidgets('renders without crashing', (tester) async {
      SharedPreferences.setMockInitialValues({});
      await tester.pumpWidget(ProviderScope(
        child: MaterialApp(
          theme: AppTheme.dark,
          home: Scaffold(
            body: SizedBox(width: 800, height: 600, child: const CanvasTab()),
          ),
        ),
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 500));
      expect(find.byType(CanvasTab), findsOneWidget);
    });

    testWidgets('shows empty state message', (tester) async {
      SharedPreferences.setMockInitialValues({});
      await tester.pumpWidget(ProviderScope(
        child: MaterialApp(
          theme: AppTheme.dark,
          home: Scaffold(
            body: SizedBox(width: 800, height: 600, child: const CanvasTab()),
          ),
        ),
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 500));
      expect(
        find.text('Agent-generated content appears here'),
        findsOneWidget,
      );
    });
  });
}