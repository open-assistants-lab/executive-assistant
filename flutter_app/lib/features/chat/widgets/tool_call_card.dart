import 'package:flutter/material.dart';
import '../../../models/message.dart';
import '../../../theme/app_theme.dart';

class ToolCallCard extends StatefulWidget {
  final ToolCallDisplay toolCall;
  const ToolCallCard({super.key, required this.toolCall});

  @override
  State<ToolCallCard> createState() => _ToolCallCardState();
}

class _ToolCallCardState extends State<ToolCallCard> {
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
    final tokens = context.tokens;
    final hasArgs = widget.toolCall.args.isNotEmpty;
    return Padding(
      padding: EdgeInsets.symmetric(vertical: tokens.spacing.xs),
      child: Container(
        decoration: BoxDecoration(
          color: tokens.colors.bgSurface,
          border: Border.all(color: tokens.colors.borderSubtle, width: 1),
          borderRadius: tokens.radius.mdAll,
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Material(
              color: Colors.transparent,
              child: InkWell(
                onTap: hasArgs ? () => setState(() => _expanded = !_expanded) : null,
                borderRadius: tokens.radius.mdAll,
                child: Padding(
                  padding: EdgeInsets.symmetric(
                    horizontal: tokens.spacing.md,
                    vertical: tokens.spacing.md - 2,
                  ),
                  child: Row(
                    children: [
                      Icon(
                        _iconFor(widget.toolCall.toolName),
                        size: 14,
                        color: tokens.colors.accent,
                      ),
                      SizedBox(width: tokens.spacing.sm),
                      Flexible(
                        child: Text(
                          widget.toolCall.toolName,
                          style: tokens.typography.monoTheme.bodySmall?.copyWith(
                            color: tokens.colors.textPrimary,
                          ),
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      SizedBox(width: tokens.spacing.sm),
                      _StatusBadge(hasResult: widget.toolCall.resultPreview != null),
                    ],
                  ),
                ),
              ),
            ),
            AnimatedSize(
              duration: tokens.motion.base,
              curve: tokens.motion.curveStandard,
              alignment: Alignment.topCenter,
              child: _expanded && hasArgs
                  ? Padding(
                      padding: EdgeInsets.fromLTRB(
                        tokens.spacing.md,
                        0,
                        tokens.spacing.md,
                        tokens.spacing.md,
                      ),
                      child: SelectableText(
                        _formatArgs(widget.toolCall.args),
                        style: tokens.typography.monoTheme.bodySmall?.copyWith(
                          color: tokens.colors.textSecondary,
                        ),
                      ),
                    )
                  : const SizedBox.shrink(),
            ),
          ],
        ),
      ),
    );
  }

  IconData _iconFor(String name) {
    if (name.startsWith('email_')) return Symbols.mail;
    if (name.startsWith('files_')) return Symbols.folder;
    if (name.startsWith('contacts_')) return Symbols.person;
    if (name.startsWith('todos_')) return Symbols.check_box;
    if (name.startsWith('memory_')) return Symbols.memory;
    if (name.startsWith('shell_')) return Symbols.terminal;
    if (name.startsWith('browser_')) return Symbols.public;
    if (name.startsWith('subagent_')) return Symbols.workspaces;
    if (name.startsWith('skills_') || name.startsWith('skill_')) return Symbols.lightbulb;
    if (name.startsWith('mcp_') || name.startsWith('mcp__')) return Symbols.extension;
    if (name.startsWith('firecrawl') || name.startsWith('scrape_') || name.startsWith('search_')) return Symbols.travel_explore;
    if (name.startsWith('time_')) return Symbols.schedule;
    return Symbols.build;
  }

  String _formatArgs(Map<String, dynamic> args) {
    final entries = args.entries.map((e) => '${e.key}: ${e.value}').toList();
    return entries.join('\n');
  }
}

class _StatusBadge extends StatelessWidget {
  final bool hasResult;
  const _StatusBadge({required this.hasResult});

  @override
  Widget build(BuildContext context) {
    final tokens = context.tokens;
    if (hasResult) {
      return Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Symbols.check, size: 12, color: tokens.colors.textSecondary),
          SizedBox(width: tokens.spacing.xs + 2),
          Text(
            'Done',
            style: tokens.typography.textTheme.labelMedium?.copyWith(
              color: tokens.colors.textSecondary,
            ),
          ),
        ],
      );
    }
    // Running
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 6,
          height: 6,
          decoration: BoxDecoration(
            color: tokens.colors.accent,
            borderRadius: tokens.radius.fullAll,
          ),
        ),
        SizedBox(width: tokens.spacing.xs + 2),
        Text(
          'Running',
          style: tokens.typography.textTheme.labelMedium?.copyWith(
            color: tokens.colors.accent,
          ),
        ),
      ],
    );
  }
}
