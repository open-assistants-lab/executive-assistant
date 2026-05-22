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

    // Initial frame: Opacity widget should be present.
    final opacityFinder = find.byType(Opacity);
    expect(opacityFinder, findsOneWidget);

    // Pump once to let postFrameCallback fire and start the animation.
    await tester.pump();
    // After full duration, opacity should be 1.
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
    // With reduced motion, child is instantly visible.
    await tester.pump();
    final opacityFinder = find.byType(Opacity);
    if (opacityFinder.evaluate().isNotEmpty) {
      final op = tester.widget<Opacity>(opacityFinder);
      expect(op.opacity, 1.0);
    }
  });
}
