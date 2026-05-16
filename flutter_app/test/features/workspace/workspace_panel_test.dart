import 'dart:async';

import 'package:executive_assistant/features/workspace/workspace_panel.dart';
import 'package:executive_assistant/features/workspace/skills_panel.dart';
import 'package:executive_assistant/providers/agent_provider.dart';
import 'package:executive_assistant/providers/workspace_provider.dart';
import 'package:executive_assistant/services/api_client.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

class MockApiClient extends Mock implements ApiClient {}

void main() {
  testWidgets('refreshes file list without switching workspace', (
    tester,
  ) async {
    var calls = 0;
    Future<List<Map<String, dynamic>>> loadFiles(WidgetRef ref) async {
      calls++;
      if (calls == 1) {
        return [
          {'name': 'old.pdf', 'is_dir': false, 'size': 10},
        ];
      }
      return [
        {'name': 'new.pdf', 'is_dir': false, 'size': 20},
      ];
    }

    await tester.pumpWidget(
      ProviderScope(
        child: MaterialApp(
          home: Scaffold(
            body: WorkspacePanel(
              refreshInterval: const Duration(seconds: 1),
              fileLoader: loadFiles,
            ),
          ),
        ),
      ),
    );
    await tester.pump();

    expect(find.text('old.pdf'), findsOneWidget);

    await tester.pump(const Duration(seconds: 1));
    await tester.pump();

    expect(find.text('new.pdf'), findsOneWidget);
  });

  testWidgets('defaults to files and switches to skills from bottom icon tab', (
    tester,
  ) async {
    final api = MockApiClient();
    when(
      () => api.listSkills(workspaceId: any(named: 'workspaceId')),
    ).thenAnswer(
      (_) async => [
        {
          'name': 'email-triage',
          'description': 'Prioritize incoming messages and draft responses',
          'scope': 'workspace',
        },
      ],
    );

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          apiClientProvider.overrideWithValue(api),
          currentWorkspaceIdProvider.overrideWith((ref) => 'sales'),
        ],
        child: MaterialApp(
          home: Scaffold(
            body: WorkspacePanel(
              refreshInterval: const Duration(days: 1),
              fileLoader: (_) async => [
                {'name': 'brief.md', 'is_dir': false, 'size': 20},
              ],
            ),
          ),
        ),
      ),
    );
    await tester.pump();

    expect(find.text('Files'), findsOneWidget);
    expect(find.text('brief.md'), findsOneWidget);

    await tester.tap(find.byIcon(Icons.bolt_outlined));
    await tester.pump();
    await tester.pump();

    expect(find.text('Skills'), findsOneWidget);
    expect(find.text('email-triage'), findsOneWidget);
    expect(find.text('ws'), findsOneWidget);
    verify(() => api.listSkills(workspaceId: 'sales')).called(1);
  });

  testWidgets('discards stale skills response after workspace changes', (
    tester,
  ) async {
    final api = MockApiClient();
    final salesCompleter = Completer<List<dynamic>>();
    when(
      () => api.listSkills(workspaceId: 'sales'),
    ).thenAnswer((_) => salesCompleter.future);
    when(() => api.listSkills(workspaceId: 'support')).thenAnswer(
      (_) async => [
        {
          'name': 'support-skill',
          'description': 'Support workflow',
          'scope': 'workspace',
        },
      ],
    );

    final container = ProviderContainer(
      overrides: [apiClientProvider.overrideWithValue(api)],
    );
    addTearDown(container.dispose);
    container.read(currentWorkspaceIdProvider.notifier).state = 'sales';

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: Scaffold(body: SkillsPanel())),
      ),
    );
    await tester.pump();

    container.read(currentWorkspaceIdProvider.notifier).state = 'support';
    await tester.pump();
    await tester.pump();

    expect(find.text('support-skill'), findsOneWidget);

    salesCompleter.complete([
      {
        'name': 'sales-skill',
        'description': 'Sales workflow',
        'scope': 'workspace',
      },
    ]);
    await tester.pump(const Duration(milliseconds: 10));
    await tester.pump(const Duration(milliseconds: 10));

    expect(find.text('support-skill'), findsOneWidget);
    expect(find.text('sales-skill'), findsNothing);
  });

  testWidgets('discards older overlapping skills response for same workspace', (
    tester,
  ) async {
    final api = MockApiClient();
    final firstCompleter = Completer<List<dynamic>>();
    final secondCompleter = Completer<List<dynamic>>();
    var calls = 0;
    when(() => api.listSkills(workspaceId: 'sales')).thenAnswer((_) {
      calls++;
      return calls == 1 ? firstCompleter.future : secondCompleter.future;
    });

    final container = ProviderContainer(
      overrides: [apiClientProvider.overrideWithValue(api)],
    );
    addTearDown(container.dispose);
    container.read(currentWorkspaceIdProvider.notifier).state = 'sales';

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: Scaffold(body: SkillsPanel())),
      ),
    );
    await tester.pump();

    await tester.tap(find.byIcon(Icons.refresh));
    await tester.pump();
    expect(calls, 2);

    secondCompleter.complete([
      <String, dynamic>{
        'name': 'fresh-skill',
        'description': 'Current workflow',
        'scope': 'workspace',
      },
    ]);
    firstCompleter.complete([
      <String, dynamic>{
        'name': 'stale-skill',
        'description': 'Older workflow',
        'scope': 'workspace',
      },
    ]);
    await tester.pump();
    await tester.pump();

    expect(find.text('fresh-skill'), findsOneWidget);
    expect(find.text('stale-skill'), findsNothing);
  });

  testWidgets('create dialog prevents duplicate submissions', (tester) async {
    final api = MockApiClient();
    final createCompleter = Completer<Map<String, dynamic>>();
    when(
      () => api.listSkills(workspaceId: any(named: 'workspaceId')),
    ).thenAnswer((_) async => []);
    when(
      () => api.createSkill(
        any(),
        any(),
        any(),
        scope: any(named: 'scope'),
        workspaceId: any(named: 'workspaceId'),
      ),
    ).thenAnswer((_) => createCompleter.future);

    final container = ProviderContainer(
      overrides: [apiClientProvider.overrideWithValue(api)],
    );
    addTearDown(container.dispose);
    container.read(currentWorkspaceIdProvider.notifier).state = 'sales';

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: Scaffold(body: SkillsPanel())),
      ),
    );
    await tester.pump();

    await tester.tap(find.byIcon(Icons.add));
    await tester.pump();
    await tester.enterText(find.widgetWithText(TextField, 'Name'), 'triage');
    await tester.enterText(
      find.widgetWithText(TextField, 'Description'),
      'Sort inbox',
    );
    await tester.enterText(
      find.widgetWithText(TextField, 'Content'),
      'Prioritize urgent messages',
    );

    final createButton = find.byType(FilledButton);
    await tester.tap(createButton);
    await tester.pump();
    await tester.tap(createButton);
    await tester.pump();

    verify(
      () => api.createSkill(
        'triage',
        'Sort inbox',
        'Prioritize urgent messages',
        scope: 'workspace',
        workspaceId: 'sales',
      ),
    ).called(1);

    createCompleter.complete({'ok': true});
  });

  testWidgets(
    'delete is cancelled when workspace changes while dialog is open',
    (tester) async {
      final api = MockApiClient();
      when(() => api.listSkills(workspaceId: 'sales')).thenAnswer(
        (_) async => [
          <String, dynamic>{
            'name': 'triage',
            'description': 'Sort inbox',
            'scope': 'workspace',
          },
        ],
      );
      when(() => api.listSkills(workspaceId: 'support')).thenAnswer(
        (_) async => [
          <String, dynamic>{
            'name': 'support-skill',
            'description': 'Support workflow',
            'scope': 'workspace',
          },
        ],
      );
      when(
        () => api.deleteSkill(
          any(),
          scope: any(named: 'scope'),
          workspaceId: any(named: 'workspaceId'),
        ),
      ).thenAnswer((_) async {});

      final container = ProviderContainer(
        overrides: [apiClientProvider.overrideWithValue(api)],
      );
      addTearDown(container.dispose);
      container.read(currentWorkspaceIdProvider.notifier).state = 'sales';

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(home: Scaffold(body: SkillsPanel())),
        ),
      );
      await tester.pump();
      await tester.pump();

      await tester.tap(find.byIcon(Icons.delete_outline));
      await tester.pump();
      container.read(currentWorkspaceIdProvider.notifier).state = 'support';
      await tester.pump();
      await tester.tap(find.widgetWithText(FilledButton, 'Delete'));
      await tester.pump();

      verifyNever(
        () => api.deleteSkill(
          any(),
          scope: any(named: 'scope'),
          workspaceId: any(named: 'workspaceId'),
        ),
      );
      expect(find.text('Workspace changed; delete cancelled.'), findsOneWidget);
    },
  );

  testWidgets(
    'create is cancelled when workspace changes while dialog is open',
    (tester) async {
      final api = MockApiClient();
      when(
        () => api.listSkills(workspaceId: any(named: 'workspaceId')),
      ).thenAnswer((_) async => []);
      when(
        () => api.createSkill(
          any(),
          any(),
          any(),
          scope: any(named: 'scope'),
          workspaceId: any(named: 'workspaceId'),
        ),
      ).thenAnswer((_) async => {'ok': true});

      final container = ProviderContainer(
        overrides: [apiClientProvider.overrideWithValue(api)],
      );
      addTearDown(container.dispose);
      container.read(currentWorkspaceIdProvider.notifier).state = 'sales';

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(home: Scaffold(body: SkillsPanel())),
        ),
      );
      await tester.pump();

      await tester.tap(find.byIcon(Icons.add));
      await tester.pump();
      await tester.enterText(find.widgetWithText(TextField, 'Name'), 'triage');
      await tester.enterText(
        find.widgetWithText(TextField, 'Description'),
        'Sort inbox',
      );
      await tester.enterText(
        find.widgetWithText(TextField, 'Content'),
        'Prioritize urgent messages',
      );
      container.read(currentWorkspaceIdProvider.notifier).state = 'support';
      await tester.pump();

      await tester.tap(find.byType(FilledButton));
      await tester.pump();

      verifyNever(
        () => api.createSkill(
          any(),
          any(),
          any(),
          scope: any(named: 'scope'),
          workspaceId: any(named: 'workspaceId'),
        ),
      );
      expect(find.text('Workspace changed; create cancelled.'), findsOneWidget);
    },
  );
}
