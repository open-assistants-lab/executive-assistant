import 'package:executive_assistant/widgets/app_input.dart';
import 'package:executive_assistant/theme/app_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('AppChatField uses external controller', (tester) async {
    final controller = TextEditingController(text: 'preloaded');
    final focusNode = FocusNode();
    addTearDown(controller.dispose);
    addTearDown(focusNode.dispose);

    await tester.pumpWidget(MaterialApp(
      theme: AppTheme.light,
      home: Scaffold(
        body: AppChatField(
          controller: controller,
          focusNode: focusNode,
          onSend: (_) {},
        ),
      ),
    ));
    expect(find.text('preloaded'), findsOneWidget);
  });
}
