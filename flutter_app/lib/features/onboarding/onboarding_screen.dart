import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;
import '../../providers/agent_provider.dart';
import '../../theme/app_theme.dart';
import '../settings/providers/settings_provider.dart';
import 'onboarding_provider.dart';

class OnboardingScreen extends ConsumerStatefulWidget {
  const OnboardingScreen({super.key});

  @override
  ConsumerState<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends ConsumerState<OnboardingScreen> {
  int _step = 0;
  bool _loading = true;
  List<Map<String, dynamic>> _providers = [];
  String? _selectedProvider;
  final _keyCtrl = TextEditingController();
  bool _testing = false;
  bool? _testResult;
  String? _testError;

  @override
  void initState() {
    super.initState();
    _loadProviders();
  }

  @override
  void dispose() {
    _keyCtrl.dispose();
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
        list.sort(
          (a, b) => (a['name'] as String).compareTo(b['name'] as String),
        );
        setState(() {
          _providers = list;
          _loading = false;
        });
        return;
      }
    } catch (_) {}
    if (!mounted) return;
    setState(() => _loading = false);
  }

  Future<void> _testKey() async {
    final key = _keyCtrl.text.trim();
    if (key.isEmpty || _selectedProvider == null) return;

    setState(() {
      _testing = true;
      _testResult = null;
      _testError = null;
    });

    try {
      final host = ref.read(hostProvider);
      final resp = await http.post(
        Uri.parse('http://$host/settings/test-key'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'provider': _selectedProvider,
          'api_key': key,
        }),
      );
      final data = jsonDecode(resp.body) as Map<String, dynamic>;
      if (!mounted) return;
      setState(() {
        _testing = false;
        _testResult = data['valid'] == true;
        _testError = data['error'] as String?;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _testing = false;
        _testResult = false;
        _testError = 'Could not reach backend: $e';
      });
    }
  }

  Future<void> _finish() async {
    if (_selectedProvider != null && _keyCtrl.text.trim().isNotEmpty) {
      final settings = ref.read(settingsProvider.notifier);
      await settings.setApiKey(_selectedProvider!, _keyCtrl.text.trim());
    }
    await ref.read(onboardingCompleteProvider.notifier).complete();
  }

  String? _providerName(String? id) {
    if (id == null) return null;
    for (final p in _providers) {
      if (p['id'] == id) return p['name'] as String? ?? id;
    }
    return id;
  }

  @override
  Widget build(BuildContext context) {
    final tokens = context.tokens;

    return Scaffold(
      backgroundColor: tokens.colors.bgCanvas,
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 520),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 48),
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : _buildContent(tokens),
          ),
        ),
      ),
    );
  }

  Widget _buildContent(EaTokens tokens) {
    return switch (_step) {
      0 => _buildWelcome(tokens),
      1 => _buildApiKeyStep(tokens),
      _ => _buildDoneStep(tokens),
    };
  }

  Widget _buildWelcome(EaTokens tokens) {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(Symbols.assistant, size: 48, color: tokens.colors.accent),
        const SizedBox(height: 24),
        Text(
          'Welcome to\nExecutive Assistant',
          style: tokens.typography.textTheme.headlineMedium?.copyWith(
            color: tokens.colors.textPrimary,
            fontWeight: FontWeight.w600,
          ),
        ),
        const SizedBox(height: 12),
        Text(
          'Your AI-powered assistant for email, tasks, research, and more. '
          'Let\'s get you set up in under a minute.',
          style: tokens.typography.textTheme.bodyMedium?.copyWith(
            color: tokens.colors.textSecondary,
          ),
        ),
        const SizedBox(height: 32),
        Text(
          'Choose your AI provider',
          style: tokens.typography.textTheme.titleSmall?.copyWith(
            color: tokens.colors.textPrimary,
          ),
        ),
        const SizedBox(height: 8),
        Expanded(
          child: _providers.isEmpty
              ? Center(
                  child: Text(
                    'No providers available.\nMake sure the backend is running.',
                    textAlign: TextAlign.center,
                    style: TextStyle(color: tokens.colors.textTertiary),
                  ),
                )
              : ListView.builder(
                  itemCount: _providers.length,
                  itemBuilder: (_, i) {
                    final p = _providers[i];
                    final pid = p['id'] as String;
                    final name = p['name'] as String? ?? pid;
                    final selected = _selectedProvider == pid;
                    return Card(
                      margin: const EdgeInsets.symmetric(vertical: 3),
                      color: selected
                          ? tokens.colors.accent.withAlpha(25)
                          : null,
                      child: ListTile(
                        leading: Icon(
                          selected
                              ? Symbols.radio_button_checked
                              : Symbols.radio_button_unchecked,
                          size: 20,
                          color: selected
                              ? tokens.colors.accent
                              : tokens.colors.textTertiary,
                        ),
                        title: Text(
                          name,
                          style: const TextStyle(fontSize: 14),
                        ),
                        subtitle: Text(
                          '${(p['models'] as List?)?.length ?? 0} models',
                          style: TextStyle(
                            fontSize: 11,
                            color: tokens.colors.textTertiary,
                          ),
                        ),
                        onTap: () => setState(() => _selectedProvider = pid),
                        dense: true,
                      ),
                    );
                  },
                ),
        ),
        const SizedBox(height: 16),
        SizedBox(
          width: double.infinity,
          child: FilledButton(
            onPressed: _selectedProvider == null
                ? null
                : () => setState(() => _step = 1),
            child: const Text('Next'),
          ),
        ),
      ],
    );
  }

  Widget _buildApiKeyStep(EaTokens tokens) {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            IconButton(
              icon: const Icon(Symbols.arrow_back, size: 20),
              onPressed: () => setState(() => _step = 0),
              visualDensity: VisualDensity.compact,
            ),
            const SizedBox(width: 4),
            Expanded(
              child: Text(
                'Enter API Key',
                style: tokens.typography.textTheme.titleMedium?.copyWith(
                  color: tokens.colors.textPrimary,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        Text(
          'Your key is stored locally and never shared.',
          style: tokens.typography.textTheme.bodySmall?.copyWith(
            color: tokens.colors.textSecondary,
          ),
        ),
        const SizedBox(height: 24),
        Text(
          'Provider: ${_providerName(_selectedProvider)}',
          style: tokens.typography.textTheme.titleSmall?.copyWith(
            color: tokens.colors.textPrimary,
          ),
        ),
        const SizedBox(height: 12),
        TextField(
          controller: _keyCtrl,
          obscureText: true,
          decoration: InputDecoration(
            hintText: 'Paste your API key here',
            border: const OutlineInputBorder(),
            isDense: true,
            contentPadding: const EdgeInsets.symmetric(
              horizontal: 12,
              vertical: 12,
            ),
            suffixIcon: _testing
                ? const Padding(
                    padding: EdgeInsets.all(10),
                    child: SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    ),
                  )
                : null,
          ),
          style: const TextStyle(fontSize: 14),
          onChanged: (_) {
            if (_testResult != null) {
              setState(() {
                _testResult = null;
                _testError = null;
              });
            }
          },
        ),
        const SizedBox(height: 12),
        Row(
          children: [
            OutlinedButton.icon(
              onPressed: _testing || _keyCtrl.text.trim().isEmpty
                  ? null
                  : _testKey,
              icon: _testing
                  ? const SizedBox(
                      width: 12,
                      height: 12,
                      child: CircularProgressIndicator(strokeWidth: 1.5),
                    )
                  : const Icon(Symbols.network_check, size: 14),
              label: const Text('Test', style: TextStyle(fontSize: 12)),
              style: OutlinedButton.styleFrom(
                visualDensity: VisualDensity.compact,
              ),
            ),
            if (_testResult != null) ...[
              const SizedBox(width: 12),
              Flexible(
                child: Text(
                  _testResult == true
                      ? '✓ Connection works'
                      : '✗ ${_testError ?? "Connection failed"}',
                  style: TextStyle(
                    fontSize: 12,
                    color: _testResult == true
                        ? Colors.green
                        : tokens.colors.error,
                  ),
                ),
              ),
            ],
          ],
        ),
        const SizedBox(height: 32),
        Row(
          children: [
            OutlinedButton(
              onPressed: () => setState(() => _step = 0),
              style: OutlinedButton.styleFrom(
                visualDensity: VisualDensity.compact,
              ),
              child: const Text('Back', style: TextStyle(fontSize: 12)),
            ),
            const Spacer(),
            FilledButton(
              onPressed: _keyCtrl.text.trim().isEmpty ? null : _finish,
              child: const Text('Get Started'),
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildDoneStep(EaTokens tokens) {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Icon(
          _testResult == true
              ? Symbols.check_circle
              : Symbols.settings,
          size: 64,
          color: _testResult == true
              ? Colors.green
              : tokens.colors.textTertiary,
        ),
        const SizedBox(height: 24),
        Text(
          'You\'re all set!',
          style: tokens.typography.textTheme.headlineSmall?.copyWith(
            color: tokens.colors.textPrimary,
            fontWeight: FontWeight.w600,
          ),
        ),
        const SizedBox(height: 12),
        Text(
          _testResult == true
              ? '${_providerName(_selectedProvider)} is connected and working.'
              : 'You can always configure more providers in Settings.',
          textAlign: TextAlign.center,
          style: tokens.typography.textTheme.bodyMedium?.copyWith(
            color: tokens.colors.textSecondary,
          ),
        ),
        const SizedBox(height: 32),
        FilledButton(
          onPressed: _finish,
          child: const Text('Start Using Executive Assistant'),
        ),
      ],
    );
  }
}
