import 'package:flutter/material.dart';
import '../../theme/app_theme.dart';

enum CapabilityScope { user, workspace }

class ScopeSwitcher extends StatelessWidget {
  final CapabilityScope scope;
  final ValueChanged<CapabilityScope> onChanged;

  const ScopeSwitcher({
    super.key,
    required this.scope,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    final tokens = context.tokens;
    return SegmentedButton<CapabilityScope>(
      segments: const [
        ButtonSegment(
          value: CapabilityScope.user,
          label: Text('User'),
          icon: Icon(Symbols.person, size: 16),
        ),
        ButtonSegment(
          value: CapabilityScope.workspace,
          label: Text('Workspace'),
          icon: Icon(Symbols.folder, size: 16),
        ),
      ],
      selected: {scope},
      onSelectionChanged: (selected) => onChanged(selected.first),
      style: SegmentedButton.styleFrom(
        backgroundColor: tokens.colors.bgSurface,
        selectedBackgroundColor: tokens.colors.accent.withAlpha(30),
        selectedForegroundColor: tokens.colors.accent,
      ),
    );
  }
}
