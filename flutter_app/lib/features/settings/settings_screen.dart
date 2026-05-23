import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;
import '../../providers/agent_provider.dart';
import '../../theme/app_theme.dart';
import '../connectors/widgets/provider_card.dart';
import 'providers/settings_provider.dart';

class SettingsScreen extends ConsumerStatefulWidget {
  const SettingsScreen({super.key});

  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen> {
  bool _loadingSettings = true;
  bool _loadingProviders = true;
  List<Map<String, dynamic>> _providers = [];
  String _search = '';
  final _searchCtrl = TextEditingController();

  @override
  void initState() {
    super.initState();
    ref.read(settingsProvider.notifier).load().then((_) {
      if (mounted) setState(() => _loadingSettings = false);
    });
    _loadProviders();
  }

  @override
  void dispose() {
    _searchCtrl.dispose();
    super.dispose();
  }

  Future<void> _loadProviders() async {
    try {
      final host = ref.read(hostProvider);
      final resp = await http.get(Uri.parse('http://$host/models'));
      if (resp.statusCode == 200) {
        final data = jsonDecode(resp.body) as Map<String, dynamic>;
        final list = (data['providers'] as List? ?? [])
            .map((p) => p as Map<String, dynamic>)
            .toList();
        setState(() {
          _providers = list;
          _loadingProviders = false;
        });
        return;
      }
    } catch (_) {}
    setState(() => _loadingProviders = false);
  }

  List<Map<String, dynamic>> get _sortedProviders {
    final settings = ref.read(settingsProvider);
    var list = _providers;
    if (_search.isNotEmpty) {
      final q = _search.toLowerCase();
      list = list.where((p) {
        if ((p['name'] as String).toLowerCase().contains(q)) return true;
        final models = p['models'] as List? ?? [];
        return models.any((m) => m.toString().toLowerCase().contains(q));
      }).toList();
    }
    list.sort((a, b) {
      final aConnected = _isConnected(a, settings);
      final bConnected = _isConnected(b, settings);
      if (aConnected && !bConnected) return -1;
      if (!aConnected && bConnected) return 1;
      return (a['name'] as String).compareTo(b['name'] as String);
    });
    return list;
  }

  bool _isConnected(Map<String, dynamic> p, SettingsState settings) {
    final pid = p['id'] as String;
    return (settings.providerKeys.containsKey(pid) &&
            settings.providerKeys[pid]!.isNotEmpty) ||
        settings.providerKeyStatus[pid] == true;
  }

  @override
  Widget build(BuildContext context) {
    final tokens = context.tokens;
    final settings = ref.watch(settingsProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Settings', style: TextStyle(fontSize: 16)),
        leading: IconButton(
          icon: const Icon(Symbols.close, size: 20),
          onPressed: () => Navigator.of(context).pop(),
        ),
      ),
      body: _loadingSettings
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                _sectionHeader('Server', tokens),
                _tile('URL', settings.host, Symbols.dns, tokens: tokens),

                const SizedBox(height: 24),
                _sectionHeader('Default Model', tokens),
                _modelDropdown(settings, tokens),
                const SizedBox(height: 6),

                const SizedBox(height: 24),
                _sectionHeader('LLM Providers', tokens),
                TextField(
                  controller: _searchCtrl,
                  decoration: InputDecoration(
                    hintText: 'Search providers or models...',
                    prefixIcon: const Icon(Symbols.search, size: 18),
                    isDense: true,
                    border: const OutlineInputBorder(),
                    contentPadding: const EdgeInsets.symmetric(
                      horizontal: 12,
                      vertical: 10,
                    ),
                  ),
                  onChanged: (v) => setState(() => _search = v),
                ),
                const SizedBox(height: 8),
                if (_loadingProviders)
                  const Padding(
                    padding: EdgeInsets.all(24),
                    child: Center(child: CircularProgressIndicator()),
                  )
                else if (_sortedProviders.isEmpty)
                  Padding(
                    padding: const EdgeInsets.all(16),
                    child: Text(
                      _search.isNotEmpty ? 'No matches' : 'No providers loaded',
                      style: TextStyle(color: tokens.colors.textTertiary, fontSize: 13),
                    ),
                  )
                else
                  ..._sortedProviders.map((p) {
                    final pid = p['id'] as String;
                    final name = p['name'] as String? ?? pid;
                    final models = List<String>.from(p['models'] ?? []);
                    final hasKey =
                        (settings.providerKeys.containsKey(pid) &&
                                settings.providerKeys[pid]!.isNotEmpty) ||
                            settings.providerKeyStatus[pid] == true;
                    return ProviderCard(
                      providerId: pid,
                      providerName: name,
                      hasKey: hasKey,
                      models: models,
                      selectedModel: settings.defaultModel,
                    );
                  }),

                const SizedBox(height: 24),
                _sectionHeader('About', tokens),
                _tile('Version', '0.1.0', Symbols.info, tokens: tokens),
                _tile(
                  'Data Directory',
                  '~/Executive Assistant',
                  Symbols.folder,
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
    required var tokens,
  }) {
    return ListTile(
      leading: Icon(icon, size: 20, color: tokens.colors.textSecondary),
      title: Text(
        title,
        style: TextStyle(fontSize: 13, color: tokens.colors.textPrimary),
      ),
      subtitle: Text(
        subtitle,
        style: TextStyle(fontSize: 12, color: tokens.colors.textSecondary),
      ),
      dense: true,
    );
  }

  Widget _modelDropdown(SettingsState settings, var tokens) {
    final connectedProviders = _sortedProviders
        .where((p) => _isConnected(p, settings))
        .toList();

    if (connectedProviders.isEmpty) {
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Text(
          'No providers configured. Add an API key below to get started.',
          style: TextStyle(fontSize: 12, color: tokens.colors.textTertiary),
        ),
      );
    }

    final modelStr = settings.defaultModel;
    final items = <DropdownMenuItem<String>>[];

    for (final p in connectedProviders) {
      final pid = p['id'] as String;
      final name = p['name'] as String? ?? pid;
      final models = List<String>.from(p['models'] ?? []);

      items.add(DropdownMenuItem<String>(
        value: '__header__$pid',
        enabled: false,
        child: Text(
          name,
          style: TextStyle(
            fontWeight: FontWeight.w600,
            fontSize: 12,
            color: tokens.colors.textSecondary,
          ),
        ),
      ));

      for (final m in models) {
        final modelValue = '$pid:$m';
        items.add(DropdownMenuItem<String>(
          value: modelValue,
          child: Row(
            children: [
              Icon(
                modelValue == modelStr
                    ? Symbols.radio_button_checked
                    : Symbols.radio_button_unchecked,
                size: 14,
                color: modelValue == modelStr
                    ? tokens.colors.accent
                    : tokens.colors.textTertiary,
              ),
              const SizedBox(width: 8),
              Text(m, style: const TextStyle(fontSize: 13)),
            ],
          ),
        ));
      }
    }

    return DropdownButtonFormField<String>(
      initialValue: modelStr,
      isExpanded: true,
      decoration: const InputDecoration(
        isDense: true,
        border: OutlineInputBorder(),
        contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      ),
      items: items,
      onChanged: (v) {
        if (v != null && !v.startsWith('__header__')) {
          ref.read(settingsProvider.notifier).setDefaultModel(v);
        }
      },
    );
  }
}
