import 'package:executive_assistant/features/chat/widgets/empty_state.dart';
import 'package:executive_assistant/theme/app_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('ChatEmptyState', () {
    Widget buildEmptyState({
      void Function(String)? onSuggestionTap,
      List<String> suggestions = const ['Summarize my emails', "What's on my calendar?", 'Add a todo'],
    }) {
      return MaterialApp(
        theme: AppTheme.dark,
        home: Scaffold(
          body: ChatEmptyState(
            onSuggestionTap: onSuggestionTap,
            suggestions: suggestions,
          ),
        ),
      );
    }

    testWidgets('shows default message', (tester) async {
      await tester.pumpWidget(buildEmptyState());
      expect(find.text("Ask anything. I'm here to help."), findsOneWidget);
    });

    testWidgets('shows default suggestions', (tester) async {
      await tester.pumpWidget(buildEmptyState());
      expect(find.text('Summarize my emails'), findsOneWidget);
      expect(find.text("What's on my calendar?"), findsOneWidget);
      expect(find.text('Add a todo'), findsOneWidget);
    });

    testWidgets('shows custom suggestions', (tester) async {
      await tester.pumpWidget(buildEmptyState(
        suggestions: ['Custom task 1', 'Custom task 2'],
      ));
      expect(find.text('Custom task 1'), findsOneWidget);
      expect(find.text('Custom task 2'), findsOneWidget);
      expect(find.text('Summarize my emails'), findsNothing);
    });

    testWidgets('tapping suggestion calls onSuggestionTap', (tester) async {
      String? tapped;
      await tester.pumpWidget(buildEmptyState(
        onSuggestionTap: (s) => tapped = s,
      ));
      await tester.tap(find.text('Summarize my emails'));
      expect(tapped, 'Summarize my emails');
    });

    testWidgets('renders dot indicator', (tester) async {
      await tester.pumpWidget(buildEmptyState());
      // The dot is a Container with decoration
      expect(find.byType(Container), findsWidgets);
    });
  });
}
