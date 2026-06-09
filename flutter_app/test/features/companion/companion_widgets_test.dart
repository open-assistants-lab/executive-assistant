import 'package:executive_assistant/features/companion/companion_pulse.dart';
import 'package:executive_assistant/features/companion/companion_feed.dart';
import 'package:executive_assistant/features/companion/companion_toast.dart';
import 'package:executive_assistant/features/companion/companion_context_pill.dart';
import 'package:executive_assistant/theme/app_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('CompanionPulse', () {
    testWidgets('renders pulse indicator', (tester) async {
      await tester.pumpWidget(ProviderScope(
        child: MaterialApp(
          theme: AppTheme.dark,
          home: const Scaffold(body: CompanionPulse()),
        ),
      ));
      expect(find.byType(CompanionPulse), findsOneWidget);
    });
  });

  group('CompanionFeed', () {
    testWidgets('renders feed', (tester) async {
      await tester.pumpWidget(ProviderScope(
        child: MaterialApp(
          theme: AppTheme.dark,
          home: Scaffold(body: SizedBox(width: 500, height: 500, child: const CompanionFeed())),
        ),
      ));
      expect(find.byType(CompanionFeed), findsOneWidget);
    });
  });

  group('CompanionToastOverlay', () {
    testWidgets('renders toast overlay', (tester) async {
      await tester.pumpWidget(ProviderScope(
        child: MaterialApp(
          theme: AppTheme.dark,
          home: const Scaffold(body: CompanionToastOverlay()),
        ),
      ));
      expect(find.byType(CompanionToastOverlay), findsOneWidget);
    });
  });

  group('CompanionContextPill', () {
    testWidgets('renders context pill', (tester) async {
      await tester.pumpWidget(ProviderScope(
        child: MaterialApp(
          theme: AppTheme.dark,
          home: Scaffold(body: CompanionContextPill(activeWorkspaceId: 'personal')),
        ),
      ));
      expect(find.byType(CompanionContextPill), findsOneWidget);
    });
  });
}
