import 'package:executive_assistant/features/tools/tools_provider.dart';
import 'package:executive_assistant/features/workspace/capabilities_tab.dart';
import 'package:executive_assistant/theme/app_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;

void main() {
  testWidgets('renders 3 ExpansionTile sections with correct icons', (tester) async {
    final container = ProviderContainer();
    addTearDown(container.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp(
          theme: AppTheme.dark,
          home: const Scaffold(body: CapabilitiesTab()),
        ),
      ),
    );
    await tester.pump();

    // Three ExpansionTile headers
    expect(find.text('Tools'), findsOneWidget);
    expect(find.text('Skills'), findsOneWidget);
    expect(find.text('Subagents'), findsOneWidget);

    // Icons
    expect(find.byIcon(Symbols.handyman), findsOneWidget);
    expect(find.byIcon(Symbols.psychology), findsOneWidget);
    expect(find.byIcon(Symbols.robot_2), findsOneWidget);
  });

  testWidgets('search bar filters sections', (tester) async {
    final container = ProviderContainer();
    addTearDown(container.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp(
          theme: AppTheme.dark,
          home: const Scaffold(body: CapabilitiesTab()),
        ),
      ),
    );
    await tester.pump();

    expect(find.byIcon(Symbols.search), findsOneWidget);
    expect(find.byType(TextField), findsOneWidget);
  });

  testWidgets('search filters tools by name', (tester) async {
    final notifier = ToolsNotifier(http.Client());
    // Preload tools into state
    notifier.state = ToolsState(
      tools: [
        const ToolItem(
          name: 'time_get',
          description: 'Get the current time',
          category: 'core',
          annotations: {},
          parameters: {},
          enabled: true,
          source: 'native',
        ),
        const ToolItem(
          name: 'files_read',
          description: 'Read a file',
          category: 'files',
          annotations: {},
          parameters: {},
          enabled: true,
          source: 'native',
        ),
      ],
    );

    final container = ProviderContainer(
      overrides: [toolsProvider.overrideWith((ref) => notifier)],
    );
    addTearDown(container.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp(
          theme: AppTheme.dark,
          home: const Scaffold(body: CapabilitiesTab()),
        ),
      ),
    );
    await tester.pump();

    // Expand tools section
    await tester.tap(find.text('Tools'));
    await tester.pumpAndSettle();

    expect(find.text('time_get'), findsOneWidget);
    expect(find.text('files_read'), findsOneWidget);

    // Type search
    await tester.enterText(find.byType(TextField), 'time');
    await tester.pump();

    expect(find.text('time_get'), findsOneWidget);
    expect(find.text('files_read'), findsNothing);
  });

  testWidgets('shows placeholder for skills and subagents', (tester) async {
    final container = ProviderContainer();
    addTearDown(container.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp(
          theme: AppTheme.dark,
          home: const Scaffold(body: CapabilitiesTab()),
        ),
      ),
    );
    await tester.pump();

    // Expand skills
    await tester.tap(find.text('Skills'));
    await tester.pumpAndSettle();

    // Expand subagents
    await tester.tap(find.text('Subagents'));
    await tester.pumpAndSettle();

    expect(find.text('Coming soon'), findsNWidgets(2));
  });
}
