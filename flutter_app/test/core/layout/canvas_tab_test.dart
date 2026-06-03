import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:executive_assistant/features/workspace/canvas_tab.dart';
import 'package:executive_assistant/theme/app_theme.dart';

void main() {
  group('CanvasTab', () {
    testWidgets('shows empty state when no surfaces', (tester) async {
      await tester.pumpWidget(_wrap(const CanvasTab()));
      await tester.pump();
      expect(find.text('Agent-generated content appears here'), findsOneWidget);
    });
  });
}

Widget _wrap(Widget child) {
  return ProviderScope(
    child: MaterialApp(
      theme: AppTheme.dark,
      home: Scaffold(body: child),
    ),
  );
}
