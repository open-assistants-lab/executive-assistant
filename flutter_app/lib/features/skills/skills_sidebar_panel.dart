import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../theme/app_theme.dart';
import '../../widgets/scope_switcher.dart';

class SkillsSidebarPanel extends ConsumerStatefulWidget {
  const SkillsSidebarPanel({super.key});

  @override
  ConsumerState<SkillsSidebarPanel> createState() => _SkillsSidebarPanelState();
}

class _SkillsSidebarPanelState extends ConsumerState<SkillsSidebarPanel> {
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
                Text('Skills',
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
              child: Text('Skill management coming soon',
                  style: tokens.typography.textTheme.bodyMedium
                      ?.copyWith(color: tokens.colors.textTertiary)),
            ),
          ),
        ],
      ),
    );
  }
}
