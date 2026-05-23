import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;
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

  @override
  void dispose() {
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
          if (authType == 'oauth2') ...[
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
                onPressed: () => Navigator.of(context).pop(),
                child: const Text('Cancel'),
              ),
              const SizedBox(width: 8),
              FilledButton(
                onPressed: _connecting ? null : _connect,
                child: _connecting
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Text('Connect'),
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
        decoration: InputDecoration(
          labelText: label,
          isDense: true,
          border: const OutlineInputBorder(),
        ),
      ),
    );
  }

  Future<void> _connect() async {
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
}
