import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:executive_assistant/core/animations.dart';

void main() {
  testWidgets('EaAnimations.fadeIn fades in over 200ms', (tester) async {
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: EaAnimations.fadeIn(
          child: const Text('hello'),
        ),
      ),
    ));

    final opacityFinder = find.byType(Opacity);
    expect(opacityFinder, findsOneWidget);

    await tester.pump();
    await tester.pump(const Duration(milliseconds: 250));
    final opacity = tester.widget<Opacity>(opacityFinder);
    expect(opacity.opacity, 1.0);
  });

  testWidgets('EaAnimations.fadeIn respects reduced-motion', (tester) async {
    await tester.pumpWidget(MaterialApp(
      home: MediaQuery(
        data: const MediaQueryData(disableAnimations: true),
        child: Scaffold(
          body: EaAnimations.fadeIn(child: const Text('hello')),
        ),
      ),
    ));
    await tester.pump();
    final opacityFinder = find.byType(Opacity);
    if (opacityFinder.evaluate().isNotEmpty) {
      final op = tester.widget<Opacity>(opacityFinder);
      expect(op.opacity, 1.0);
    }
  });

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
