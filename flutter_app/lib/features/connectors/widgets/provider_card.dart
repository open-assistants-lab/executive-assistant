import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../theme/app_theme.dart';
import '../../settings/providers/settings_provider.dart';

class ProviderCard extends ConsumerStatefulWidget {
  final String providerId;
  final String providerName;
  final bool hasKey;
  final List<String> models;
  final String? selectedModel;

  const ProviderCard({
    super.key,
    required this.providerId,
    required this.providerName,
    required this.hasKey,
    required this.models,
    this.selectedModel,
  });

  @override
  ConsumerState<ProviderCard> createState() => _ProviderCardState();
}

class _ProviderCardState extends ConsumerState<ProviderCard> {
  bool _expanded = false;
  final _keyCtrl = TextEditingController();
  bool _saving = false;

  @override
  void dispose() {
    _keyCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final tokens = context.tokens;
    final settings = ref.read(settingsProvider.notifier);

    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      child: Column(
        children: [
          ListTile(
            leading: Icon(
              widget.hasKey
                  ? Symbols.radio_button_checked
                  : Symbols.radio_button_unchecked,
              size: 18,
              color: widget.hasKey
                  ? tokens.colors.accent
                  : tokens.colors.textTertiary,
            ),
            title: Text(
              widget.providerName,
              style: const TextStyle(fontSize: 14),
            ),
            subtitle: Text(
              widget.hasKey ? '🔑 Configured' : '⚠️ Needs API key',
              style: TextStyle(
                fontSize: 11,
                color: widget.hasKey ? Colors.green : Colors.orange,
              ),
            ),
            trailing: Icon(
              _expanded ? Symbols.expand_less : Symbols.expand_more,
              size: 18,
            ),
            onTap: () => setState(() => _expanded = !_expanded),
          ),
          if (_expanded) ...[
            Padding(
              padding: const EdgeInsets.symmetric(
                horizontal: 16,
                vertical: 8,
              ),
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _keyCtrl,
                      obscureText: true,
                      decoration: InputDecoration(
                        hintText: 'API key for ${widget.providerName}',
                        labelText: widget.hasKey ? 'API Key' : null,
                        isDense: true,
                        border: const OutlineInputBorder(),
                        contentPadding: const EdgeInsets.symmetric(
                          horizontal: 12,
                          vertical: 10,
                        ),
                        suffixIcon: _saving
                            ? const SizedBox(
                                width: 16,
                                height: 16,
                                child: Padding(
                                  padding: EdgeInsets.all(10),
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2,
                                  ),
                                ),
                              )
                            : null,
                      ),
                      style: const TextStyle(fontSize: 13),
                    ),
                  ),
                  const SizedBox(width: 8),
                  FilledButton(
                    onPressed: () async {
                      setState(() => _saving = true);
                      await settings.setApiKey(
                        widget.providerId,
                        _keyCtrl.text,
                      );
                      setState(() => _saving = false);
                    },
                    style: FilledButton.styleFrom(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 16,
                      ),
                    ),
                    child: Text(
                      widget.hasKey ? 'Change' : 'Save',
                      style: const TextStyle(fontSize: 12),
                    ),
                  ),
                ],
              ),
            ),
            const Divider(height: 1),
            if (widget.models.isEmpty)
              Padding(
                padding: const EdgeInsets.all(12),
                child: Text(
                  'No models found for this provider.',
                  style: TextStyle(
                    fontSize: 12,
                    color: tokens.colors.textTertiary,
                  ),
                ),
              )
            else
              ...widget.models.map((m) {
                final modelValue = '${widget.providerId}:$m';
                final isSelected = modelValue == widget.selectedModel;
                return ListTile(
                  title: Text(m, style: const TextStyle(fontSize: 12)),
                  // ignore: deprecated_member_use
                  leading: Radio<String>(
                    value: modelValue,
                    // ignore: deprecated_member_use
                    groupValue: widget.selectedModel,
                    // ignore: deprecated_member_use
                    onChanged: (v) {
                      if (v != null) {
                        settings.setDefaultModel(v);
                      }
                    },
                  ),
                  dense: true,
                  selected: isSelected,
                );
              }),
          ],
        ],
      ),
    );
  }
}
