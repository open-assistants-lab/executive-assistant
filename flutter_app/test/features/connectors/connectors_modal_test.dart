import 'package:executive_assistant/features/connectors/connectors_modal.dart';
import 'package:executive_assistant/theme/app_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  group('ConnectorsModal', () {
    testWidgets('renders title and search field', (tester) async {
      SharedPreferences.setMockInitialValues({});
      await tester.pumpWidget(MaterialApp(
        theme: AppTheme.dark,
        home: Scaffold(body: SizedBox(width: 400, height: 600, child: ConnectorsModal())),
      ));
      expect(find.text('Connection'), findsOneWidget);
      expect(find.byIcon(Symbols.search), findsOneWidget);
    });

    testWidgets('search field updates on typing', (tester) async {
      SharedPreferences.setMockInitialValues({});
      await tester.pumpWidget(MaterialApp(
        theme: AppTheme.dark,
        home: Scaffold(body: SizedBox(width: 400, height: 600, child: ConnectorsModal())),
      ));
      await tester.enterText(find.byType(TextField), 'gmail');
      await tester.pump();
      expect(find.text('Connection'), findsOneWidget);
    });
  });
}
