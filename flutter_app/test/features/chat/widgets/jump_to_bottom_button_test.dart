import 'package:executive_assistant/features/chat/widgets/jump_to_bottom_button.dart';
import 'package:executive_assistant/theme/app_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  Widget wrap(Widget child) => MaterialApp(
    theme: AppTheme.light,
    home: Scaffold(body: Center(child: child)),
  );

  testWidgets('renders with new message count', (tester) async {
    await tester.pumpWidget(
      wrap(JumpToBottomButton(newCount: 3, onPressed: () {})),
    );
    expect(find.text('3 new'), findsOneWidget);
    expect(find.byIcon(Icons.arrow_downward), findsOneWidget);
  });

  testWidgets('renders singular "new" when count is 1', (tester) async {
    await tester.pumpWidget(
      wrap(JumpToBottomButton(newCount: 1, onPressed: () {})),
    );
    expect(find.text('1 new'), findsOneWidget);
  });

  testWidgets('hides badge text when newCount is 0', (tester) async {
    await tester.pumpWidget(
      wrap(JumpToBottomButton(newCount: 0, onPressed: () {})),
    );
    expect(find.byIcon(Icons.arrow_downward), findsOneWidget);
    expect(find.text('0 new'), findsNothing);
  });

  testWidgets('calls onPressed when tapped', (tester) async {
    var tapped = 0;
    await tester.pumpWidget(
      wrap(JumpToBottomButton(newCount: 2, onPressed: () => tapped++)),
    );
    await tester.tap(find.byType(JumpToBottomButton));
    expect(tapped, 1);
  });
}
