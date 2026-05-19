import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../theme/app_theme.dart';
import '../../../models/message.dart';
import '../../../widgets/app_input.dart';
import '../../../providers/agent_provider.dart';
import 'model_switcher.dart';

class ChatInput extends ConsumerWidget {
  const ChatInput({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(agentProvider);
    final isSending =
        state.status == ChatStatus.streaming ||
        state.status == ChatStatus.awaitingApproval;
    final hasPendingApprovals = state.pendingApprovals.isNotEmpty;

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        if (hasPendingApprovals) _ApprovalBar(
          pendingApprovals: state.pendingApprovals,
          ref: ref,
        ),
        AppChatField(
          hint: state.connected ? 'Ask anything...' : 'Connecting...',
          enabled: state.connected,
          sending: isSending,
          onSend: (text) => ref.read(agentProvider.notifier).sendMessage(text),
          onCancel: isSending
              ? () => ref.read(agentProvider.notifier).cancelExecution()
              : null,
          onReconnect: !state.connected
              ? () => ref.read(agentProvider.notifier).connect()
              : null,
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(
            AppSpacing.cardPadding,
            8,
            AppSpacing.cardPadding,
            12,
          ),
          child: Row(children: const [ModelSwitcher(), Spacer()]),
        ),
      ],
    );
  }
}

class _ApprovalBar extends StatelessWidget {
  final Map<String, ToolCallDisplay> pendingApprovals;
  final WidgetRef ref;

  const _ApprovalBar({
    required this.pendingApprovals,
    required this.ref,
  });

  @override
  Widget build(BuildContext context) {
    final approvals = pendingApprovals.values.toList();
    return Container(
      margin: const EdgeInsets.fromLTRB(
        AppSpacing.cardPadding,
        4,
        AppSpacing.cardPadding,
        4,
      ),
      padding: const EdgeInsets.all(AppSpacing.cardPadding),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(AppRadius.card),
        border: Border.all(color: AppColors.warning.withValues(alpha: 0.4)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            children: [
              Icon(Icons.warning_amber, size: 16, color: AppColors.warning),
              const SizedBox(width: 6),
              Text(
                'Tool requires approval',
                style: AppTypography.caption.copyWith(
                  color: AppColors.warning,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          ...approvals.map((tc) => Padding(
            padding: const EdgeInsets.only(bottom: 4),
            child: Text(
              tc.toolName,
              style: AppTypography.sectionTitle.copyWith(fontSize: 15),
            ),
          )),
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(
                child: OutlinedButton(
                  onPressed: () {
                    for (final entry in approvals) {
                      ref.read(agentProvider.notifier).rejectToolCall(entry.callId);
                    }
                  },
                  style: OutlinedButton.styleFrom(
                    foregroundColor: AppColors.danger,
                    side: const BorderSide(color: AppColors.danger),
                    padding: const EdgeInsets.symmetric(vertical: 10),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(AppRadius.button),
                    ),
                  ),
                  child: const Text('Reject', style: TextStyle(fontSize: 13)),
                ),
              ),
              const SizedBox(width: AppSpacing.itemGap),
              Expanded(
                child: FilledButton(
                  onPressed: () {
                    for (final entry in approvals) {
                      ref.read(agentProvider.notifier).approveToolCall(entry.callId);
                    }
                  },
                  style: FilledButton.styleFrom(
                    backgroundColor: AppColors.accent,
                    padding: const EdgeInsets.symmetric(vertical: 10),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(AppRadius.button),
                    ),
                  ),
                  child: const Text('Approve', style: TextStyle(fontSize: 13)),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
