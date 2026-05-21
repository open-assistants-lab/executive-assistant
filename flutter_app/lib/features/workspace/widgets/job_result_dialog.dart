import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../models/subagent.dart';
import '../../../theme/app_theme.dart';

class JobResultDialog extends ConsumerWidget {
  final SubagentJob job;

  const JobResultDialog({super.key, required this.job});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = context.tokens;
    final isRunning = job.isRunning;
    final statusColor = switch (job.status) {
      'completed' => t.colors.success,
      'failed' => t.colors.error,
      'cancelled' => t.colors.warning,
      'running' => t.colors.accent,
      'cancelling' => t.colors.warning,
      _ => t.colors.textTertiary,
    };

    return Dialog(
      insetPadding: const EdgeInsets.symmetric(horizontal: 32, vertical: 24),
      child: SizedBox(
        width: 600,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 16, 12, 8),
              child: Row(
                children: [
                  Expanded(
                    child: Text(
                      'Job Result',
                      style: t.typography.textTheme.titleLarge?.copyWith(
                        color: t.colors.textPrimary,
                      ),
                    ),
                  ),
                  IconButton(
                    icon: Icon(Symbols.close, size: 18, color: t.colors.textSecondary),
                    onPressed: () => Navigator.pop(context),
                  ),
                ],
              ),
            ),
            // Metadata row
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: Wrap(
                spacing: 16,
                runSpacing: 6,
                children: [
                  _metaChip(context, 'Status', job.status, statusColor),
                  if (job.startedAt != null && job.completedAt != null)
                    _metaChip(context, 'Duration', _formatDuration(job.startedAt!, job.completedAt!), t.colors.textSecondary),
                  _metaChip(context, 'Agent', job.agentName, t.colors.accent),
                  if (job.result?.isNotEmpty == true && job.result!.contains('llm_calls'))
                    _metaChip(context, 'LLM calls', _extractField(job.result!, 'llm_calls'), t.colors.textSecondary),
                  if (job.result?.isNotEmpty == true && job.result!.contains('cost_usd'))
                    _metaChip(context, 'Cost', '\$${_extractField(job.result!, 'cost_usd')}', t.colors.textSecondary),
                  if (job.createdAt != null)
                    _metaChip(context, 'Created', job.createdAt!, t.colors.textTertiary),
                ],
              ),
            ),
            const Divider(height: 24),
            // Task section
            if (job.task.isNotEmpty) ...[
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                child: Text('Task',
                  style: t.typography.textTheme.labelLarge?.copyWith(
                    color: t.colors.textSecondary,
                  )),
              ),
              const SizedBox(height: 4),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                child: Text(
                  job.task,
                  style: t.typography.textTheme.bodyMedium?.copyWith(
                    color: t.colors.textPrimary,
                  ),
                  maxLines: 3,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              const SizedBox(height: 12),
            ],
            // Output section (scrollable, monospace)
            if (job.result != null && job.result!.isNotEmpty) ...[
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                child: Text('Output',
                  style: t.typography.textTheme.labelLarge?.copyWith(
                    color: t.colors.textSecondary,
                  )),
              ),
              const SizedBox(height: 4),
              Container(
                margin: const EdgeInsets.symmetric(horizontal: 20),
                padding: const EdgeInsets.all(12),
                constraints: const BoxConstraints(maxHeight: 300),
                decoration: BoxDecoration(
                  color: t.colors.bgElevated,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: t.colors.borderSubtle),
                ),
                child: SingleChildScrollView(
                  child: SelectableText(
                    job.result!,
                    style: TextStyle(
                      fontFamily: 'monospace',
                      fontSize: 12,
                      color: t.colors.textPrimary,
                      height: 1.4,
                    ),
                  ),
                ),
              ),
            ],
            // Error section (conditional)
            if (job.error != null && job.error!.isNotEmpty) ...[
              const SizedBox(height: 12),
              Container(
                margin: const EdgeInsets.symmetric(horizontal: 20),
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: t.colors.error.withAlpha(18),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: t.colors.error.withAlpha(60)),
                ),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(Symbols.error, size: 16, color: t.colors.error),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        job.error!,
                        style: TextStyle(
                          fontFamily: 'monospace',
                          fontSize: 12,
                          color: t.colors.error,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ],
            // Progress section (conditional, for running jobs)
            if (isRunning && job.progress != null) ...[
              const SizedBox(height: 12),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                child: Row(
                  children: [
                    SizedBox(
                      width: 14, height: 14,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: t.colors.accent,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Text(
                      job.progress!['message']?.toString() ?? 'Running...',
                      style: t.typography.textTheme.bodySmall?.copyWith(
                        color: t.colors.textSecondary,
                      ),
                    ),
                  ],
                ),
              ),
            ],
            const SizedBox(height: 20),
            // Close button
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 0, 20, 16),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  FilledButton(
                    onPressed: () => Navigator.pop(context),
                    child: const Text('Close'),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _metaChip(BuildContext context, String label, String value, Color color) {
    final t = context.tokens;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withAlpha(18),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(
        '$label: $value',
        style: TextStyle(fontSize: 11, color: color),
      ),
    );
  }

  String _formatDuration(String start, String end) {
    try {
      final s = DateTime.parse(start);
      final e = DateTime.parse(end);
      final diff = e.difference(s);
      if (diff.inSeconds < 60) return '${diff.inSeconds}s';
      return '${diff.inMinutes}m ${diff.inSeconds % 60}s';
    } catch (_) {
      return '';
    }
  }

  String _extractField(String jsonStr, String field) {
    try {
      final regex = RegExp('"$field"\\s*:\\s*([\\d.]+)');
      final match = regex.firstMatch(jsonStr);
      return match?.group(1) ?? '';
    } catch (_) {
      return '';
    }
  }
}
