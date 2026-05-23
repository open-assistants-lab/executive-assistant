import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;
import '../../../theme/app_theme.dart';
import '../../../providers/agent_provider.dart';
import '../../settings/providers/settings_provider.dart';
import 'provider_card.dart';

class LlmProvidersTab extends ConsumerStatefulWidget {
  const LlmProvidersTab({super.key});

  @override
  ConsumerState<LlmProvidersTab> createState() => _LlmProvidersTabState();
}

class _LlmProvidersTabState extends ConsumerState<LlmProvidersTab> {
  bool _loading = true;
  List<Map<String, dynamic>> _providers = [];
  String _search = '';
  final _searchCtrl = TextEditingController();

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _searchCtrl.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final host = ref.read(hostProvider);
      final resp = await http.get(Uri.parse('http://$host/models'));
      if (resp.statusCode == 200) {
        final data = jsonDecode(resp.body) as Map<String, dynamic>;
        final list = (data['providers'] as List? ?? [])
            .map((p) => p as Map<String, dynamic>)
            .toList();
        list.sort((a, b) =>
            (a['name'] as String).compareTo(b['name'] as String));
        setState(() {
          _providers = list;
          _loading = false;
        });
        return;
      }
    } catch (_) {}
    setState(() => _loading = false);
  }

  List<Map<String, dynamic>> get _filtered {
    if (_search.isEmpty) return _providers;
    final q = _search.toLowerCase();
    return _providers.where((p) {
      if ((p['name'] as String).toLowerCase().contains(q)) return true;
      final models = p['models'] as List? ?? [];
      return models.any((m) => m.toString().toLowerCase().contains(q));
    }).toList();
  }

  @override
  Widget build(BuildContext context) {
    final tokens = context.tokens;
    final settings = ref.watch(settingsProvider);

    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 12, 12, 8),
          child: TextField(
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
        ),
        Expanded(
          child: _loading
              ? const Center(child: CircularProgressIndicator())
              : _filtered.isEmpty
                  ? Center(
                      child: Text(
                        _search.isNotEmpty
                            ? 'No matches'
                            : 'No providers loaded',
                        style: TextStyle(color: tokens.colors.textTertiary),
                      ),
                    )
                  : ListView.builder(
                      itemCount: _filtered.length,
                      itemBuilder: (_, i) {
                        final p = _filtered[i];
                        final pid = p['id'] as String;
                        final name = p['name'] as String? ?? pid;
                        final models =
                            List<String>.from(p['models'] ?? []);
                        final hasKey =
                            (settings.providerKeys.containsKey(pid) &&
                                    settings
                                        .providerKeys[pid]!.isNotEmpty) ||
                                settings.providerKeyStatus[pid] == true;
                        return ProviderCard(
                          providerId: pid,
                          providerName: name,
                          hasKey: hasKey,
                          models: models,
                          selectedModel: settings.defaultModel,
                        );
                      },
                    ),
        ),
      ],
    );
  }
}
