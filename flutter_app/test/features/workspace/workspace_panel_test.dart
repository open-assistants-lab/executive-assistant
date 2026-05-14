import 'package:executive_assistant/features/workspace/workspace_panel.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('refreshes file list without switching workspace', (
    tester,
  ) async {
    var calls = 0;
    Future<List<Map<String, dynamic>>> loadFiles(WidgetRef ref) async {
      calls++;
      if (calls == 1) {
        return [
          {'name': 'old.pdf', 'is_dir': false, 'size': 10},
        ];
      }
      return [
        {'name': 'new.pdf', 'is_dir': false, 'size': 20},
      ];
    }

    await tester.pumpWidget(
      ProviderScope(
        child: MaterialApp(
          home: Scaffold(
            body: WorkspacePanel(
              refreshInterval: const Duration(seconds: 1),
              fileLoader: loadFiles,
            ),
          ),
        ),
      ),
    );
    await tester.pump();

    expect(find.text('old.pdf'), findsOneWidget);

    await tester.pump(const Duration(seconds: 1));
    await tester.pump();

    expect(find.text('new.pdf'), findsOneWidget);
  });
}
