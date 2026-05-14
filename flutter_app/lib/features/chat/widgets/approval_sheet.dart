import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../theme/app_theme.dart';
import '../../../models/message.dart';
import '../../../providers/agent_provider.dart';

class ApprovalSheet extends ConsumerWidget {
  final Map<String, ToolCallDisplay> pendingApprovals;

  const ApprovalSheet({super.key, required this.pendingApprovals});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (pendingApprovals.isEmpty) {
      // Pop immediately — don't leave a blank sheet open
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (Navigator.of(context).canPop()) {
          Navigator.of(context).pop();
        }
      });
      return const SizedBox.shrink();
    }
    final approvals = pendingApprovals.values.toList();

    return Container(
      decoration: BoxDecoration(
        color: AppColors.background,
        borderRadius: BorderRadius.vertical(
          top: Radius.circular(AppRadius.sheet),
        ),
      ),
      child: SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              margin: const EdgeInsets.only(top: 12),
              width: 40,
              height: 4,
              decoration: BoxDecoration(
                color: AppColors.textDim,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            Flexible(
              child: ListView.builder(
                shrinkWrap: true,
                itemCount: approvals.length,
                itemBuilder: (context, index) {
                  final tc = approvals[index];
                  return Padding(
                    padding: const EdgeInsets.all(AppSpacing.screenEdge),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        if (approvals.length > 1)
                          Padding(
                            padding: const EdgeInsets.only(bottom: AppSpacing.itemGap),
                            child: Text(
                              'Request ${index + 1} of ${approvals.length}',
                              style: AppTypography.caption.copyWith(
                                color: AppColors.textDim,
                              ),
                            ),
                          ),
                        Row(
                          children: [
                            Container(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 10,
                                vertical: 4,
                              ),
                              decoration: BoxDecoration(
                                color: AppColors.warning.withValues(alpha: 0.1),
                                borderRadius: BorderRadius.circular(AppRadius.chip),
                              ),
                              child: Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Icon(Icons.warning_amber,
                                      size: 14, color: AppColors.warning),
                                  const SizedBox(width: 4),
                                  Text(
                                    'Needs Approval',
                                    style: AppTypography.chip.copyWith(
                                      color: AppColors.warning,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: AppSpacing.componentDefault),
                        _ApprovalCard(tc: tc, ref: ref),
                        const SizedBox(height: AppSpacing.componentDefault),
                        _ApprovalActions(tc: tc, ref: ref),
                      ],
                    ),
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ApprovalCard extends StatelessWidget {
  final ToolCallDisplay tc;
  final WidgetRef ref;

  const _ApprovalCard({required this.tc, required this.ref});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppSpacing.cardPadding),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(AppRadius.card),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.build_circle_outlined,
                  size: 20, color: AppColors.accent),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  tc.toolName,
                  style: AppTypography.sectionTitle.copyWith(fontSize: 18),
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.itemGap),
          ...tc.args.entries.take(4).map(
            (entry) => Padding(
              padding: const EdgeInsets.only(bottom: AppSpacing.tightGap),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    entry.key,
                    style: AppTypography.caption.copyWith(
                      color: AppColors.textSecondary,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      '${entry.value}',
                      style: AppTypography.caption,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _ApprovalActions extends StatelessWidget {
  final ToolCallDisplay tc;
  final WidgetRef ref;

  const _ApprovalActions({required this.tc, required this.ref});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: OutlinedButton(
            onPressed: () {
              ref.read(agentProvider.notifier).rejectToolCall(tc.callId);
              Navigator.pop(context);
            },
            style: OutlinedButton.styleFrom(
              foregroundColor: AppColors.danger,
              side: const BorderSide(color: AppColors.danger),
              padding: const EdgeInsets.symmetric(vertical: 14),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(AppRadius.button),
              ),
            ),
            child: const Text('Reject'),
          ),
        ),
        const SizedBox(width: AppSpacing.itemGap),
        Expanded(
          child: FilledButton(
            onPressed: () {
              ref.read(agentProvider.notifier).approveToolCall(tc.callId);
              Navigator.pop(context);
            },
            style: FilledButton.styleFrom(
              backgroundColor: AppColors.accent,
              padding: const EdgeInsets.symmetric(vertical: 14),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(AppRadius.button),
              ),
            ),
            child: const Text('Approve'),
          ),
        ),
      ],
    );
  }
}