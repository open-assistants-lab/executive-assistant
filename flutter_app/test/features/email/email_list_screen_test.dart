import 'package:executive_assistant/features/email/email_list_screen.dart';
import 'package:executive_assistant/theme/app_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('EmailListScreen', () {
    testWidgets('renders title', (tester) async {
      await tester.pumpWidget(ProviderScope(
        child: MaterialApp(
          theme: AppTheme.dark,
          home: Scaffold(body: SizedBox(width: 400, height: 600, child: const EmailListScreen())),
        ),
      ));
      expect(find.text('Email'), findsOneWidget);
    });
  });
}
