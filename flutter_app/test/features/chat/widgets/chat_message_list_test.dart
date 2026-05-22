import 'package:executive_assistant/features/chat/widgets/chat_message_list.dart';
import 'package:executive_assistant/models/message.dart';
import 'package:executive_assistant/theme/app_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('renders existing messages without entry slide animation', (
    tester,
  ) async {
    final controller = ScrollController();
    addTearDown(controller.dispose);

    await tester.pumpWidget(
      MaterialApp(
        theme: AppTheme.light,
        home: Scaffold(
          body: ChatMessageList(
            scrollController: controller,
            messages: [
              ChatMessage(
                id: 'm1',
                role: 'assistant',
                content: 'Existing message',
                timestamp: DateTime(2026),
              ),
            ],
          ),
        ),
      ),
    );

    expect(find.text('Existing message'), findsOneWidget);
    expect(find.byType(TweenAnimationBuilder<double>), findsNothing);
  });
}
