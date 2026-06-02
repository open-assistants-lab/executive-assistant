import 'package:executive_assistant/features/chat/widgets/tool_call_card.dart';
import 'package:executive_assistant/models/message.dart';
import 'package:executive_assistant/theme/app_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  Widget wrap(Widget child) => MaterialApp(
    theme: AppTheme.light,
    home: Scaffold(body: Center(child: child)),
  );

  testWidgets('header shows tool name and status', (tester) async {
    await tester.pumpWidget(
      wrap(
        const ToolCallCard(
          toolCall: ToolCallDisplay(
            callId: 'c1',
            toolName: 'email_list',
            args: {},
            isPending: true,
          ),
        ),
      ),
    );
    expect(find.text('email_list'), findsOneWidget);
    expect(find.text('Running'), findsOneWidget);
  });

  testWidgets('shows duration in header when set', (tester) async {
    await tester.pumpWidget(
      wrap(
        ToolCallCard(
          toolCall: ToolCallDisplay(
            callId: 'c1',
            toolName: 'email_list',
            args: {},
            duration: const Duration(milliseconds: 320),
            isPending: false,
          ),
        ),
      ),
    );
    expect(find.text('0.3s'), findsOneWidget);
  });

  testWidgets('shows result preview line under header', (tester) async {
    await tester.pumpWidget(
      wrap(
        const ToolCallCard(
          toolCall: ToolCallDisplay(
            callId: 'c1',
            toolName: 'email_list',
            args: {},
            resultPreview: 'Found 12 unread messages in INBOX',
            isPending: false,
          ),
        ),
      ),
    );
    expect(find.text('Found 12 unread messages in INBOX'), findsOneWidget);
  });

  testWidgets('expanding reveals Args and Result sections', (tester) async {
    await tester.pumpWidget(
      wrap(
        const ToolCallCard(
          toolCall: ToolCallDisplay(
            callId: 'c1',
            toolName: 'email_list',
            args: {'folder': 'INBOX', 'limit': 20},
            resultPreview: 'Found 12 unread',
            isPending: false,
          ),
        ),
      ),
    );
    await tester.tap(find.text('email_list'));
    await tester.pumpAndSettle();
    expect(find.text('Args'), findsOneWidget);
    expect(find.text('Result'), findsOneWidget);
    expect(find.textContaining('folder'), findsOneWidget);
    expect(find.textContaining('Found 12'), findsOneWidget);
  });
}
