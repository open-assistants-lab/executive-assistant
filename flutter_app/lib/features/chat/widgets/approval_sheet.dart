import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../models/message.dart';
import '../../../providers/agent_provider.dart';
import '../../../theme/app_theme.dart';
import '../../../widgets/ea_button.dart';

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

    final tokens = context.tokens;
    final approvals = pendingApprovals.values.toList();

    return TweenAnimationBuilder<double>(
      duration: tokens.motion.moment,
      curve: tokens.motion.curveSpring,
      tween: Tween(begin: 0.0, end: 1.0),
      builder: (_, t, child) => Transform.translate(
        offset: Offset(0, 24 * (1 - t)),
        child: Opacity(opacity: t.clamp(0.0, 1.0), child: child),
      ),
      child: Container(
        decoration: BoxDecoration(
          color: tokens.colors.bgElevated,
          border: Border(
            top: BorderSide(color: tokens.colors.borderDefault),
            left: BorderSide(color: tokens.colors.accent, width: 3),
          ),
          borderRadius: BorderRadius.vertical(
            top: Radius.circular(tokens.radius.lg),
          ),
        ),
        child: SafeArea(
          top: false,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              // Drag handle
              Container(
                margin: EdgeInsets.only(top: tokens.spacing.md),
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: tokens.colors.borderDefault,
                  borderRadius: tokens.radius.fullAll,
                ),
              ),
              Flexible(
                child: ListView.builder(
                  shrinkWrap: true,
                  itemCount: approvals.length,
                  itemBuilder: (context, index) {
                    final tc = approvals[index];
                    return Padding(
                      padding: EdgeInsets.all(tokens.spacing.lg),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          if (approvals.length > 1)
                            Padding(
                              padding: EdgeInsets.only(bottom: tokens.spacing.sm),
                              child: Text(
                                'Request ${index + 1} of ${approvals.length}',
                                style: tokens.typography.textTheme.labelSmall?.copyWith(
                                  color: tokens.colors.textTertiary,
                                ),
                              ),
                            ),
                          // "Needs Approval" badge
                          Container(
                            padding: EdgeInsets.symmetric(
                              horizontal: tokens.spacing.sm + 2,
                              vertical: tokens.spacing.xs,
                            ),
                            decoration: BoxDecoration(
                              color: tokens.colors.warning.withValues(alpha: 0.12),
                              border: Border.all(
                                color: tokens.colors.warning.withValues(alpha: 0.3),
                                width: 1,
                              ),
                              borderRadius: tokens.radius.smAll,
                            ),
                            child: Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Icon(
                                  Symbols.warning,
                                  size: 12,
                                  color: tokens.colors.warning,
                                ),
                                SizedBox(width: tokens.spacing.xs + 2),
                                Text(
                                  'Needs Approval',
                                  style: tokens.typography.textTheme.labelMedium?.copyWith(
                                    color: tokens.colors.warning,
                                  ),
                                ),
                              ],
                            ),
                          ),
                          SizedBox(height: tokens.spacing.md),
                          _ApprovalCard(tc: tc),
                          SizedBox(height: tokens.spacing.md),
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
      ),
    );
  }
}

class _ApprovalCard extends StatelessWidget {
  final ToolCallDisplay tc;
  const _ApprovalCard({required this.tc});

  @override
  Widget build(BuildContext context) {
    final tokens = context.tokens;
    return Container(
      padding: EdgeInsets.all(tokens.spacing.md),
      decoration: BoxDecoration(
        color: tokens.colors.bgSurface,
        border: Border.all(color: tokens.colors.borderSubtle, width: 1),
        borderRadius: tokens.radius.mdAll,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                Symbols.build_circle,
                size: 16,
                color: tokens.colors.accent,
              ),
              SizedBox(width: tokens.spacing.sm),
              Expanded(
                child: Text(
                  tc.toolName,
                  style: tokens.typography.monoTheme.bodyMedium?.copyWith(
                    color: tokens.colors.textPrimary,
                  ),
                ),
              ),
            ],
          ),
          if (tc.args.isNotEmpty) ...[
            SizedBox(height: tokens.spacing.sm),
            ...tc.args.entries.take(4).map(
                  (entry) => Padding(
                padding: EdgeInsets.only(bottom: tokens.spacing.xs),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      entry.key,
                      style: tokens.typography.monoTheme.bodySmall?.copyWith(
                        color: tokens.colors.textTertiary,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    SizedBox(width: tokens.spacing.sm),
                    Expanded(
                      child: Text(
                        '${entry.value}',
                        style: tokens.typography.monoTheme.bodySmall?.copyWith(
                          color: tokens.colors.textSecondary,
                        ),
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
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
    final tokens = context.tokens;
    return Row(
      mainAxisAlignment: MainAxisAlignment.end,
      children: [
        EaButton.secondary(
          label: 'Reject',
          icon: Symbols.close,
          onPressed: () {
            ref.read(agentProvider.notifier).rejectToolCall(tc.callId);
            Navigator.pop(context);
          },
        ),
        SizedBox(width: tokens.spacing.sm),
        EaButton.primary(
          label: 'Approve',
          icon: Symbols.check,
          onPressed: () {
            ref.read(agentProvider.notifier).approveToolCall(tc.callId);
            Navigator.pop(context);
          },
        ),
      ],
    );
  }
}
