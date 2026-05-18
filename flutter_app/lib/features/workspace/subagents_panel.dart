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
      color: AppColors.background,
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
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: AppColors.divider)),
      ),
      child: Row(
        children: [
          Icon(Icons.smart_toy_outlined, size: 18, color: AppColors.accent),
          const SizedBox(width: 8),
          Text(
            'Subagents',
            style: AppTypography.sectionTitle.copyWith(fontSize: 15),
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
            style: AppTypography.caption.copyWith(color: AppColors.textDim),
          ),
          const SizedBox(width: 4),
          InkWell(
            onTap: _load,
            child: Icon(Icons.refresh, size: 16, color: AppColors.textDim),
          ),
          const SizedBox(width: 8),
          InkWell(
            onTap: _showCreateDialog,
            child: Icon(Icons.add, size: 18, color: AppColors.textDim),
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
                style: AppTypography.caption.copyWith(color: AppColors.danger),
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
            Icon(Icons.smart_toy_outlined, size: 40, color: AppColors.textDim),
            const SizedBox(height: 8),
            Text(
              'No subagents yet',
              style: AppTypography.caption.copyWith(color: AppColors.textDim),
            ),
            const SizedBox(height: 4),
            Text(
              'Create one from the panel or via chat',
              style: AppTypography.caption.copyWith(
                color: AppColors.textDim,
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
          onDetail: () => _showDetailDialog(agent),
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

    List<String>? allTools;
    try {
      allTools = await ref.read(apiClientProvider).listToolNames();
      selectedTools = allTools.toSet();
    } catch (_) {}
    if (!mounted) {
      nameCtrl.dispose();
      descriptionCtrl.dispose();
      modelCtrl.dispose();
      systemPromptCtrl.dispose();
      return;
    }

    final created = await showDialog<bool>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          title: const Text('Create Subagent'),
          content: SingleChildScrollView(
            child: SizedBox(
              width: 480,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  TextField(
                    controller: nameCtrl,
                    decoration: InputDecoration(
                      labelText: 'Name *',
                      hintText: 'my-researcher',
                      errorText: nameError,
                      border: const OutlineInputBorder(),
                    ),
                    onChanged: (_) =>
                        setDialogState(() => nameError = null),
                  ),
                  const SizedBox(height: 10),
                  TextField(
                    controller: descriptionCtrl,
                    decoration: const InputDecoration(
                      labelText: 'Description *',
                      hintText: 'Researches topics and summarizes',
                      border: OutlineInputBorder(),
                    ),
                    maxLines: 2,
                  ),
                  const SizedBox(height: 10),
                  Row(
                    children: [
                      Expanded(
                        child: _ScopeSelector(
                          value: scope,
                          onChanged: (v) => setDialogState(() => scope = v),
                          enabled: !submitting,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 10),
                  TextField(
                    controller: modelCtrl,
                    decoration: const InputDecoration(
                      labelText: 'Model',
                      hintText: 'deepseek:deepseek-v4-flash',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: 10),
                  TextField(
                    controller: systemPromptCtrl,
                    maxLines: 3,
                    decoration: const InputDecoration(
                      labelText: 'System prompt (optional)',
                      border: OutlineInputBorder(),
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
                              style: AppTypography.caption.copyWith(
                                color: AppColors.textSecondary,
                              ),
                            ),
                            const Spacer(),
                            InkWell(
                              onTap: () => setDialogState(
                                () => selectedTools = allTools!.toSet(),
                              ),
                              child: Text(
                                'All',
                                style: AppTypography.caption.copyWith(
                                  color: AppColors.accent,
                                ),
                              ),
                            ),
                            const Text(' / ',
                                style: TextStyle(color: AppColors.textDim)),
                            InkWell(
                              onTap: () => setDialogState(
                                () => selectedTools = {},
                              ),
                              child: Text(
                                'Clear',
                                style: AppTypography.caption.copyWith(
                                  color: AppColors.accent,
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
                                      style: AppTypography.caption.copyWith(
                                        fontSize: 12,
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

    await showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          title: Text('Start ${agent.name}'),
          content: SizedBox(
            width: 400,
            child: TextField(
              controller: taskCtrl,
              autofocus: true,
              minLines: 3,
              maxLines: 6,
              decoration: const InputDecoration(
                labelText: 'Task',
                hintText: 'What should the subagent do?',
                border: OutlineInputBorder(),
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

  void _showDetailDialog(SubagentAgentDef agent) {
    final state = ref.read(subagentProvider);
    final agentJobs =
        state.activeJobs.values.where((j) => j.agentName == agent.name).toList()
          ..sort((a, b) => (b.createdAt ?? '').compareTo(a.createdAt ?? ''));

    var selectedJobId = agentJobs.isNotEmpty ? agentJobs.first.jobId : null;

    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          titlePadding: const EdgeInsets.fromLTRB(20, 16, 8, 0),
          title: Row(
            children: [
              Expanded(
                child: Text(
                  agent.name,
                  style: AppTypography.sectionTitle.copyWith(fontSize: 18),
                ),
              ),
              IconButton(
                icon: const Icon(Icons.edit_outlined, size: 18),
                onPressed: () {
                  Navigator.pop(ctx);
                  _showEditDialog(agent);
                },
                tooltip: 'Edit',
              ),
              IconButton(
                icon: const Icon(Icons.close, size: 18),
                onPressed: () => Navigator.pop(ctx),
              ),
            ],
          ),
          content: SizedBox(
            width: 520,
            child: SingleChildScrollView(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  _DetailInfoRow(agent: agent),
                  const Divider(),
                  if (agentJobs.isEmpty)
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 16),
                      child: Center(
                        child: Text(
                          'No jobs yet',
                          style: AppTypography.caption.copyWith(
                            color: AppColors.textDim,
                          ),
                        ),
                      ),
                    )
                  else
                    ...agentJobs.map(
                      (job) => _JobCard(
                        job: job,
                        isSelected: job.jobId == selectedJobId,
                        onSelect: () =>
                            setDialogState(() => selectedJobId = job.jobId),
                        onCancel: () async {
                          await ref
                              .read(subagentProvider.notifier)
                              .cancelJob(
                                job.jobId,
                                workspaceId: job.workspaceId,
                              );
                        },
                        onInstruct: () => _showInstructDialog(job, ctx),
                      ),
                    ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      FilledButton.icon(
                        icon: const Icon(Icons.play_arrow, size: 16),
                        label: const Text('Start new task'),
                        onPressed: () {
                          Navigator.pop(ctx);
                          _showStartDialog(agent);
                        },
                      ),
                      const Spacer(),
                      OutlinedButton.icon(
                        icon: const Icon(Icons.delete_outline, size: 16),
                        label: const Text('Delete agent'),
                        onPressed: () {
                          Navigator.pop(ctx);
                          _confirmDelete(agent);
                        },
                        style: OutlinedButton.styleFrom(
                          foregroundColor: AppColors.danger,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
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

    await showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          title: Text('Edit ${agent.name}'),
          content: SingleChildScrollView(
            child: SizedBox(
              width: 480,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  TextField(
                    controller: descriptionCtrl,
                    decoration: const InputDecoration(
                      labelText: 'Description',
                      border: OutlineInputBorder(),
                    ),
                    maxLines: 2,
                  ),
                  const SizedBox(height: 10),
                  TextField(
                    controller: modelCtrl,
                    decoration: const InputDecoration(
                      labelText: 'Model',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: 10),
                  TextField(
                    controller: systemPromptCtrl,
                    maxLines: 3,
                    decoration: const InputDecoration(
                      labelText: 'System prompt (optional)',
                      border: OutlineInputBorder(),
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
        title: const Text('Delete subagent?'),
        content: Text(
          'Delete ${agent.name}? This will also cancel any running jobs.',
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

  Future<void> _showInstructDialog(
    SubagentJob job,
    BuildContext dialogCtx,
  ) async {
    final instructionCtrl = TextEditingController();
    var submitting = false;

    await showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          title: const Text('Send Instruction'),
          content: SizedBox(
            width: 400,
            child: TextField(
              controller: instructionCtrl,
              autofocus: true,
              minLines: 2,
              maxLines: 4,
              decoration: const InputDecoration(
                labelText: 'Instruction',
                hintText: 'e.g., focus on Sydney weather',
                border: OutlineInputBorder(),
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
                      final text = instructionCtrl.text.trim();
                      if (text.isEmpty) return;
                      setDialogState(() => submitting = true);
                      try {
                        await ref
                            .read(subagentProvider.notifier)
                            .instructJob(
                              job.jobId,
                              text,
                              workspaceId: job.workspaceId,
                            );
                        if (ctx.mounted) Navigator.pop(ctx);
                      } catch (e) {
                        if (!ctx.mounted) return;
                        setDialogState(() => submitting = false);
                        ScaffoldMessenger.of(ctx).showSnackBar(
                          SnackBar(content: Text('Instruct failed: $e')),
                        );
                      }
                    },
              child: submitting
                  ? const SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Text('Send'),
            ),
          ],
        ),
      ),
    );

    instructionCtrl.dispose();
  }
}

class _SubagentTile extends ConsumerWidget {
  final SubagentAgentDef agent;
  final List<SubagentJob> runningJobs;
  final VoidCallback onStart;
  final VoidCallback onDetail;
  final VoidCallback onDelete;

  const _SubagentTile({
    required this.agent,
    required this.runningJobs,
    required this.onStart,
    required this.onDetail,
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
      title: Row(
        children: [
          Expanded(
            child: Text(
              agent.name,
              style: AppTypography.body.copyWith(fontSize: 13),
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
            style: AppTypography.caption.copyWith(fontSize: 11),
          ),
          if (progressMsg != null)
            Text(
              progressMsg,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: AppTypography.caption.copyWith(
                fontSize: 10,
                color: AppColors.accent,
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
              icon: const Icon(Icons.stop_circle_outlined, size: 18),
              color: AppColors.warning,
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
              icon: const Icon(Icons.play_arrow_outlined, size: 18),
              onPressed: onStart,
            ),
          IconButton(
            tooltip: 'Details',
            icon: const Icon(Icons.visibility_outlined, size: 18),
            onPressed: onDetail,
          ),
          if (!hasRunning)
            IconButton(
              tooltip: 'Delete',
              icon: const Icon(Icons.delete_outline, size: 18),
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
        color: AppColors.accent.withAlpha(18),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        label == 'workspace' ? 'ws' : 'user',
        style: AppTypography.caption.copyWith(
          fontSize: 10,
          color: AppColors.accent,
        ),
      ),
    );
  }
}

class _StatusBadge extends StatelessWidget {
  final String label;

  const _StatusBadge({required this.label});

  Color _color() {
    switch (label) {
      case 'running':
        return AppColors.success;
      case 'cancelling':
        return AppColors.warning;
      case 'completed':
        return AppColors.accent;
      case 'failed':
        return AppColors.danger;
      case 'cancelled':
        return AppColors.warning;
      default:
        return AppColors.textDim;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: _color().withAlpha(18),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        label,
        style: AppTypography.caption.copyWith(fontSize: 10, color: _color()),
      ),
    );
  }
}

class _ScopeSelector extends StatelessWidget {
  final String value;
  final ValueChanged<String> onChanged;
  final bool enabled;

  const _ScopeSelector({
    required this.value,
    required this.onChanged,
    this.enabled = true,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        const Text('Scope:', style: TextStyle(fontSize: 13)),
        const SizedBox(width: 8),
        Radio<String>(
          value: 'user',
          groupValue: value,
          onChanged: enabled ? (v) => onChanged(v!) : null,
        ),
        const Text('User', style: TextStyle(fontSize: 13)),
        const SizedBox(width: 8),
        Radio<String>(
          value: 'workspace',
          groupValue: value,
          onChanged: enabled ? (v) => onChanged(v!) : null,
        ),
        const Text('Workspace', style: TextStyle(fontSize: 13)),
      ],
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
      decoration: InputDecoration(
        labelText: label,
        border: const OutlineInputBorder(),
        isDense: true,
        contentPadding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
      ),
      keyboardType: TextInputType.numberWithOptions(
        decimal: isDouble,
        signed: false,
      ),
      style: const TextStyle(fontSize: 13),
      onChanged: (s) {
        final parsed = isDouble ? double.tryParse(s) : int.tryParse(s);
        if (parsed != null && parsed > 0) onChanged(parsed);
      },
    );
  }
}

class _DetailInfoRow extends StatelessWidget {
  final SubagentAgentDef agent;

  const _DetailInfoRow({required this.agent});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            _ScopeBadge(label: agent.scope),
            const SizedBox(width: 8),
            if (agent.model != null)
              Text(
                agent.model!,
                style: AppTypography.caption.copyWith(fontSize: 11),
              ),
          ],
        ),
        if (agent.description.isNotEmpty) ...[
          const SizedBox(height: 4),
          Text(
            agent.description,
            style: AppTypography.body.copyWith(fontSize: 13),
          ),
        ],
        const SizedBox(height: 8),
        if (agent.tools != null)
          Wrap(
            spacing: 4,
            runSpacing: 2,
            children: agent.tools!
                .map(
                  (t) => Chip(
                    label: Text(t, style: const TextStyle(fontSize: 10)),
                    materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                    visualDensity: VisualDensity.compact,
                    padding: EdgeInsets.zero,
                    labelPadding: const EdgeInsets.symmetric(horizontal: 4),
                  ),
                )
                .toList(),
          ),
        const SizedBox(height: 4),
        Text(
          'Max calls: ${agent.maxLlmCalls}  |  Cost: \$${agent.costLimitUsd}  |  Timeout: ${agent.timeoutSeconds}s',
          style: AppTypography.caption.copyWith(fontSize: 10),
        ),
      ],
    );
  }
}

class _JobCard extends StatelessWidget {
  final SubagentJob job;
  final bool isSelected;
  final VoidCallback onSelect;
  final VoidCallback onCancel;
  final VoidCallback onInstruct;

  const _JobCard({
    required this.job,
    required this.isSelected,
    required this.onSelect,
    required this.onCancel,
    required this.onInstruct,
  });

  @override
  Widget build(BuildContext context) {
    final progress = job.progress;
    final phase = progress?['phase']?.toString();
    final message = progress?['message']?.toString();
    final steps = progress?['steps_completed'] as int?;

    return Card(
      margin: const EdgeInsets.symmetric(vertical: 4),
      color: isSelected ? AppColors.accentLight : null,
      child: InkWell(
        onTap: onSelect,
        borderRadius: BorderRadius.circular(8),
        child: Padding(
          padding: const EdgeInsets.all(10),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      job.task,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: AppTypography.body.copyWith(fontSize: 12),
                    ),
                  ),
                  _StatusBadge(label: job.status),
                ],
              ),
              const SizedBox(height: 4),
              if (phase != null || message != null) ...[
                Text(
                  phase != null && message != null
                      ? '$phase: $message'
                      : phase ?? message ?? '',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppTypography.caption.copyWith(fontSize: 11),
                ),
                const SizedBox(height: 2),
              ],
              if (steps != null)
                Text(
                  'Step $steps',
                  style: AppTypography.caption.copyWith(
                    fontSize: 10,
                    color: AppColors.textDim,
                  ),
                ),
              if (job.result != null && job.isTerminal)
                Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: Text(
                    job.result!.length > 100
                        ? '${job.result!.substring(0, 100)}...'
                        : job.result!,
                    style: AppTypography.caption.copyWith(
                      fontSize: 10,
                      color: AppColors.success,
                    ),
                  ),
                ),
              if (job.error != null && job.isTerminal)
                Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: Text(
                    job.error!,
                    style: AppTypography.caption.copyWith(
                      fontSize: 10,
                      color: AppColors.danger,
                    ),
                  ),
                ),
              if (job.instructions.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: Text(
                    '📝 ${job.instructions.length} instruction(s)',
                    style: AppTypography.caption.copyWith(
                      fontSize: 10,
                      color: AppColors.textDim,
                    ),
                  ),
                ),
              if (job.isRunning)
                Padding(
                  padding: const EdgeInsets.only(top: 6),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      TextButton.icon(
                        icon: const Icon(Icons.stop, size: 14),
                        label: const Text(
                          'Cancel',
                          style: TextStyle(fontSize: 11),
                        ),
                        onPressed: onCancel,
                        style: TextButton.styleFrom(
                          foregroundColor: AppColors.warning,
                          padding: const EdgeInsets.symmetric(
                            horizontal: 8,
                            vertical: 2,
                          ),
                        ),
                      ),
                      const SizedBox(width: 4),
                      TextButton.icon(
                        icon: const Icon(Icons.edit_note, size: 14),
                        label: const Text(
                          'Instruct',
                          style: TextStyle(fontSize: 11),
                        ),
                        onPressed: onInstruct,
                        style: TextButton.styleFrom(
                          foregroundColor: AppColors.accent,
                          padding: const EdgeInsets.symmetric(
                            horizontal: 8,
                            vertical: 2,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}
