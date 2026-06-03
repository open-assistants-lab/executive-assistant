import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:executive_assistant/widgets/scope_picker.dart';

void main() {
  group('ScopePicker', () {
    testWidgets('shows All badge when scope is all', (tester) async {
      await tester.pumpWidget(_wrap(
        ScopePicker(
          scope: ScopeState.all,
          onChanged: (_) {},
        ),
      ));
      expect(find.text('All ✓'), findsOneWidget);
    });

    testWidgets('shows count badge when scope is selected', (tester) async {
      await tester.pumpWidget(_wrap(
        ScopePicker(
          scope: ScopeState.selected,
          selectedWorkspaceIds: ['ws-1', 'ws-2', 'ws-3'],
          onChanged: (_) {},
        ),
      ));
      expect(find.text('3 WS ✓'), findsOneWidget);
    });

    testWidgets('shows Off badge when scope is none', (tester) async {
      await tester.pumpWidget(_wrap(
        ScopePicker(
          scope: ScopeState.none,
          onChanged: (_) {},
        ),
      ));
      expect(find.text('Off'), findsOneWidget);
    });

    testWidgets('tapping badge opens popup menu', (tester) async {
      await tester.pumpWidget(_wrap(
        ScopePicker(
          scope: ScopeState.all,
          onChanged: (_) {},
        ),
      ));
      await tester.tap(find.text('All ✓'));
      await tester.pumpAndSettle();
      expect(find.text('Enable for all workspaces'), findsOneWidget);
      expect(find.text('Enable for selected workspaces…'), findsOneWidget);
      expect(find.text('Disable'), findsOneWidget);
    });

    testWidgets('choosing All from popup fires onChanged', (tester) async {
      ScopeChange? result;
      await tester.pumpWidget(_wrap(
        ScopePicker(
          scope: ScopeState.none,
          onChanged: (c) => result = c,
        ),
      ));
      await tester.tap(find.text('Off'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Enable for all workspaces'));
      await tester.pumpAndSettle();
      expect(result?.scope, ScopeState.all);
    });

    testWidgets('choosing Disable from popup fires onChanged', (tester) async {
      ScopeChange? result;
      await tester.pumpWidget(_wrap(
        ScopePicker(
          scope: ScopeState.all,
          onChanged: (c) => result = c,
        ),
      ));
      await tester.tap(find.text('All ✓'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Disable'));
      await tester.pumpAndSettle();
      expect(result?.scope, ScopeState.none);
    });

    testWidgets('choosing Selected opens workspace modal', (tester) async {
      await tester.pumpWidget(_wrap(
        ScopePicker(
          scope: ScopeState.all,
          selectedWorkspaceIds: [],
          allWorkspaces: [
            {'id': 'ws-1', 'name': 'Alpha'},
            {'id': 'ws-2', 'name': 'Beta'},
          ],
          onChanged: (_) {},
        ),
      ));
      await tester.tap(find.text('All ✓'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Enable for selected workspaces…'));
      await tester.pumpAndSettle();
      expect(find.text('Select Workspaces'), findsOneWidget);
      expect(find.text('Alpha'), findsOneWidget);
      expect(find.text('Beta'), findsOneWidget);
      expect(find.text('Apply'), findsOneWidget);
    });

    testWidgets('workspace modal applies selected ids', (tester) async {
      ScopeChange? result;
      await tester.pumpWidget(_wrap(
        ScopePicker(
          scope: ScopeState.all,
          selectedWorkspaceIds: [],
          allWorkspaces: [
            {'id': 'ws-1', 'name': 'Alpha'},
            {'id': 'ws-2', 'name': 'Beta'},
          ],
          onChanged: (c) => result = c,
        ),
      ));
      await tester.tap(find.text('All ✓'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Enable for selected workspaces…'));
      await tester.pumpAndSettle();

      await tester.tap(find.byType(CheckboxListTile).first);
      await tester.pumpAndSettle();
      await tester.tap(find.text('Apply'));
      await tester.pumpAndSettle();

      expect(result?.scope, ScopeState.selected);
      expect(result?.workspaceIds, ['ws-1']);
    });

    testWidgets('selecting zero workspaces switches to none', (tester) async {
      ScopeChange? result;
      await tester.pumpWidget(_wrap(
        ScopePicker(
          scope: ScopeState.selected,
          selectedWorkspaceIds: ['ws-1'],
          allWorkspaces: [
            {'id': 'ws-1', 'name': 'Alpha'},
          ],
          onChanged: (c) => result = c,
        ),
      ));
      await tester.tap(find.text('1 WS ✓'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Enable for selected workspaces (1)…'));
      await tester.pumpAndSettle();

      await tester.tap(find.byType(CheckboxListTile).first);
      await tester.pumpAndSettle();
      await tester.tap(find.text('Apply'));
      await tester.pumpAndSettle();

      expect(result?.scope, ScopeState.none);
      expect(result?.workspaceIds, isEmpty);
    });
  });
}

Widget _wrap(Widget child) {
  return MaterialApp(
    home: Scaffold(body: Center(child: child)),
  );
}
