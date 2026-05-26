import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;
import 'package:url_launcher/url_launcher.dart';

import '../../../providers/agent_provider.dart';

class ConnectAuthForm extends ConsumerStatefulWidget {
  final Map<String, dynamic> spec;
  final VoidCallback onDone;

  const ConnectAuthForm({
    super.key,
    required this.spec,
    required this.onDone,
  });

  @override
  ConsumerState<ConnectAuthForm> createState() => _ConnectAuthFormState();
}

class _ConnectAuthFormState extends ConsumerState<ConnectAuthForm> {
  final _formKey = GlobalKey<FormState>();
  final Map<String, TextEditingController> _ctrls = {};
  bool _connecting = false;
  bool _browserOpened = false;
  Timer? _pollTimer;

  bool get _isPkce => widget.spec['pkce'] == true;

  @override
  void initState() {
    super.initState();
    if (_isPkce) {
      final fields = (widget.spec['required_fields'] as List? ?? [])
          .cast<Map<String, dynamic>>();
      for (final f in fields) {
        final name = f['name'] as String;
        final ctrl = TextEditingController(text: f['default'] as String? ?? '');
        _ctrls[name] = ctrl;
      }
    }
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    for (final c in _ctrls.values) {
      c.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final spec = widget.spec;
    final fields = (spec['required_fields'] as List? ?? [])
        .cast<Map<String, dynamic>>();
    final authType = spec['auth_type'] as String? ?? 'none';

    return Form(
      key: _formKey,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            'Connect ${spec['name'] ?? ''}',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 4),
          Text(
            spec['description'] ?? '',
            style: Theme.of(context).textTheme.bodySmall,
          ),
          const SizedBox(height: 16),
          if (_isPkce) ...[
            ...fields.map(_buildField),
            const SizedBox(height: 8),
            Row(
              children: [
                Icon(
                  _browserOpened ? Icons.check_circle : Icons.open_in_browser,
                  size: 16,
                  color: _browserOpened ? Colors.green : Colors.grey,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    _browserOpened
                        ? 'Browser opened — authorize and return here.'
                        : 'Click the button to authorize via your browser.',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ),
              ],
            ),
          ] else if (authType == 'oauth2') ...[
            Text(
              'OAuth2 — click Sign In to authorize:',
              style: Theme.of(context).textTheme.bodySmall,
            ),
            const SizedBox(height: 8),
            if (fields.isNotEmpty) ...[
              Text(
                'Optional custom app settings:',
                style: Theme.of(context).textTheme.bodySmall,
              ),
              ...fields.map(_buildField),
            ],
          ] else if (authType == 'api_key')
            ...fields.map(_buildField)
          else if (authType == 'basic')
            ...fields.map(_buildField)
          else
            Text(
              'No credentials needed. Click Connect to enable.',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          const SizedBox(height: 16),
          Row(
            mainAxisAlignment: MainAxisAlignment.end,
            children: [
              TextButton(
                onPressed: () {
                  _pollTimer?.cancel();
                  Navigator.of(context).pop();
                },
                child: const Text('Cancel'),
              ),
              const SizedBox(width: 8),
              if (_isPkce && _browserOpened)
                FilledButton(
                  onPressed: _connecting ? null : _checkConnected,
                  child: _connecting
                      ? const SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Text("I've Authorized"),
                )
              else
                FilledButton(
                  onPressed: _connecting ? null : _connect,
                  child: _connecting
                      ? const SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : Text(_isPkce ? 'Open Browser' : 'Connect'),
                ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildField(Map<String, dynamic> field) {
    final name = field['name'] as String;
    final label = field['label'] as String? ?? name;
    final type = field['type'] as String? ?? 'string';
    final ctrl = _ctrls.putIfAbsent(name, () => TextEditingController());
    final obscure =
        type == 'password' || name.toLowerCase().contains('secret');
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: TextFormField(
        controller: ctrl,
        obscureText: obscure,
        readOnly: _isPkce && name == 'client_id' && ctrl.text.isNotEmpty,
        decoration: InputDecoration(
          labelText: label,
          isDense: true,
          border: const OutlineInputBorder(),
        ),
      ),
    );
  }

  Future<void> _openBrowser({String? clientSecret}) async {
    final host = ref.read(hostProvider);
    final service = widget.spec['name'] as String;
    var url = 'http://$host/auth/login?service=$service&user_id=default_user';
    if (clientSecret != null && clientSecret.isNotEmpty) {
      // Google's token endpoint requires client_secret even with PKCE
      url += '&client_secret=${Uri.encodeQueryComponent(clientSecret)}';
    }
    final uri = Uri.parse(url);
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    }
  }

  Future<void> _connect() async {
    if (_isPkce) {
      setState(() => _connecting = true);
      try {
        final secretCtrl = _ctrls['client_secret'];
        final clientSecret = secretCtrl?.text;
        await _openBrowser(clientSecret: clientSecret);
        setState(() {
          _browserOpened = true;
          _connecting = false;
        });
      } catch (e) {
        setState(() => _connecting = false);
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to open browser: $e')),
        );
      }
      return;
    }

    if (!_formKey.currentState!.validate()) return;
    setState(() => _connecting = true);
    try {
      final body = <String, String>{};
      for (final entry in _ctrls.entries) {
        if (entry.value.text.isNotEmpty) {
          body[entry.key] = entry.value.text;
        }
      }
      final host = ref.read(hostProvider);
      final resp = await http.post(
        Uri.parse(
          'http://$host/connectors/connect?service=${widget.spec['name']}&user_id=default_user',
        ),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode(body),
      );
      if (resp.statusCode == 200) {
        widget.onDone();
        if (!mounted) return;
        Navigator.of(context).pop();
      } else {
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed: ${resp.body}')),
        );
      }
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error: $e')),
      );
    } finally {
      if (mounted) setState(() => _connecting = false);
    }
  }

  Future<void> _checkConnected() async {
    setState(() => _connecting = true);
    try {
      final host = ref.read(hostProvider);
      final service = widget.spec['name'] as String;
      final resp = await http.get(
        Uri.parse(
          'http://$host/connectors/catalog?user_id=default_user',
        ),
      );
      if (resp.statusCode == 200) {
        final list = (jsonDecode(resp.body) as List)
            .map((e) => e as Map<String, dynamic>)
            .toList();
        for (final c in list) {
          if (c['name'] == service && c['connected'] == true) {
            widget.onDone();
            if (!mounted) return;
            Navigator.of(context).pop();
            return;
          }
        }
      }
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Not connected yet. Complete authorization in the browser.'),
        ),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error: $e')),
      );
    } finally {
      if (mounted) setState(() => _connecting = false);
    }
  }
}
