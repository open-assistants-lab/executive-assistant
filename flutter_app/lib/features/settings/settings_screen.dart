import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:http/http.dart' as http;
import 'package:executive_assistant/providers/agent_provider.dart';

class SettingsScreen extends ConsumerStatefulWidget {
  const SettingsScreen({super.key});

  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen> {
  String _host = '127.0.0.1';
  int _port = 8080;
  String _apiKey = '';
  String _selectedModel = 'deepseek:deepseek-v4-flash';
  String _selectedProvider = 'deepseek';
  Map<String, String> _providerKeys = {};
  Map<String, dynamic> _providers = {};
  bool _loadingModels = true;
  final _searchCtrl = TextEditingController();
  String _searchQuery = '';

  @override
  void initState() {
    super.initState();
    _load();
    _loadModels();
  }

  @override
  void dispose() {
    _searchCtrl.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    final prefs = await SharedPreferences.getInstance();
    final host = ref.read(hostProvider);
    // Load ALL provider keys from prefs (dynamic — all prefixed keys)
    final keys = <String, String>{};
    for (final key in prefs.getKeys()) {
      if (key.startsWith('ea_key_')) {
        final pid = key.substring(7);
        final val = prefs.getString(key);
        if (val != null && val.isNotEmpty) keys[pid] = val;
      }
    }
    final selectedModel =
        prefs.getString('ea_model') ?? 'deepseek:deepseek-v4-flash';
    final parts = selectedModel.split(':');
    final provider = parts.length > 1 ? parts[0] : 'deepseek';
    setState(() {
      _host = host.isNotEmpty ? host : '127.0.0.1';
      _port = 8080;
      _apiKey = prefs.getString('ea_api_key') ?? '';
      _selectedModel = selectedModel;
      _selectedProvider = provider;
      _providerKeys = keys;
    });
    // Sync to global state
    ref.read(selectedModelProvider.notifier).state = _selectedModel;
    ref.read(providerKeysProvider.notifier).state = Map<String, String>.from(
      _providerKeys,
    );
    ref.read(apiClientProvider).model = _selectedModel;
    ref.read(apiClientProvider).apiKey = _apiKey;
    ref.read(apiClientProvider).providerKeys = _providerKeys.isNotEmpty
        ? Map<String, String>.from(_providerKeys)
        : null;
    ref.read(agentProvider.notifier).updateModel(_selectedModel);
    ref
        .read(agentProvider.notifier)
        .updateProviderKeys(Map<String, String>.from(_providerKeys));
  }

  Future<void> _save() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('ea_api_key', _apiKey);
    await prefs.setString('ea_model', _selectedModel);
    for (final e in _providerKeys.entries) {
      await prefs.setString('ea_key_${e.key}', e.value);
    }
    // Sync to global state
    ref.read(selectedModelProvider.notifier).state = _selectedModel;
    ref.read(providerKeysProvider.notifier).state = Map<String, String>.from(
      _providerKeys,
    );
    ref.read(apiClientProvider).model = _selectedModel;
    ref.read(apiClientProvider).apiKey = _apiKey;
    ref.read(apiClientProvider).providerKeys = _providerKeys.isNotEmpty
        ? Map<String, String>.from(_providerKeys)
        : null;
    ref.read(agentProvider.notifier).updateModel(_selectedModel);
    ref
        .read(agentProvider.notifier)
        .updateProviderKeys(Map<String, String>.from(_providerKeys));
  }

  Future<void> _loadModels() async {
    try {
      final host = ref.read(hostProvider);
      final url = Uri.parse('http://$host/models');
      final resp = await http.get(url);
      if (resp.statusCode == 200) {
        final data = jsonDecode(resp.body) as Map<String, dynamic>;
        final providers = <String, dynamic>{};
        for (final p in data['providers'] ?? []) {
          providers[p['id']] = p;
        }
        setState(() {
          _providers = providers;
          _loadingModels = false;
        });
      }
    } catch (_) {
      setState(() => _loadingModels = false);
    }
  }

  List<MapEntry<String, dynamic>> get _filteredProviders {
    if (_providers.isEmpty) return [];
    final entries = _providers.entries.toList();
    if (_searchQuery.isEmpty) return entries;
    final q = _searchQuery.toLowerCase();
    return entries.where((e) {
      final name = (e.value['name'] ?? '').toString().toLowerCase();
      return name.contains(q);
    }).toList();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Settings'),
        leading: IconButton(
          icon: const Icon(Icons.close),
          onPressed: () => Navigator.of(context).pop(),
        ),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _sectionHeader('Server'),
          _tile('Host', _host, Icons.dns_outlined, readOnly: true),
          _tile('Port', '$_port', Icons.numbers_outlined, readOnly: true),
          _tile(
            'API Key',
            _apiKey.isEmpty ? 'Not set' : '••••••••',
            Icons.key_outlined,
            onTap: _editApiKey,
          ),
          const Divider(height: 32),

          _sectionHeader('Providers & Default Model'),
          TextField(
            controller: _searchCtrl,
            decoration: const InputDecoration(
              hintText: 'Search providers or models...',
              prefixIcon: Icon(Icons.search, size: 18),
              isDense: true,
              border: OutlineInputBorder(),
            ),
            onChanged: (v) => setState(() => _searchQuery = v),
          ),
          const SizedBox(height: 8),
          if (_loadingModels)
            const Center(child: CircularProgressIndicator())
          else if (_filteredProviders.isEmpty)
            const Center(child: Text('No providers found'))
          else
            ..._buildProviderList(),

          const Divider(height: 32),
          _sectionHeader('Connectors'),
          ListTile(
            leading: const Icon(Icons.mail_outlined),
            title: const Text('Google Workspace'),
            subtitle: const Text('Gmail, Drive, Calendar'),
            dense: true,
            trailing: TextButton(
              onPressed: _connectGws,
              child: const Text('Connect', style: TextStyle(fontSize: 12)),
            ),
          ),
          ListTile(
            leading: const Icon(Icons.cloud_outlined),
            title: const Text('Microsoft 365'),
            subtitle: const Text('Coming soon'),
            dense: true,
          ),
          const Divider(height: 32),
          _sectionHeader('Memory & Storage'),
          ListTile(
            leading: const Icon(Icons.delete_outline),
            title: const Text('Clear all memory'),
            onTap: _clearMemory,
            dense: true,
          ),
          const Divider(height: 32),
          _sectionHeader('About'),
          _tile('Version', '0.1.0', Icons.info_outline, readOnly: true),
          _tile('Default Model', _selectedModel, Icons.tag, readOnly: true),
          const SizedBox(height: 32),
        ],
      ),
    );
  }

  List<Widget> _buildProviderList() {
    return _filteredProviders.map((e) {
      final pid = e.key;
      final name = e.value['name'] ?? pid;
      final models = List<String>.from(e.value['models'] ?? []);
      final isActive = _selectedProvider == pid;

      return ExpansionTile(
        initiallyExpanded: isActive,
        leading: Icon(
          isActive ? Icons.radio_button_checked : Icons.radio_button_off,
          size: 18,
          color: isActive ? Theme.of(context).colorScheme.primary : Colors.grey,
        ),
        title: Text(name, style: const TextStyle(fontSize: 14)),
        subtitle: Text(
          '${models.length} models',
          style: const TextStyle(fontSize: 11),
        ),
        children: [
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 8),
            child: TextField(
              obscureText: true,
              decoration: const InputDecoration(
                hintText: 'API key',
                isDense: true,
                border: OutlineInputBorder(),
              ),
              style: const TextStyle(fontSize: 13),
              controller: TextEditingController(text: _providerKeys[pid] ?? ''),
              onChanged: (v) {
                _providerKeys[pid] = v;
                _save();
              },
            ),
          ),
          const SizedBox(height: 4),
          ...models.map((m) {
            final modelValue = '$pid:$m';
            return ListTile(
              title: Text(m, style: const TextStyle(fontSize: 12)),
              leading: Radio<String>(
                value: modelValue,
                groupValue: _selectedModel,
                onChanged: (v) {
                  setState(() {
                    _selectedModel = v!;
                    _selectedProvider = pid;
                  });
                  _save();
                },
              ),
              dense: true,
            );
          }),
        ],
      );
    }).toList();
  }

  Widget _sectionHeader(String title) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Text(
        title,
        style: TextStyle(
          fontSize: 13,
          fontWeight: FontWeight.w600,
          color: Theme.of(context).colorScheme.primary,
        ),
      ),
    );
  }

  Widget _tile(
    String title,
    String subtitle,
    IconData icon, {
    bool readOnly = false,
    VoidCallback? onTap,
    Color? color,
  }) {
    return ListTile(
      leading: Icon(icon, color: color),
      title: Text(title),
      subtitle: Text(subtitle, style: const TextStyle(fontSize: 12)),
      trailing: readOnly ? null : const Icon(Icons.chevron_right, size: 18),
      onTap: readOnly ? null : onTap,
      dense: true,
    );
  }

  void _editApiKey() {
    final ctrl = TextEditingController(text: _apiKey);
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Server API Key'),
        content: TextField(
          controller: ctrl,
          obscureText: true,
          decoration: const InputDecoration(
            hintText: 'API key for remote EA access',
            border: OutlineInputBorder(),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () {
              setState(() => _apiKey = ctrl.text);
              _save();
              Navigator.pop(ctx);
            },
            child: const Text('Save'),
          ),
        ],
      ),
    );
  }

  void _connectGws() {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Run gws auth login in terminal')),
    );
  }

  void _clearMemory() {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Clear all memory?'),
        content: const Text(
          'This deletes all conversation history and emails.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(ctx),
            style: FilledButton.styleFrom(backgroundColor: Colors.red),
            child: const Text('Delete all'),
          ),
        ],
      ),
    );
  }
}
