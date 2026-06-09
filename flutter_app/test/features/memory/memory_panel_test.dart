import 'package:executive_assistant/features/memory/memory_panel.dart';
import 'package:executive_assistant/theme/app_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('MemoryPanel', () {
    testWidgets('renders title', (tester) async {
      await tester.pumpWidget(ProviderScope(
        child: MaterialApp(
          theme: AppTheme.dark,
          home: Scaffold(body: SizedBox(width: 300, height: 500, child: const MemoryPanel())),
        ),
      ));
      expect(find.text('Memory'), findsOneWidget);
    });
  });
}
