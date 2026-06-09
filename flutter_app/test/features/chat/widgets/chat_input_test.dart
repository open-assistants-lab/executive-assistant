import 'package:executive_assistant/features/chat/widgets/chat_input.dart';
import 'package:executive_assistant/theme/app_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  group('ChatInput', () {
    testWidgets('renders text field when connected', (tester) async {
      SharedPreferences.setMockInitialValues({});
      await tester.pumpWidget(ProviderScope(
        child: MaterialApp(
          theme: AppTheme.dark,
          home: Scaffold(body: SizedBox(width: 400, height: 200, child: const ChatInput())),
        ),
      ));
      await tester.pump();
      expect(find.byType(ChatInput), findsOneWidget);
    });

    testWidgets('renders without crashing', (tester) async {
      SharedPreferences.setMockInitialValues({});
      await tester.pumpWidget(ProviderScope(
        child: MaterialApp(
          theme: AppTheme.dark,
          home: Scaffold(body: SizedBox(width: 400, height: 200, child: const ChatInput())),
        ),
      ));
      await tester.pump();
      expect(find.byType(ChatInput), findsOneWidget);
    });
  });
}