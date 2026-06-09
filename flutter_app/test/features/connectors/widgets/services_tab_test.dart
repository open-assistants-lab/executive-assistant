import 'package:executive_assistant/features/connectors/widgets/services_tab.dart';
import 'package:executive_assistant/theme/app_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('ServicesTab', () {
    testWidgets('shows loading spinner initially', (tester) async {
      await tester.pumpWidget(ProviderScope(
        child: MaterialApp(
          theme: AppTheme.dark,
          home: Scaffold(body: SizedBox(width: 400, height: 600, child: const ServicesTab())),
        ),
      ));
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
    });

    testWidgets('shows All category chip', (tester) async {
      await tester.pumpWidget(ProviderScope(
        child: MaterialApp(
          theme: AppTheme.dark,
          home: Scaffold(body: SizedBox(width: 400, height: 600, child: const ServicesTab())),
        ),
      ));
      expect(find.text('All'), findsOneWidget);
    });
  });
}
