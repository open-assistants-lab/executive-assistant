import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

/// Search bar with consistent styling — filled, rounded, with icon.
class AppSearchField extends StatelessWidget {
  final String hint;
  final ValueChanged<String>? onSubmitted;
  final TextEditingController? controller;
  final ValueChanged<String>? onChanged;
  final VoidCallback? onTap;

  const AppSearchField({
    super.key,
    this.hint = 'Search...',
    this.onSubmitted,
    this.controller,
    this.onChanged,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final tokens = context.tokens;
    return Container(
      height: 36,
      decoration: BoxDecoration(
        color: tokens.colors.bgField,
        borderRadius: BorderRadius.circular(8),
      ),
      child: TextField(
        controller: controller,
        onTap: onTap,
        onChanged: onChanged,
        onSubmitted: onSubmitted,
        textAlignVertical: TextAlignVertical.center,
        style: tokens.typography.textTheme.bodyMedium?.copyWith(
          fontSize: 13, color: tokens.colors.textPrimary,
        ),
        decoration: InputDecoration(
          hintText: hint,
          hintStyle: tokens.typography.textTheme.bodySmall?.copyWith(fontSize: 13, color: tokens.colors.textTertiary),
          prefixIcon: Icon(Symbols.search, size: 16, color: tokens.colors.textTertiary),
          border: InputBorder.none,
          enabledBorder: InputBorder.none,
          focusedBorder: InputBorder.none,
          isDense: true,
          contentPadding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
        ),
      ),
    );
  }
}

/// Chat input with consistent styling — filled, rounded, with send button.
class AppChatField extends StatefulWidget {
  final String hint;
  final ValueChanged<String> onSend;
  final bool enabled;
  final bool sending;
  final VoidCallback? onCancel;
  final VoidCallback? onReconnect;

  const AppChatField({
    super.key,
    this.hint = 'Ask anything...',
    required this.onSend,
    this.enabled = true,
    this.sending = false,
    this.onCancel,
    this.onReconnect,
  });

  @override
  State<AppChatField> createState() => _AppChatFieldState();
}

class _AppChatFieldState extends State<AppChatField> {
  final _controller = TextEditingController();
  final _focusNode = FocusNode();

  @override
  void dispose() {
    _controller.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  void _send() {
    final text = _controller.text.trim();
    if (text.isEmpty) return;
    _controller.clear();
    widget.onSend(text);
    _focusNode.requestFocus();
  }

  @override
  Widget build(BuildContext context) {
    final tokens = context.tokens;
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.cardPadding,
        vertical: AppSpacing.itemGap,
      ),
      decoration: BoxDecoration(
        color: tokens.colors.bgCanvas,
        border: Border(top: BorderSide(color: tokens.colors.borderSubtle)),
      ),
      child: Row(
        children: [
          Expanded(
            child: Container(
              decoration: BoxDecoration(
                color: tokens.colors.bgField,
                borderRadius: BorderRadius.circular(tokens.radius.md),
              ),
              clipBehavior: Clip.antiAlias,
              child: TextField(
                controller: _controller,
                focusNode: _focusNode,
                enabled: widget.enabled,
                textAlignVertical: TextAlignVertical.center,
                style: tokens.typography.textTheme.bodyMedium?.copyWith(
                  fontSize: 13, color: tokens.colors.textPrimary,
                ),
                decoration: InputDecoration(
                  hintText: widget.hint,
                  hintStyle: tokens.typography.textTheme.bodySmall?.copyWith(
                    fontSize: 13, color: tokens.colors.textTertiary,
                  ),
                  suffixIcon: widget.sending
                      ? IconButton(
                          icon: const Icon(Symbols.stop, size: 18),
                          padding: EdgeInsets.zero,
                          constraints: const BoxConstraints(minWidth: 36, minHeight: 36),
                          onPressed: widget.onCancel,
                        )
                      : !widget.enabled
                          ? IconButton(
                              icon: const Icon(Symbols.refresh, size: 18),
                              padding: EdgeInsets.zero,
                              constraints: const BoxConstraints(minWidth: 36, minHeight: 36),
                              tooltip: 'Reconnect',
                              onPressed: widget.onReconnect,
                            )
                          : IconButton(
                              icon: Icon(Symbols.send, size: 20, color: tokens.colors.textPrimary),
                              padding: EdgeInsets.zero,
                              constraints: const BoxConstraints(minWidth: 36, minHeight: 36),
                              onPressed: _send,
                            ),
                  suffixIconConstraints: const BoxConstraints(minWidth: 36, minHeight: 36),
                  border: InputBorder.none,
                  enabledBorder: InputBorder.none,
                  focusedBorder: InputBorder.none,
                  errorBorder: InputBorder.none,
                  disabledBorder: InputBorder.none,
                  isDense: true,
                  contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                ),
                onSubmitted: (_) => _send(),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
