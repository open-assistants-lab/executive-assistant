import 'package:flutter/material.dart';
import '../../theme/app_theme.dart';
import 'widgets/services_tab.dart';

class ConnectorsModal extends StatefulWidget {
  const ConnectorsModal({super.key});

  @override
  State<ConnectorsModal> createState() => _ConnectorsModalState();
}

class _ConnectorsModalState extends State<ConnectorsModal> {
  String _search = '';
  final _searchCtrl = TextEditingController();

  @override
  void dispose() {
    _searchCtrl.dispose();
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
                    Icon(Symbols.cable,
                        size: 18, color: tokens.colors.accent),
                    const SizedBox(width: 8),
                    Text('Connection',
                        style: tokens.typography.textTheme.titleLarge
                            ?.copyWith(color: tokens.colors.textPrimary)),
                    const Spacer(),
                  ],
                ),
                SizedBox(height: tokens.spacing.sm),
                TextField(
                  controller: _searchCtrl,
                  decoration: const InputDecoration(
                    hintText: 'Search services...',
                    prefixIcon: Icon(Symbols.search, size: 18),
                    isDense: true,
                  ),
                  onChanged: (v) => setState(() => _search = v),
                ),
              ],
            ),
          ),
          Expanded(
            child: Padding(
              padding: EdgeInsets.symmetric(horizontal: tokens.spacing.md),
              child: ServicesTab(
                search: _search,
                onSearchChanged: (v) {
                  _searchCtrl.text = v;
                  setState(() => _search = v);
                },
              ),
            ),
          ),
        ],
      ),
    );
  }
}
