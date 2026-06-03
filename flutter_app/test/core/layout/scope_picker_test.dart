import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:executive_assistant/widgets/scope_picker.dart';

void main() {
  group('ScopePicker', () {
    testWidgets('shows All ✓, Select, Off segments', (tester) async {
      await tester.pumpWidget(_wrap(
        ScopePicker(
          scope: ScopeState.all,
          onChanged: (_) {},
        ),
      ));
      expect(find.text('All ✓'), findsOneWidget);
      expect(find.text('Select'), findsOneWidget);
      expect(find.text('Off'), findsOneWidget);
    });

    testWidgets('highlights All when scope is all', (tester) async {
      await tester.pumpWidget(_wrap(
        ScopePicker(
          scope: ScopeState.all,
          onChanged: (_) {},
        ),
      ));
      // All should have bold style
      final allText = tester.widget<Text>(find.text('All ✓'));
      expect(allText.style?.fontWeight, FontWeight.w700);
      final offText = tester.widget<Text>(find.text('Off'));
      expect(offText.style?.fontWeight, FontWeight.w400);
    });

    testWidgets('shows count when scope is selected', (tester) async {
      await tester.pumpWidget(_wrap(
        ScopePicker(
          scope: ScopeState.selected,
          selectedWorkspaceIds: ['ws-1', 'ws-2'],
          onChanged: (_) {},
        ),
      ));
      expect(find.text('2 WS'), findsOneWidget);
    });

    testWidgets('tapping All fires onChanged immediately', (tester) async {
      ScopeChange? result;
      await tester.pumpWidget(_wrap(
        ScopePicker(
          scope: ScopeState.none,
          onChanged: (c) => result = c,
        ),
      ));
      await tester.tap(find.text('All ✓'));
      await tester.pumpAndSettle();
      expect(result?.scope, ScopeState.all);
    });

    testWidgets('tapping Off fires onChanged immediately', (tester) async {
      ScopeChange? result;
      await tester.pumpWidget(_wrap(
        ScopePicker(
          scope: ScopeState.all,
          onChanged: (c) => result = c,
        ),
      ));
      await tester.tap(find.text('Off'));
      await tester.pumpAndSettle();
      expect(result?.scope, ScopeState.none);
    });

    testWidgets('tapping Select opens workspace modal', (tester) async {
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
      await tester.tap(find.text('Select'));
      await tester.pumpAndSettle();
      expect(find.text('Select Workspaces'), findsOneWidget);
      expect(find.text('Alpha'), findsOneWidget);
      expect(find.text('Beta'), findsOneWidget);
      expect(find.text('All'), findsOneWidget);
      expect(find.text('None'), findsOneWidget);
      expect(find.text('Apply'), findsOneWidget);
    });

    testWidgets('Select All / Deselect All work in modal', (tester) async {
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
      await tester.tap(find.text('Select'));
      await tester.pumpAndSettle();

      // Select All
      await tester.tap(find.text('All'));
      await tester.pumpAndSettle();
      final checkboxes = tester.widgetList<CheckboxListTile>(find.byType(CheckboxListTile));
      expect(checkboxes.every((c) => c.value == true), isTrue);

      // Deselect All
      await tester.tap(find.text('None'));
      await tester.pumpAndSettle();
      final checkboxes2 = tester.widgetList<CheckboxListTile>(find.byType(CheckboxListTile));
      expect(checkboxes2.every((c) => c.value == false), isTrue);
    });

    testWidgets('applying with zero workspaces switches to none', (tester) async {
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
      await tester.tap(find.text('1 WS'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('None'));
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
