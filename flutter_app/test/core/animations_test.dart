import 'package:executive_assistant/core/animations.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('staggeredEntry fades without translating the child', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: EaAnimations.staggeredEntry(
            index: 0,
            child: const Text('message'),
          ),
        ),
      ),
    );

    expect(find.text('message'), findsOneWidget);
    expect(find.byType(Opacity), findsOneWidget);
    final translatedWidgets = tester
        .widgetList<Transform>(find.byType(Transform))
        .where((widget) => widget.transform.getTranslation().y.abs() > 0.1);
    expect(translatedWidgets, isEmpty);
  });
}
