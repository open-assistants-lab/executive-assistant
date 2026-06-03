import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;
import '../../../theme/app_theme.dart';
import '../../../providers/agent_provider.dart';
import 'connect_auth_form.dart';

class ServicesTab extends ConsumerStatefulWidget {
  const ServicesTab({super.key, this.search, this.onSearchChanged});

  final String? search;
  final ValueChanged<String>? onSearchChanged;

  @override
  ConsumerState<ServicesTab> createState() => _ServicesTabState();
}

class _ServicesTabState extends ConsumerState<ServicesTab> {
  bool _loading = true;
  List<Map<String, dynamic>> _allConnectors = [];
  final Set<String> _connected = {};
  final String _search = '';
  String? _categoryFilter;

  String get _effectiveSearch => widget.search ?? _search;

  Set<String> get _categories {
    final cats = <String>{};
    for (final c in _allConnectors) {
      cats.add(c['category'] as String? ?? 'Other');
    }
    return cats;
  }

  List<Map<String, dynamic>> get _filtered {
    var list = _allConnectors;
    if (_categoryFilter != null) {
      list = list
          .where((c) =>
              (c['category'] as String? ?? 'Other') == _categoryFilter)
          .toList();
    }
    if (_effectiveSearch.isNotEmpty) {
      final q = _effectiveSearch.toLowerCase();
      list = list.where((c) {
        final name = (c['name'] as String? ?? '').toLowerCase();
        final desc = (c['description'] as String? ?? '').toLowerCase();
        return name.contains(q) || desc.contains(q);
      }).toList();
    }
    list.sort((a, b) {
      final aConn = _connected.contains(a['name']) ? 0 : 1;
      final bConn = _connected.contains(b['name']) ? 0 : 1;
      return aConn.compareTo(bConn);
    });
    return list;
  }

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final host = ref.read(hostProvider);
      final resp = await http.get(
        Uri.parse(
          'http://$host/connectors/catalog?user_id=default_user',
        ),
      );
      if (resp.statusCode == 200) {
        final list = (jsonDecode(resp.body) as List)
            .map((e) => e as Map<String, dynamic>)
            .toList();
        final connected = <String>{};
        for (final c in list) {
          if (c['connected'] == true) {
            connected.add(c['name'] as String);
          }
        }
        setState(() {
          _allConnectors = list;
          _connected.addAll(connected);
          _loading = false;
        });
        return;
      }
    } catch (_) {}
    setState(() => _loading = false);
  }

  @override
  Widget build(BuildContext context) {
    final tokens = context.tokens;

    return Column(
      children: [
        SizedBox(
          height: 36,
          child: ListView(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
            children: [
              _categoryChip(null, 'All', tokens),
              ..._categories.map((c) => _categoryChip(c, c, tokens)),
            ],
          ),
        ),
        Expanded(
          child: _loading
              ? const Center(child: CircularProgressIndicator())
              : _filtered.isEmpty
                  ? Center(
                      child: Text(
                        'No services',
                        style: TextStyle(color: tokens.colors.textTertiary),
                      ),
                    )
                  : ListView.builder(
                      itemCount: _filtered.length,
                      itemBuilder: (_, i) {
                        final c = _filtered[i];
                        final name = c['name'] as String;
                        final isConnected = _connected.contains(name);
                        return ListTile(
                          leading: Icon(
                            isConnected
                                ? Symbols.check_circle
                                : Symbols.lan,
                            size: 20,
                            color: isConnected
                                ? Colors.green
                                : tokens.colors.textSecondary,
                          ),
                          title: Text(
                            name,
                            style: const TextStyle(fontSize: 13),
                          ),
                          subtitle: Text(
                            c['description'] as String? ?? '',
                            style: TextStyle(
                              fontSize: 11,
                              color: tokens.colors.textTertiary,
                            ),
                          ),
                          trailing: isConnected
                              ? TextButton(
                                  onPressed: () => _disconnect(name),
                                  child: Text(
                                    'Disconnect',
                                    style: TextStyle(
                                      fontSize: 11,
                                      color: Colors.red,
                                    ),
                                  ),
                                )
                              : TextButton(
                                  onPressed: () =>
                                      _showConnectDialog(c),
                                  child: const Text(
                                    'Connect',
                                    style: TextStyle(fontSize: 11),
                                  ),
                                ),
                          dense: true,
                        );
                      },
                    ),
        ),
      ],
    );
  }

  Widget _categoryChip(
    String? category,
    String label,
    var tokens,
  ) {
    final isSelected = _categoryFilter == category;
    return Padding(
      padding: const EdgeInsets.only(right: 6),
      child: ChoiceChip(
        label: Text(label, style: const TextStyle(fontSize: 11)),
        selected: isSelected,
        onSelected: (_) => setState(() => _categoryFilter = category),
        visualDensity: VisualDensity.compact,
      ),
    );
  }

  void _showConnectDialog(Map<String, dynamic> spec) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        content: SizedBox(
          width: 400,
          child: ConnectAuthForm(
            spec: spec,
            onDone: () {
              setState(() => _connected.add(spec['name'] as String));
            },
          ),
        ),
      ),
    );
  }

  Future<void> _disconnect(String name) async {
    try {
      final host = ref.read(hostProvider);
      await http.delete(
        Uri.parse(
          'http://$host/connectors/disconnect?service=$name&user_id=default_user',
        ),
      );
      setState(() => _connected.remove(name));
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to disconnect: $e')),
        );
      }
    }
  }
}
