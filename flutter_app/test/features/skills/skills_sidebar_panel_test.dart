import 'package:executive_assistant/features/skills/skills_sidebar_panel.dart';
import 'package:executive_assistant/theme/app_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('SkillsSidebarPanel', () {
    testWidgets('renders title', (tester) async {
      await tester.pumpWidget(ProviderScope(
        child: MaterialApp(
          theme: AppTheme.dark,
          home: Scaffold(body: SizedBox(width: 300, height: 500, child: const SkillsSidebarPanel())),
        ),
      ));
      expect(find.text('Skills'), findsOneWidget);
    });
  });
}
