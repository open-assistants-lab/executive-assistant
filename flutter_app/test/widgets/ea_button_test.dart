import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:executive_assistant/widgets/ea_button.dart';
import 'package:executive_assistant/theme/app_theme.dart';

Widget wrap(Widget child) => MaterialApp(
      theme: AppTheme.dark,
      home: Scaffold(body: Center(child: child)),
    );

void main() {
  testWidgets('EaButton.primary renders label and is tappable', (tester) async {
    var tapped = false;
    await tester.pumpWidget(wrap(
      EaButton.primary(label: 'Send', onPressed: () => tapped = true),
    ));
    expect(find.text('Send'), findsOneWidget);
    await tester.tap(find.text('Send'));
    await tester.pump();
    expect(tapped, true);
  });

  testWidgets('EaButton respects disabled state (onPressed: null)', (tester) async {
    await tester.pumpWidget(wrap(
      const EaButton.primary(label: 'Send', onPressed: null),
    ));
    final inkWell = find.byType(InkWell).first;
    final widget = tester.widget<InkWell>(inkWell);
    expect(widget.onTap, isNull);
  });

  testWidgets('EaButton.secondary has a border', (tester) async {
    await tester.pumpWidget(wrap(
      EaButton.secondary(label: 'Cancel', onPressed: () {}),
    ));
    expect(find.text('Cancel'), findsOneWidget);
  });

  testWidgets('EaButton.ghost has no border and transparent bg', (tester) async {
    await tester.pumpWidget(wrap(
      EaButton.ghost(label: 'More', onPressed: () {}),
    ));
    expect(find.text('More'), findsOneWidget);
  });
}
