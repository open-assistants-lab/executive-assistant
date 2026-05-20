import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../models/subagent.dart';
import '../../providers/agent_provider.dart';
import '../../providers/subagent_provider.dart';
import '../../providers/workspace_provider.dart';
import '../../theme/app_theme.dart';

final _nameRegex = RegExp(r'^[a-zA-Z0-9_-]+$');
const _nameValidationMessage =
    'Name can only contain letters, numbers, hyphens, and underscores';

class SubagentsPanel extends ConsumerStatefulWidget {
  const SubagentsPanel({super.key});

  @override
  ConsumerState<SubagentsPanel> createState() => _SubagentsPanelState();
}

class _SubagentsPanelState extends ConsumerState<SubagentsPanel> {
  int _loadSequence = 0;
  bool _initialized = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  Future<void> _load() async {
    final requestId = ++_loadSequence;
    final wsId = ref.read(currentWorkspaceIdProvider);
    await ref.read(subagentProvider.notifier).loadList(workspaceId: wsId);
    if (!mounted || requestId != _loadSequence) return;
    _initialized = true;
  }

  @override
  Widget build(BuildContext context) {
    ref.listen(currentWorkspaceIdProvider, (prev, next) {
      if (prev != next) _load();
    });

    ref.listen<ChatState>(agentProvider, (prev, next) {
      if (prev?.status == ChatStatus.streaming &&
          next.status == ChatStatus.idle) {
        _load();
      }
    });

    final state = ref.watch(subagentProvider);

    return Container(
      color: context.tokens.colors.bgCanvas,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildHeader(state),
          Expanded(child: _buildBody(state)),
        ],
      ),
    );
  }

  Widget _buildHeader(SubagentPanelState state) {
    return Container(
      height: 52,
      padding: const EdgeInsets.symmetric(horizontal: 12),
      decoration: BoxDecoration(
        border: Border(bottom: BorderSide(color: context.tokens.colors.borderSubtle)),
      ),
      child: Row(
        children: [
          Icon(Symbols.smart_toy, size: 18, color: context.tokens.colors.accent),
          const SizedBox(width: 8),
          Text(
            'Subagents',
            style: context.tokens.typography.textTheme.headlineMedium!.copyWith(fontSize: 15, color: context.tokens.colors.textPrimary),
          ),
          const Spacer(),
          if (state.loading && state.agents.isNotEmpty)
            const SizedBox(
              width: 14,
              height: 14,
              child: CircularProgressIndicator(strokeWidth: 2),
            ),
          const SizedBox(width: 4),
          Text(
            '${state.agents.length}',
            style: context.tokens.typography.textTheme.bodySmall!.copyWith(color: context.tokens.colors.textTertiary),
          ),
          const SizedBox(width: 4),
          InkWell(
            onTap: _load,
            child: Icon(Symbols.refresh, size: 16, color: context.tokens.colors.textTertiary),
          ),
          const SizedBox(width: 8),
          InkWell(
            onTap: _showCreateDialog,
            child: Icon(Symbols.add, size: 18, color: context.tokens.colors.textTertiary),
          ),
        ],
      ),
    );
  }

  Widget _buildBody(SubagentPanelState state) {
    if (!_initialized && state.loading) {
      return const Center(child: CircularProgressIndicator(strokeWidth: 2));
    }
    if (state.error != null && state.agents.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                state.error!,
                style: context.tokens.typography.textTheme.bodySmall!.copyWith(color: context.tokens.colors.error),
              ),
              const SizedBox(height: 8),
              OutlinedButton(onPressed: _load, child: const Text('Retry')),
            ],
          ),
        ),
      );
    }
    if (state.agents.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Symbols.smart_toy, size: 40, color: context.tokens.colors.textTertiary),
            const SizedBox(height: 8),
            Text(
              'No subagents yet',
              style: context.tokens.typography.textTheme.bodySmall!.copyWith(color: context.tokens.colors.textTertiary),
            ),
            const SizedBox(height: 4),
            Text(
              'Create one from the panel or via chat',
              style: context.tokens.typography.textTheme.bodySmall!.copyWith(
                color: context.tokens.colors.textTertiary,
                fontSize: 11,
              ),
            ),
          ],
        ),
      );
    }
    return ListView.builder(
      padding: EdgeInsets.zero,
      itemCount: state.agents.length,
      itemBuilder: (_, i) {
        final agent = state.agents[i];
        final runningJobs = state.activeJobs.values
            .where((j) => j.agentName == agent.name && !j.isTerminal)
            .toList();
        return _SubagentTile(
          agent: agent,
          runningJobs: runningJobs,
          onStart: () => _showStartDialog(agent),
          onEdit: () => _showEditDialog(agent),
          onDelete: () => _confirmDelete(agent),
        );
      },
    );
  }

  Future<void> _showCreateDialog() async {
    final wsId = ref.read(currentWorkspaceIdProvider);
    final defaultScope = wsId == 'personal' ? 'user' : 'workspace';

    final nameCtrl = TextEditingController();
    final descriptionCtrl = TextEditingController();
    final modelCtrl = TextEditingController();
    final systemPromptCtrl = TextEditingController();
    var scope = defaultScope;
    var advancedExpanded = false;
    var maxLlmCalls = 50;
    var costLimitUsd = 1.0;
    var timeoutSeconds = 300;
    var submitting = false;
    String? nameError;
    Set<String> selectedTools = {};
    Set<String> selectedSkills = {};

    List<String>? allTools;
    List<String>? allSkills;
    try {
      allTools = await ref.read(apiClientProvider).listToolNames();
      selectedTools = allTools.toSet();
    } catch (_) {}
    try {
      final skillsJson = await ref.read(apiClientProvider).listSkills();
      allSkills = skillsJson.map((s) => s['name']?.toString() ?? '').where((n) => n.isNotEmpty).toList();
    } catch (_) {}
    if (!mounted) {
      nameCtrl.dispose();
      descriptionCtrl.dispose();
      modelCtrl.dispose();
      systemPromptCtrl.dispose();
      return;
    }

    final t = context.tokens;
    final created = await showDialog<bool>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          title: Text('Create Subagent', style: t.typography.textTheme.titleLarge?.copyWith(color: t.colors.textPrimary)),
          content: SingleChildScrollView(
            child: SizedBox(
              width: 480,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  TextField(
                    controller: nameCtrl,
                    style: t.typography.textTheme.bodyLarge?.copyWith(color: t.colors.textPrimary),
                    decoration: InputDecoration(
                      labelText: 'Name *',
                      hintText: 'my-researcher',
                      errorText: nameError,
                    ),
                    onChanged: (_) =>
                        setDialogState(() => nameError = null),
                  ),
                  const SizedBox(height: 10),
                  TextField(
                    controller: descriptionCtrl,
                    style: t.typography.textTheme.bodyLarge?.copyWith(color: t.colors.textPrimary),
                    decoration: const InputDecoration(
                      labelText: 'Description *',
                      hintText: 'Researches topics and summarizes',
                    ),
                    maxLines: 2,
                  ),
                  const SizedBox(height: 10),
                  DropdownButtonFormField<String>(
                    value: scope,
                    decoration: const InputDecoration(
                      labelText: 'Scope',
                    ),
                    items: const [
                      DropdownMenuItem(value: 'user', child: Text('User')),
                      DropdownMenuItem(value: 'workspace', child: Text('Workspace')),
                    ],
                    onChanged: submitting ? null : (v) {
                      if (v != null) setDialogState(() => scope = v);
                    },
                  ),
                  const SizedBox(height: 10),
                  TextField(
                    controller: modelCtrl,
                    style: t.typography.textTheme.bodyLarge?.copyWith(color: t.colors.textPrimary),
                    decoration: const InputDecoration(
                      labelText: 'Model',
                      hintText: 'deepseek:deepseek-v4-flash',
                    ),
                  ),
                  const SizedBox(height: 10),
                  TextField(
                    controller: systemPromptCtrl,
                    style: t.typography.textTheme.bodyLarge?.copyWith(color: t.colors.textPrimary),
                    maxLines: 3,
                    decoration: const InputDecoration(
                      labelText: 'System prompt (optional)',
                    ),
                  ),
                  const SizedBox(height: 8),
                  ExpansionTile(
                    title: const Text('Advanced'),
                    initiallyExpanded: advancedExpanded,
                    onExpansionChanged: (v) =>
                        setDialogState(() => advancedExpanded = v),
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: _NumberField(
                              label: 'Max LLM calls',
                              value: maxLlmCalls,
                              onChanged: (v) =>
                                  setDialogState(() => maxLlmCalls = v as int),
                            ),
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: _NumberField(
                              label: 'Cost limit (\$)',
                              value: costLimitUsd,
                              isDouble: true,
                              onChanged: (v) => setDialogState(
                                () => costLimitUsd = v as double,
                              ),
                            ),
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: _NumberField(
                              label: 'Timeout (s)',
                              value: timeoutSeconds,
                              onChanged: (v) => setDialogState(
                                () => timeoutSeconds = v as int,
                              ),
                            ),
                          ),
                        ],
                      ),
                      if (allTools != null) ...[
                        const SizedBox(height: 10),
                        Row(
                          children: [
                            Text(
                              'Tools',
                              style: context.tokens.typography.textTheme.bodySmall!.copyWith(
                                color: context.tokens.colors.textSecondary,
                              ),
                            ),
                            const Spacer(),
                            InkWell(
                              onTap: () => setDialogState(
                                () => selectedTools = allTools!.toSet(),
                              ),
                              child: Text(
                                'All',
                                style: context.tokens.typography.textTheme.bodySmall!.copyWith(
                                  color: context.tokens.colors.accent,
                                ),
                              ),
                            ),
                            Text(' / ',
                                style: TextStyle(color: context.tokens.colors.textTertiary)),
                            InkWell(
                              onTap: () => setDialogState(
                                () => selectedTools = {},
                              ),
                              child: Text(
                                'Clear',
                                style: context.tokens.typography.textTheme.bodySmall!.copyWith(
                                  color: context.tokens.colors.accent,
                                ),
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 4),
                        SizedBox(
                          height: 120,
                          child: ListView(
                            children: allTools
                                .where((t) => !t.startsWith('subagent_'))
                                .map(
                                  (t) => CheckboxListTile(
                                    dense: true,
                                    value: selectedTools.contains(t),
                                    title: Text(
                                      t,
                                  style: context.tokens.typography.textTheme.bodySmall!.copyWith(
                                    fontSize: 12, color: context.tokens.colors.textSecondary,
                                  ),
                                    ),
                                    onChanged: (v) {
                                      setDialogState(() {
                                        if (v == true) {
                                          selectedTools = {
                                            ...selectedTools,
                                            t,
                                          };
                                        } else {
                                          selectedTools = selectedTools
                                              .difference({t});
                                        }
                                      });
                                    },
                                  ),
                                )
                                .toList(),
                          ),
                        ),
                      ],
                      if (allSkills != null) ...[
                        const SizedBox(height: 10),
                        Row(
                          children: [
                            Text(
                              'Skills',
                              style: context.tokens.typography.textTheme.bodySmall!.copyWith(
                                color: context.tokens.colors.textSecondary,
                              ),
                            ),
                            const Spacer(),
                            InkWell(
                              onTap: () => setDialogState(
                                () => selectedSkills = allSkills!.toSet(),
                              ),
                              child: Text(
                                'All',
                                style: context.tokens.typography.textTheme.bodySmall!.copyWith(
                                  color: context.tokens.colors.accent,
                                ),
                              ),
                            ),
                            Text(' / ',
                                style: TextStyle(color: context.tokens.colors.textTertiary)),
                            InkWell(
                              onTap: () => setDialogState(
                                () => selectedSkills = {},
                              ),
                              child: Text(
                                'Clear',
                                style: context.tokens.typography.textTheme.bodySmall!.copyWith(
                                  color: context.tokens.colors.accent,
                                ),
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 4),
                        SizedBox(
                          height: 120,
                          child: ListView(
                            children: allSkills
                                .map(
                                  (s) => CheckboxListTile(
                                    dense: true,
                                    value: selectedSkills.contains(s),
                                    title: Text(
                                      s,
                                  style: context.tokens.typography.textTheme.bodySmall!.copyWith(
                                    fontSize: 12, color: context.tokens.colors.textSecondary,
                                  ),
                                    ),
                                    onChanged: (v) {
                                      setDialogState(() {
                                        if (v == true) {
                                          selectedSkills = {
                                            ...selectedSkills,
                                            s,
                                          };
                                        } else {
                                          selectedSkills = selectedSkills
                                              .difference({s});
                                        }
                                      });
                                    },
                                  ),
                                )
                                .toList(),
                          ),
                        ),
                      ],
                    ],
                  ),
                ],
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: submitting ? null : () => Navigator.pop(ctx, false),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: submitting
                  ? null
                  : () async {
                      final name = nameCtrl.text.trim();
                      final description = descriptionCtrl.text.trim();
                      if (name.isEmpty || description.isEmpty) return;
                      if (!_nameRegex.hasMatch(name)) {
                        setDialogState(
                          () => nameError = _nameValidationMessage,
                        );
                        return;
                      }
                      setDialogState(() => nameError = null);
                      if (ref.read(currentWorkspaceIdProvider) != wsId) {
                        if (!ctx.mounted) return;
                        ScaffoldMessenger.of(ctx).showSnackBar(
                          const SnackBar(
                            content: Text('Workspace changed; cancelled.'),
                          ),
                        );
                        Navigator.pop(ctx, false);
                        return;
                      }
                      setDialogState(() => submitting = true);
                      try {
                        await ref
                            .read(subagentProvider.notifier)
                            .createAgent(
                              name: name,
                              description: description,
                              model: modelCtrl.text.trim().isEmpty
                                  ? null
                                  : modelCtrl.text.trim(),
                              scope: scope,
                              maxLlmCalls: maxLlmCalls,
                              costLimitUsd: costLimitUsd,
                              timeoutSeconds: timeoutSeconds,
                              systemPrompt: systemPromptCtrl.text.trim().isEmpty
                                  ? null
                                  : systemPromptCtrl.text.trim(),
                              workspaceId: wsId,
                              tools: selectedTools.length ==
                                      (allTools?.length ?? 0)
                                  ? null
                                  : selectedTools.toList(),
                              skills: selectedSkills.isEmpty
                                  ? null
                                  : selectedSkills.toList(),
                            );
                        if (ctx.mounted) Navigator.pop(ctx, true);
                      } catch (e) {
                        if (!ctx.mounted) return;
                        setDialogState(() => submitting = false);
                        ScaffoldMessenger.of(ctx).showSnackBar(
                          SnackBar(content: Text('Create failed: $e')),
                        );
                      }
                    },
              child: submitting
                  ? const SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Text('Create'),
            ),
          ],
        ),
      ),
    );

    nameCtrl.dispose();
    descriptionCtrl.dispose();
    modelCtrl.dispose();
    systemPromptCtrl.dispose();
    if (created == true) await _load();
  }

  Future<void> _showStartDialog(SubagentAgentDef agent) async {
    final taskCtrl = TextEditingController();
    var submitting = false;

    final t = context.tokens;
    await showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          title: Text('Start ${agent.name}', style: t.typography.textTheme.titleLarge?.copyWith(color: t.colors.textPrimary)),
          content: SizedBox(
            width: 400,
            child: TextField(
              controller: taskCtrl,
              autofocus: true,
              minLines: 3,
              maxLines: 6,
              style: t.typography.textTheme.bodyLarge?.copyWith(color: t.colors.textPrimary),
              decoration: const InputDecoration(
                labelText: 'Task',
                hintText: 'What should the subagent do?',
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: submitting ? null : () => Navigator.pop(ctx),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: submitting
                  ? null
                  : () async {
                      final task = taskCtrl.text.trim();
                      if (task.isEmpty) return;
                      setDialogState(() => submitting = true);
                      try {
                        await ref
                            .read(subagentProvider.notifier)
                            .startJob(agent.name, task);
                        if (ctx.mounted) Navigator.pop(ctx);
                      } catch (e) {
                        if (!ctx.mounted) return;
                        setDialogState(() => submitting = false);
                        ScaffoldMessenger.of(ctx).showSnackBar(
                          SnackBar(content: Text('Start failed: $e')),
                        );
                      }
                    },
              child: submitting
                  ? const SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Text('Start'),
            ),
          ],
        ),
      ),
    );

    taskCtrl.dispose();
  }

  Future<void> _showEditDialog(SubagentAgentDef agent) async {
    final descriptionCtrl = TextEditingController(text: agent.description);
    final modelCtrl = TextEditingController(text: agent.model ?? '');
    final systemPromptCtrl = TextEditingController(
      text: agent.systemPrompt ?? '',
    );
    var maxLlmCalls = agent.maxLlmCalls;
    var costLimitUsd = agent.costLimitUsd;
    var timeoutSeconds = agent.timeoutSeconds;
    var submitting = false;

    Set<String> selectedTools = agent.tools?.toSet() ?? {};
    Set<String> selectedSkills = agent.skills?.toSet() ?? {};

    List<String>? allTools;
    List<String>? allSkills;
    try {
      allTools = await ref.read(apiClientProvider).listToolNames();
      if (selectedTools.isEmpty) selectedTools = allTools.toSet();
    } catch (_) {}
    try {
      final skillsJson = await ref.read(apiClientProvider).listSkills();
      allSkills = skillsJson.map((s) => s['name']?.toString() ?? '').where((n) => n.isNotEmpty).toList();
    } catch (_) {}

    final t = context.tokens;
    await showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          title: Text('Edit ${agent.name}', style: t.typography.textTheme.titleLarge?.copyWith(color: t.colors.textPrimary)),
          content: SingleChildScrollView(
            child: SizedBox(
              width: 480,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  TextField(
                    controller: descriptionCtrl,
                    style: t.typography.textTheme.bodyLarge?.copyWith(color: t.colors.textPrimary),
                    decoration: const InputDecoration(
                      labelText: 'Description',
                    ),
                    maxLines: 2,
                  ),
                  const SizedBox(height: 10),
                  TextField(
                    controller: modelCtrl,
                    style: t.typography.textTheme.bodyLarge?.copyWith(color: t.colors.textPrimary),
                    decoration: const InputDecoration(
                      labelText: 'Model',
                    ),
                  ),
                  const SizedBox(height: 10),
                  TextField(
                    controller: systemPromptCtrl,
                    style: t.typography.textTheme.bodyLarge?.copyWith(color: t.colors.textPrimary),
                    maxLines: 3,
                    decoration: const InputDecoration(
                      labelText: 'System prompt (optional)',
                    ),
                  ),
                  const SizedBox(height: 10),
                  Row(
                    children: [
                      Expanded(
                        child: _NumberField(
                          label: 'Max LLM calls',
                          value: maxLlmCalls,
                          onChanged: (v) =>
                              setDialogState(() => maxLlmCalls = v as int),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: _NumberField(
                          label: 'Cost limit (\$)',
                          value: costLimitUsd,
                          isDouble: true,
                          onChanged: (v) =>
                              setDialogState(() => costLimitUsd = v as double),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: _NumberField(
                          label: 'Timeout (s)',
                          value: timeoutSeconds,
                          onChanged: (v) =>
                              setDialogState(() => timeoutSeconds = v as int),
                        ),
                      ),
                    ],
                  ),
                  if (allTools != null) ...[
                    const SizedBox(height: 10),
                    Row(
                      children: [
                        Text(
                          'Tools',
                          style: context.tokens.typography.textTheme.bodySmall!.copyWith(
                            color: context.tokens.colors.textSecondary,
                          ),
                        ),
                        const Spacer(),
                        InkWell(
                          onTap: () => setDialogState(
                            () => selectedTools = allTools!.toSet(),
                          ),
                          child: Text(
                            'All',
                            style: context.tokens.typography.textTheme.bodySmall!.copyWith(
                              color: context.tokens.colors.accent,
                            ),
                          ),
                        ),
                        Text(' / ',
                            style: TextStyle(color: context.tokens.colors.textTertiary)),
                        InkWell(
                          onTap: () => setDialogState(
                            () => selectedTools = {},
                          ),
                          child: Text(
                            'Clear',
                            style: context.tokens.typography.textTheme.bodySmall!.copyWith(
                              color: context.tokens.colors.accent,
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 4),
                    SizedBox(
                      height: 120,
                      child: ListView(
                        children: allTools
                            .where((t) => !t.startsWith('subagent_'))
                            .map(
                              (t) => CheckboxListTile(
                                dense: true,
                                value: selectedTools.contains(t),
                                title: Text(
                                  t,
                              style: context.tokens.typography.textTheme.bodySmall!.copyWith(
                                fontSize: 12, color: context.tokens.colors.textSecondary,
                              ),
                                ),
                                onChanged: (v) {
                                  setDialogState(() {
                                    if (v == true) {
                                      selectedTools = {
                                        ...selectedTools,
                                        t,
                                      };
                                    } else {
                                      selectedTools = selectedTools
                                          .difference({t});
                                    }
                                  });
                                },
                              ),
                            )
                            .toList(),
                      ),
                    ),
                  ],
                  if (allSkills != null) ...[
                    const SizedBox(height: 10),
                    Row(
                      children: [
                        Text(
                          'Skills',
                          style: context.tokens.typography.textTheme.bodySmall!.copyWith(
                            color: context.tokens.colors.textSecondary,
                          ),
                        ),
                        const Spacer(),
                        InkWell(
                          onTap: () => setDialogState(
                            () => selectedSkills = allSkills!.toSet(),
                          ),
                          child: Text(
                            'All',
                            style: context.tokens.typography.textTheme.bodySmall!.copyWith(
                              color: context.tokens.colors.accent,
                            ),
                          ),
                        ),
                        Text(' / ',
                            style: TextStyle(color: context.tokens.colors.textTertiary)),
                        InkWell(
                          onTap: () => setDialogState(
                            () => selectedSkills = {},
                          ),
                          child: Text(
                            'Clear',
                            style: context.tokens.typography.textTheme.bodySmall!.copyWith(
                              color: context.tokens.colors.accent,
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 4),
                    SizedBox(
                      height: 120,
                      child: ListView(
                        children: allSkills
                            .map(
                              (s) => CheckboxListTile(
                                dense: true,
                                value: selectedSkills.contains(s),
                                title: Text(
                                  s,
                              style: context.tokens.typography.textTheme.bodySmall!.copyWith(
                                fontSize: 12, color: context.tokens.colors.textSecondary,
                              ),
                                ),
                                onChanged: (v) {
                                  setDialogState(() {
                                    if (v == true) {
                                      selectedSkills = {
                                        ...selectedSkills,
                                        s,
                                      };
                                    } else {
                                      selectedSkills = selectedSkills
                                          .difference({s});
                                    }
                                  });
                                },
                              ),
                            )
                            .toList(),
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: submitting ? null : () => Navigator.pop(ctx),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: submitting
                  ? null
                  : () async {
                      setDialogState(() => submitting = true);
                      try {
                        await ref
                            .read(apiClientProvider)
                            .updateSubagent(
                              agent.name,
                              description: descriptionCtrl.text.trim(),
                              model: modelCtrl.text.trim().isEmpty
                                  ? null
                                  : modelCtrl.text.trim(),
                              systemPrompt: systemPromptCtrl.text.trim().isEmpty
                                  ? null
                                  : systemPromptCtrl.text.trim(),
                              maxLlmCalls: maxLlmCalls,
                              costLimitUsd: costLimitUsd,
                              timeoutSeconds: timeoutSeconds,
                              tools: selectedTools.length ==
                                      (allTools?.length ?? 0)
                                  ? null
                                  : selectedTools.toList(),
                              skills: selectedSkills.isEmpty
                                  ? null
                                  : selectedSkills.toList(),
                            );
                        if (ctx.mounted) Navigator.pop(ctx, true);
                        await _load();
                      } catch (e) {
                        if (!ctx.mounted) return;
                        setDialogState(() => submitting = false);
                        ScaffoldMessenger.of(ctx).showSnackBar(
                          SnackBar(content: Text('Update failed: $e')),
                        );
                      }
                    },
              child: submitting
                  ? const SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Text('Save'),
            ),
          ],
        ),
      ),
    );

    descriptionCtrl.dispose();
    modelCtrl.dispose();
    systemPromptCtrl.dispose();
  }

  void _confirmDelete(SubagentAgentDef agent) async {
    final wsId = ref.read(currentWorkspaceIdProvider);
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text('Delete subagent?', style: context.tokens.typography.textTheme.titleLarge?.copyWith(color: context.tokens.colors.textPrimary)),
        content: Text(
          'Delete ${agent.name}? This will also cancel any running jobs.',
          style: context.tokens.typography.textTheme.bodyMedium?.copyWith(color: context.tokens.colors.textPrimary),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    try {
      await ref
          .read(subagentProvider.notifier)
          .deleteAgent(agent.name, workspaceId: wsId);
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text('Delete failed: $e')));
    }
  }

}

class _SubagentTile extends ConsumerWidget {
  final SubagentAgentDef agent;
  final List<SubagentJob> runningJobs;
  final VoidCallback onStart;
  final VoidCallback onEdit;
  final VoidCallback onDelete;

  const _SubagentTile({
    required this.agent,
    required this.runningJobs,
    required this.onStart,
    required this.onEdit,
    required this.onDelete,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final hasRunning = runningJobs.isNotEmpty;
    final latestJob = hasRunning
        ? runningJobs.first
        : (runningJobs.isNotEmpty ? runningJobs.first : null);
    final statusLabel = hasRunning
        ? (runningJobs.first.status == 'cancelling' ? 'cancelling' : 'running')
        : 'idle';
    final progressMsg = latestJob?.progress?['message']?.toString();

    return ListTile(
      dense: true,
      onTap: onEdit,
      title: Row(
        children: [
          Expanded(
            child: Text(
              agent.name,
              style: context.tokens.typography.textTheme.bodyLarge!.copyWith(fontSize: 13, color: context.tokens.colors.textPrimary),
            ),
          ),
          _ScopeBadge(label: agent.scope),
          const SizedBox(width: 4),
          _StatusBadge(label: statusLabel),
        ],
      ),
      subtitle: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            agent.description.isEmpty ? 'No description' : agent.description,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: context.tokens.typography.textTheme.bodySmall!.copyWith(fontSize: 11, color: context.tokens.colors.textSecondary),
          ),
          if (progressMsg != null)
            Text(
              progressMsg,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: context.tokens.typography.textTheme.bodySmall!.copyWith(
                fontSize: 10,
                color: context.tokens.colors.accent,
              ),
            ),
        ],
      ),
      trailing: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (hasRunning)
            IconButton(
              tooltip: 'Cancel job',
              icon: const Icon(Symbols.stop_circle, size: 18),
              color: context.tokens.colors.warning,
              onPressed: () {
                ref
                    .read(subagentProvider.notifier)
                    .cancelJob(
                      runningJobs.first.jobId,
                      workspaceId: runningJobs.first.workspaceId,
                    );
              },
            )
          else
            IconButton(
              tooltip: 'Start task',
              icon: const Icon(Symbols.play_arrow, size: 18),
              onPressed: onStart,
            ),
          IconButton(
            tooltip: 'Edit',
            icon: const Icon(Symbols.edit, size: 18),
            onPressed: onEdit,
          ),
          if (!hasRunning)
            IconButton(
              tooltip: 'Delete',
              icon: const Icon(Symbols.delete, size: 18),
              onPressed: onDelete,
            ),
        ],
      ),
    );
  }
}

class _ScopeBadge extends StatelessWidget {
  final String label;

  const _ScopeBadge({required this.label});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(left: 4),
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: context.tokens.colors.accent.withAlpha(18),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        label == 'workspace' ? 'ws' : 'user',
        style: context.tokens.typography.textTheme.bodySmall!.copyWith(
          fontSize: 10,
          color: context.tokens.colors.accent,
        ),
      ),
    );
  }
}

class _StatusBadge extends StatelessWidget {
  final String label;

  const _StatusBadge({required this.label});

  Color _color(EaTokens tokens) {
    return switch (label) {
      'running' => tokens.colors.success,
      'cancelling' => tokens.colors.warning,
      'completed' => tokens.colors.accent,
      'failed' => tokens.colors.error,
      'cancelled' => tokens.colors.warning,
      _ => tokens.colors.textTertiary,
    };
  }

  @override
  Widget build(BuildContext context) {
    final tokens = context.tokens;
    final color = _color(tokens);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: color.withAlpha(18),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        label,
        style: tokens.typography.textTheme.bodySmall!.copyWith(fontSize: 10, color: color),
      ),
    );
  }
}

class _NumberField extends StatelessWidget {
  final String label;
  final num value;
  final bool isDouble;
  final ValueChanged<num> onChanged;

  const _NumberField({
    required this.label,
    required this.value,
    this.isDouble = false,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return TextField(
      controller: TextEditingController(text: value.toString())
        ..selection = TextSelection.collapsed(offset: value.toString().length),
      style: DefaultTextStyle.of(context).style.copyWith(fontSize: 13, color: context.tokens.colors.textPrimary),
      decoration: InputDecoration(
        labelText: label,
        isDense: true,
        contentPadding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
      ),
      keyboardType: TextInputType.numberWithOptions(
        decimal: isDouble,
        signed: false,
      ),
      onChanged: (s) {
        final parsed = isDouble ? double.tryParse(s) : int.tryParse(s);
        if (parsed != null && parsed > 0) onChanged(parsed);
      },
    );
  }
}


