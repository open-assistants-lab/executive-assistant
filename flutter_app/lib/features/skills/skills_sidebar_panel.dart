import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../theme/app_theme.dart';

class SkillsSidebarPanel extends ConsumerStatefulWidget {
  const SkillsSidebarPanel({super.key});

  @override
  ConsumerState<SkillsSidebarPanel> createState() => _SkillsSidebarPanelState();
}

class _SkillsSidebarPanelState extends ConsumerState<SkillsSidebarPanel> {
  final _searchController = TextEditingController();

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final tokens = context.tokens;
    return Container(
      color: tokens.colors.bgCanvas,
      child: Column(
        children: [
          Padding(
            padding: EdgeInsets.fromLTRB(
                tokens.spacing.md,
                tokens.spacing.lg,
                tokens.spacing.md,
                tokens.spacing.md,
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(Symbols.psychology,
                        size: 18, color: tokens.colors.accent),
                    const SizedBox(width: 8),
                    Text('Skills',
                        style: tokens.typography.textTheme.titleLarge
                            ?.copyWith(color: tokens.colors.textPrimary)),
                    const Spacer(),
                  ],
                ),
                SizedBox(height: tokens.spacing.sm),
                TextField(
                  controller: _searchController,
                  decoration: const InputDecoration(
                    hintText: 'Search skills...',
                    prefixIcon: Icon(Symbols.search, size: 18),
                    isDense: true,
                  ),
                ),
              ],
            ),
          ),
          Expanded(
            child: Padding(
              padding: EdgeInsets.symmetric(horizontal: tokens.spacing.md),
              child: Center(
                child: Text('Skill management coming soon',
                    style: tokens.typography.textTheme.bodyMedium
                        ?.copyWith(color: tokens.colors.textTertiary)),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
