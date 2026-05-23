import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'providers/settings_provider.dart';
import '../../theme/app_theme.dart';

class SettingsScreen extends ConsumerStatefulWidget {
  final VoidCallback? onManageProviders;
  const SettingsScreen({super.key, this.onManageProviders});

  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen> {
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    ref.read(settingsProvider.notifier).load().then((_) {
      if (mounted) setState(() => _loading = false);
    });
  }

  @override
  Widget build(BuildContext context) {
    final tokens = context.tokens;
    final settings = ref.watch(settingsProvider);

    return Scaffold(
      appBar: AppBar(
        title: Text('Ajustes', style: const TextStyle(fontSize: 16)),
        leading: IconButton(
          icon: const Icon(Symbols.close, size: 20),
          onPressed: () => Navigator.of(context).pop(),
        ),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                _sectionHeader('Server', tokens),
                _tile(
                  'URL',
                  settings.host,
                  Symbols.dns,
                  readOnly: true,
                  tokens: tokens,
                ),

                const SizedBox(height: 24),
                _sectionHeader('Default Model', tokens),
                _modelDropdown(settings, tokens),
                const SizedBox(height: 6),
                Align(
                  alignment: Alignment.centerLeft,
                  child: TextButton.icon(
                    onPressed: widget.onManageProviders ?? () {
                      Navigator.of(context).pop();
                    },
                    icon: const Icon(Symbols.cable, size: 14),
                    label: const Text(
                      'Manage providers →',
                      style: TextStyle(fontSize: 12),
                    ),
                  ),
                ),

                const SizedBox(height: 24),
                _sectionHeader('About', tokens),
                _tile(
                  'Version',
                  '0.1.0',
                  Symbols.info,
                  readOnly: true,
                  tokens: tokens,
                ),
                _tile(
                  'Data Directory',
                  '~/Executive Assistant',
                  Symbols.folder,
                  readOnly: true,
                  tokens: tokens,
                ),

                const SizedBox(height: 24),
                Center(
                  child: FilledButton(
                    onPressed: () => Navigator.of(context).pop(),
                    child: const Text('Done'),
                  ),
                ),
                const SizedBox(height: 24),
              ],
            ),
    );
  }

  Widget _sectionHeader(String title, var tokens) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Text(
        title,
        style: TextStyle(
          fontSize: 13,
          fontWeight: FontWeight.w600,
          color: tokens.colors.accent,
        ),
      ),
    );
  }

  Widget _tile(
    String title,
    String subtitle,
    IconData icon, {
    bool readOnly = false,
    required var tokens,
  }) {
    return ListTile(
      leading: Icon(icon, size: 20, color: tokens.colors.textSecondary),
      title: Text(
        title,
        style: TextStyle(
          fontSize: 13,
          color: tokens.colors.textPrimary,
        ),
      ),
      subtitle: Text(
        subtitle,
        style: TextStyle(
          fontSize: 12,
          color: tokens.colors.textSecondary,
        ),
      ),
      dense: true,
    );
  }

  Widget _modelDropdown(SettingsState settings, var tokens) {
    if (settings.providerKeys.isEmpty &&
        settings.providerKeyStatus.isEmpty) {
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Text(
          'No providers configured. Click "Manage providers" to add one.',
          style: TextStyle(
            fontSize: 12,
            color: tokens.colors.textTertiary,
          ),
        ),
      );
    }

    final modelStr = settings.defaultModel;
    final parts = modelStr.split(':');
    final currentModelName = parts.length > 1
        ? parts.sublist(1).join(':')
        : modelStr;

    return DropdownButtonFormField<String>(
      initialValue: modelStr,
      isExpanded: true,
      decoration: const InputDecoration(
        isDense: true,
        border: OutlineInputBorder(),
        contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      ),
      items: [
        DropdownMenuItem(
          value: modelStr,
          child: Text(
            currentModelName,
            style: const TextStyle(fontSize: 13),
          ),
        ),
      ],
      onChanged: (v) {
        if (v != null) {
          ref.read(settingsProvider.notifier).setDefaultModel(v);
        }
      },
    );
  }
}
