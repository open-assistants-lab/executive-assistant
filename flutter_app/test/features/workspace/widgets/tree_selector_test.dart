import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:executive_assistant/theme/app_theme.dart';
import 'package:executive_assistant/features/workspace/widgets/tree_selector.dart';

void main() {
  const testGroups = [
    TreeSelectorGroup<String>(
      label: 'email',
      items: [
        TreeSelectorItem(label: 'send', value: 'email_send'),
        TreeSelectorItem(label: 'list', value: 'email_list'),
      ],
    ),
    TreeSelectorGroup<String>(
      label: 'files',
      items: [
        TreeSelectorItem(label: 'read', value: 'files_read'),
        TreeSelectorItem(label: 'write', value: 'files_write'),
      ],
    ),
  ];

  Widget buildTestApp({
    Set<String> selected = const {},
    TreeSelectionMode mode = TreeSelectionMode.multi,
  }) {
    return MaterialApp(
      theme: AppTheme.dark,
      home: Scaffold(
        body: GroupedTreeSelector<String>(
          groups: testGroups,
          selected: selected,
          onChanged: (_) {},
          mode: mode,
        ),
      ),
    );
  }

  testWidgets('renders search field and group headers', (tester) async {
    await tester.pumpWidget(buildTestApp());
    expect(find.byType(TextField), findsOneWidget);
    expect(find.text('email'), findsOneWidget);
    expect(find.text('files'), findsOneWidget);
    expect(find.text('0/2'), findsNWidgets(2));
  });

  testWidgets('search filters groups by label', (tester) async {
    await tester.pumpWidget(buildTestApp());
    await tester.enterText(find.byType(TextField), 'email');
    await tester.pump();
    expect(find.text('files'), findsNothing);
  });

  testWidgets('search filters group items', (tester) async {
    await tester.pumpWidget(buildTestApp());
    await tester.enterText(find.byType(TextField), 'read');
    await tester.pump();
    expect(find.text('files'), findsOneWidget);
    expect(find.text('email'), findsNothing);
  });

  testWidgets('expand/collapse group reveals items', (tester) async {
    await tester.pumpWidget(buildTestApp());
    expect(find.text('send'), findsNothing);
    expect(find.text('list'), findsNothing);

    await tester.tap(find.text('email'));
    await tester.pump();
    expect(find.text('send'), findsOneWidget);
    expect(find.text('list'), findsOneWidget);

    await tester.tap(find.text('email'));
    await tester.pump();
    expect(find.text('send'), findsNothing);
  });

  testWidgets('toggles checkbox on item tap in multi mode', (tester) async {
    final selected = <String>{};
    await tester.pumpWidget(MaterialApp(
      theme: AppTheme.dark,
      home: Scaffold(
        body: GroupedTreeSelector<String>(
          groups: testGroups,
          selected: selected,
          onChanged: (v) => selected..clear()..addAll(v),
          mode: TreeSelectionMode.multi,
        ),
      ),
    ));

    await tester.tap(find.text('email'));
    await tester.pump();

    await tester.tap(find.text('send'));
    expect(selected, {'email_send'});
  });

  testWidgets('single mode selects only one item at a time', (tester) async {
    final selected = <String>{};
    await tester.pumpWidget(MaterialApp(
      theme: AppTheme.dark,
      home: Scaffold(
        body: GroupedTreeSelector<String>(
          groups: testGroups,
          selected: selected,
          onChanged: (v) => selected..clear()..addAll(v),
          mode: TreeSelectionMode.single,
        ),
      ),
    ));

    await tester.tap(find.text('email'));
    await tester.pump();

    await tester.tap(find.text('send'));
    expect(selected, {'email_send'});

    await tester.tap(find.text('files'));
    await tester.pump();

    await tester.tap(find.text('read'));
    expect(selected, {'files_read'});
  });

  testWidgets('group tri-state checkbox selects/deselects all', (tester) async {
    final selected = <String>{};
    await tester.pumpWidget(MaterialApp(
      theme: AppTheme.dark,
      home: Scaffold(
        body: GroupedTreeSelector<String>(
          groups: testGroups,
          selected: selected,
          onChanged: (v) => selected..clear()..addAll(v),
          mode: TreeSelectionMode.multi,
        ),
      ),
    ));

    final groupCheckboxes = find.byType(Checkbox);
    await tester.tap(groupCheckboxes.first);
    expect(selected, {'email_send', 'email_list'});
  });
}
