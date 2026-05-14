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
    return Container(
      height: 36,
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppColors.divider),
      ),
      child: TextField(
        controller: controller,
        onTap: onTap,
        onChanged: onChanged,
        onSubmitted: onSubmitted,
        style: AppTypography.body.copyWith(fontSize: 13),
        decoration: InputDecoration(
          hintText: hint,
          hintStyle: AppTypography.caption.copyWith(fontSize: 13, color: AppColors.textDim),
          prefixIcon: Icon(Icons.search, size: 16, color: AppColors.textDim),
          border: InputBorder.none,
          isDense: true,
          contentPadding: const EdgeInsets.symmetric(horizontal: 8, vertical: 10),
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
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.cardPadding,
        vertical: AppSpacing.itemGap,
      ),
      decoration: const BoxDecoration(
        color: AppColors.background,
        border: Border(top: BorderSide(color: AppColors.divider)),
      ),
      child: Row(
        children: [
          Expanded(
            child: Container(
              decoration: BoxDecoration(
                color: AppColors.surface,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: AppColors.divider),
              ),
              child: TextField(
                controller: _controller,
                focusNode: _focusNode,
                enabled: widget.enabled,
                style: AppTypography.body.copyWith(fontSize: 13),
                decoration: InputDecoration(
                  hintText: widget.hint,
                  hintStyle: AppTypography.caption.copyWith(
                    fontSize: 13, color: AppColors.textDim,
                  ),
                  suffixIcon: widget.sending
                      ? IconButton(
                          icon: const Icon(Icons.stop_rounded, size: 18),
                          padding: EdgeInsets.zero,
                          constraints: const BoxConstraints(minWidth: 36, minHeight: 36),
                          onPressed: widget.onCancel,
                        )
                      : !widget.enabled
                          ? IconButton(
                              icon: const Icon(Icons.refresh, size: 18),
                              padding: EdgeInsets.zero,
                              constraints: const BoxConstraints(minWidth: 36, minHeight: 36),
                              tooltip: 'Reconnect',
                              onPressed: widget.onReconnect,
                            )
                          : IconButton(
                              icon: Icon(Icons.send_rounded, size: 20, color: AppColors.accent),
                              padding: EdgeInsets.zero,
                              constraints: const BoxConstraints(minWidth: 36, minHeight: 36),
                              onPressed: _send,
                            ),
                  border: InputBorder.none,
                  isDense: true,
                  contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
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
