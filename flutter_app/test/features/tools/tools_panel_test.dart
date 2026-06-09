import 'package:executive_assistant/features/tools/tools_panel.dart';
import 'package:executive_assistant/theme/app_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  group('ToolsPanel', () {
    testWidgets('shows title and search', (tester) async {
      SharedPreferences.setMockInitialValues({});
      await tester.pumpWidget(ProviderScope(
        child: MaterialApp(
          theme: AppTheme.dark,
          home: Scaffold(body: SizedBox(width: 400, height: 600, child: const ToolsPanel())),
        ),
      ));
      await tester.pump();
      expect(find.text('Tools'), findsOneWidget);
      expect(find.byIcon(Symbols.search), findsOneWidget);
    });
  });
}
