import 'dart:async';

import 'package:executive_assistant/features/workspace/subagents_panel.dart';
import 'package:executive_assistant/features/workspace/workspace_panel.dart';
import 'package:executive_assistant/features/workspace/skills_panel.dart';
import 'package:executive_assistant/models/message.dart';
import 'package:executive_assistant/models/subagent.dart';
import 'package:executive_assistant/providers/agent_provider.dart';
import 'package:executive_assistant/providers/subagent_provider.dart';
import 'package:executive_assistant/providers/workspace_provider.dart';
import 'package:executive_assistant/services/api_client.dart';
import 'package:executive_assistant/services/ws_client.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

class MockApiClient extends Mock implements ApiClient {}

class MockWsClient extends Mock implements WsClient {}

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

  testWidgets('refreshes subagent list after chat-created subagent completes', (
    tester,
  ) async {
    final api = MockApiClient();
    final ws = MockWsClient();
    final msgCtrl = StreamController<WsMessage>.broadcast();
    final statusCtrl = StreamController<ConnectionStatus>.broadcast();
    var listCalls = 0;

    when(() => ws.status).thenAnswer((_) => statusCtrl.stream);
    when(() => ws.messages).thenAnswer((_) => msgCtrl.stream);
    when(() => ws.connect()).thenReturn(null);
    when(
      () => ws.sendMessage(any(), workspaceId: any(named: 'workspaceId')),
    ).thenReturn(null);
    when(
      () => api.getConversation(
        limit: any(named: 'limit'),
        workspaceId: any(named: 'workspaceId'),
      ),
    ).thenAnswer((_) async => []);
    when(() => api.listSubagents(workspaceId: 'test12345')).thenAnswer((
      _,
    ) async {
      listCalls++;
      if (listCalls == 1) return [];
      return [
        {
          'name': 'sydney-weather',
          'description': 'Weather forecast specialist',
          'scope': 'workspace',
        },
      ];
    });

    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(api),
        wsClientProvider.overrideWithValue(ws),
      ],
    );
    addTearDown(() async {
      container.dispose();
      await msgCtrl.close();
      await statusCtrl.close();
    });
    container.read(currentWorkspaceIdProvider.notifier).state = 'test12345';
    container.read(agentProvider.notifier).setWorkspaceId('test12345');

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp(
          home: Scaffold(
            body: WorkspacePanel(
              refreshInterval: const Duration(days: 1),
              fileLoader: (_) async => [],
            ),
          ),
        ),
      ),
    );
    await tester.pump();
    await tester.tap(find.byIcon(Icons.smart_toy_outlined));
    await tester.pump();
    await tester.pump();

    expect(find.text('No subagents yet'), findsOneWidget);

    statusCtrl.add(ConnectionStatus.connected);
    await tester.pump();
    expect(container.read(agentProvider).connected, isTrue);
    container.read(agentProvider.notifier).sendMessage('create subagent');
    await tester.pump();
    expect(container.read(agentProvider).status, ChatStatus.streaming);
    msgCtrl.add(
      WsMessage(
        type: 'done',
        data: {
          'type': 'done',
          'response': 'created',
          'workspace_id': 'test12345',
        },
      ),
    );
    await tester.pump();
    await tester.pump();
    await tester.pumpAndSettle();

    expect(container.read(agentProvider).status, ChatStatus.idle);
    expect(container.read(subagentProvider).agents.map((a) => a.name), [
      'sydney-weather',
    ]);

    expect(find.text('sydney-weather'), findsOneWidget);
  });

  testWidgets('start task dialog keeps its text controller alive', (
    tester,
  ) async {
    final api = MockApiClient();
    when(() => api.listSubagents(workspaceId: 'test12345')).thenAnswer(
      (_) async => [
        {
          'name': 'sydney-weather',
          'description': 'Weather forecast specialist',
          'scope': 'workspace',
        },
      ],
    );

    final container = ProviderContainer(
      overrides: [apiClientProvider.overrideWithValue(api)],
    );
    addTearDown(container.dispose);
    container.read(currentWorkspaceIdProvider.notifier).state = 'test12345';

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp(
          home: Scaffold(
            body: WorkspacePanel(
              refreshInterval: const Duration(days: 1),
              fileLoader: (_) async => [],
            ),
          ),
        ),
      ),
    );
    await tester.pump();
    await tester.tap(find.byIcon(Icons.smart_toy_outlined));
    await tester.pump();
    await tester.pump();

    await tester.tap(find.byIcon(Icons.visibility_outlined));
    await tester.pump();
    await tester.tap(find.text('Start new task'));
    await tester.pump();

    expect(tester.takeException(), isNull);
    expect(find.widgetWithText(TextField, 'Task'), findsOneWidget);
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

  testWidgets('create dialog tool picker shows toggles that work', (
    tester,
  ) async {
    final api = MockApiClient();
    when(
      () => api.listSubagents(workspaceId: any(named: 'workspaceId')),
    ).thenAnswer((_) async => []);
    when(
      () => api.listToolNames(),
    ).thenAnswer((_) async => ['time_get', 'shell_execute', 'files_read']);
    when(
      () => api.createSubagent(
        name: any(named: 'name'),
        description: any(named: 'description'),
        model: any(named: 'model'),
        scope: any(named: 'scope'),
        tools: any(named: 'tools'),
        skills: any(named: 'skills'),
        systemPrompt: any(named: 'systemPrompt'),
        maxLlmCalls: any(named: 'maxLlmCalls'),
        costLimitUsd: any(named: 'costLimitUsd'),
        timeoutSeconds: any(named: 'timeoutSeconds'),
        workspaceId: any(named: 'workspaceId'),
      ),
    ).thenAnswer((_) async => {});

    final container = ProviderContainer(
      overrides: [apiClientProvider.overrideWithValue(api)],
    );
    addTearDown(container.dispose);
    container.read(currentWorkspaceIdProvider.notifier).state = 'personal';

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: Scaffold(body: SubagentsPanel())),
      ),
    );
    await tester.pump();

    await tester.tap(find.byIcon(Icons.add));
    await tester.pumpAndSettle();
    await tester.drag(find.byType(SingleChildScrollView), const Offset(0, -300));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Advanced'));
    await tester.pumpAndSettle();

    final checkboxes =
        tester.widgetList<CheckboxListTile>(find.byType(CheckboxListTile));
    expect(checkboxes.isNotEmpty, true);
    final first = checkboxes.first;
    expect(first.onChanged, isNotNull);
  });

  testWidgets('prunes terminal jobs after max threshold', (tester) async {
    final api = MockApiClient();
    when(() => api.listSubagents(workspaceId: 'test12345')).thenAnswer(
      (_) async => [],
    );
    when(() => api.cancelSubagentJob(
      any(),
      workspaceId: any(named: 'workspaceId'),
    )).thenAnswer((_) async => {});

    final container = ProviderContainer(
      overrides: [apiClientProvider.overrideWithValue(api)],
    );
    addTearDown(container.dispose);
    container.read(currentWorkspaceIdProvider.notifier).state = 'test12345';

    final notifier = container.read(subagentProvider.notifier);

    final seeded = <String, SubagentJob>{};
    for (var i = 0; i < 15; i++) {
      seeded['job-$i'] = SubagentJob(
        jobId: 'job-$i',
        agentName: 'agent',
        task: 'task',
        status: 'completed',
        workspaceId: 'test12345',
        createdAt: '2026-01-${(i + 1).toString().padLeft(2, '0')}T00:00:00',
      );
    }
    // Add one running job that we'll cancel to trigger prune
    seeded['job-running'] = SubagentJob(
      jobId: 'job-running',
      agentName: 'agent',
      task: 'task',
      status: 'running',
      workspaceId: 'test12345',
    );
    notifier.state = notifier.state.copyWith(activeJobs: seeded);

    await notifier.cancelJob('job-running', workspaceId: 'test12345');

    // 15 completed + 1 cancelling = 16, pruned to 11 (cancelling + 10 terminal)
    expect(notifier.state.activeJobs.length, 11);
    expect(notifier.state.activeJobs.containsKey('job-0'), isFalse);
    expect(notifier.state.activeJobs.containsKey('job-14'), isTrue);
  });

  testWidgets('create dialog rejects invalid name with inline error', (
    tester,
  ) async {
    final api = MockApiClient();
    when(() => api.listSubagents(workspaceId: any(named: 'workspaceId')))
        .thenAnswer((_) async => []);
    when(() => api.listToolNames()).thenAnswer((_) async => ['time_get']);
    when(
      () => api.createSubagent(
        name: any(named: 'name'),
        description: any(named: 'description'),
        model: any(named: 'model'),
        scope: any(named: 'scope'),
        tools: any(named: 'tools'),
        skills: any(named: 'skills'),
        systemPrompt: any(named: 'systemPrompt'),
        maxLlmCalls: any(named: 'maxLlmCalls'),
        costLimitUsd: any(named: 'costLimitUsd'),
        timeoutSeconds: any(named: 'timeoutSeconds'),
        workspaceId: any(named: 'workspaceId'),
      ),
    ).thenAnswer((_) async => {});

    final container = ProviderContainer(
      overrides: [apiClientProvider.overrideWithValue(api)],
    );
    addTearDown(container.dispose);
    container.read(currentWorkspaceIdProvider.notifier).state = 'personal';

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: Scaffold(body: SubagentsPanel())),
      ),
    );
    await tester.pump();

    await tester.tap(find.byIcon(Icons.add));
    await tester.pumpAndSettle();

    // Enter invalid name with spaces
    await tester.enterText(
      find.widgetWithText(TextField, 'Name *'),
      'bad name',
    );
    await tester.enterText(
      find.widgetWithText(TextField, 'Description *'),
      'Description',
    );
    await tester.tap(find.text('Create'));
    await tester.pumpAndSettle();

    // Dialog should still be open with error message
    expect(
      find.text('Name can only contain letters, numbers, hyphens, and underscores'),
      findsOneWidget,
    );
    verifyNever(
      () => api.createSubagent(
        name: any(named: 'name'),
        description: any(named: 'description'),
        workspaceId: any(named: 'workspaceId'),
        model: any(named: 'model'),
        scope: any(named: 'scope'),
        tools: any(named: 'tools'),
        skills: any(named: 'skills'),
        systemPrompt: any(named: 'systemPrompt'),
        maxLlmCalls: any(named: 'maxLlmCalls'),
        costLimitUsd: any(named: 'costLimitUsd'),
        timeoutSeconds: any(named: 'timeoutSeconds'),
      ),
    );
  });
}
