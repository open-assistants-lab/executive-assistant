import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../theme/app_theme.dart';
import '../../widgets/scope_switcher.dart';

class SubagentsSidebarPanel extends ConsumerStatefulWidget {
  const SubagentsSidebarPanel({super.key});

  @override
  ConsumerState<SubagentsSidebarPanel> createState() =>
      _SubagentsSidebarPanelState();
}

class _SubagentsSidebarPanelState extends ConsumerState<SubagentsSidebarPanel> {
  CapabilityScope _scope = CapabilityScope.workspace;

  @override
  Widget build(BuildContext context) {
    final tokens = context.tokens;
    return Container(
      color: tokens.colors.bgCanvas,
      child: Column(
        children: [
          Padding(
            padding: EdgeInsets.all(tokens.spacing.md),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Subagents',
                    style: tokens.typography.textTheme.titleLarge
                        ?.copyWith(color: tokens.colors.textPrimary)),
                SizedBox(height: tokens.spacing.sm),
                ScopeSwitcher(
                  scope: _scope,
                  onChanged: (s) => setState(() => _scope = s),
                ),
              ],
            ),
          ),
          Expanded(
            child: Center(
              child: Text('Subagent management coming soon',
                  style: tokens.typography.textTheme.bodyMedium
                      ?.copyWith(color: tokens.colors.textTertiary)),
            ),
          ),
        ],
      ),
    );
  }
}
