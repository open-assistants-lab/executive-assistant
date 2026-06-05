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
  final TextEditingController controller;
  final FocusNode focusNode;
  final ValueChanged<String>? onChanged;

  const AppChatField({
    super.key,
    this.hint = 'Ask anything...',
    required this.onSend,
    this.enabled = true,
    this.sending = false,
    this.onCancel,
    this.onReconnect,
    required this.controller,
    required this.focusNode,
    this.onChanged,
  });

  @override
  State<AppChatField> createState() => _AppChatFieldState();
}

class _AppChatFieldState extends State<AppChatField> {
  bool _focused = false;
  bool _hasText = false;

  @override
  void initState() {
    super.initState();
    widget.focusNode.addListener(_handleFocusChange);
    widget.controller.addListener(_handleTextChange);
    _hasText = widget.controller.text.trim().isNotEmpty;
  }

  @override
  void didUpdateWidget(covariant AppChatField oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.controller != widget.controller) {
      oldWidget.controller.removeListener(_handleTextChange);
      widget.controller.addListener(_handleTextChange);
    }
    if (oldWidget.focusNode != widget.focusNode) {
      oldWidget.focusNode.removeListener(_handleFocusChange);
      widget.focusNode.addListener(_handleFocusChange);
    }
  }

  @override
  void dispose() {
    widget.controller.removeListener(_handleTextChange);
    widget.focusNode.removeListener(_handleFocusChange);
    super.dispose();
  }

  void _handleFocusChange() {
    if (_focused != widget.focusNode.hasFocus) {
      setState(() => _focused = widget.focusNode.hasFocus);
    }
  }

  void _handleTextChange() {
    final hasText = widget.controller.text.trim().isNotEmpty;
    if (_hasText != hasText) {
      setState(() => _hasText = hasText);
    }
    widget.onChanged?.call(widget.controller.text);
  }

  void _send() {
    final text = widget.controller.text.trim();
    if (text.isEmpty) return;
    widget.controller.clear();
    widget.onSend(text);
    widget.focusNode.requestFocus();
  }

  @override
  Widget build(BuildContext context) {
    final tokens = context.tokens;
    final canSend = _hasText && widget.enabled && !widget.sending;
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
            child: AnimatedContainer(
              duration: tokens.motion.fast,
              curve: tokens.motion.curveStandard,
              decoration: BoxDecoration(
                color: tokens.colors.bgField,
                border: Border.all(
                  color: _focused ? tokens.colors.borderAccent : tokens.colors.borderDefault,
                  width: 1,
                ),
                borderRadius: tokens.radius.mdAll,
              ),
              clipBehavior: Clip.antiAlias,
              padding: const EdgeInsets.symmetric(
                horizontal: 12,
                vertical: 0,
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.center,
                children: [
                  Expanded(
                    child: SizedBox(
                      height: 32,
                      child: Align(
                        alignment: Alignment.centerLeft,
                        child: TextField(
                          controller: widget.controller,
                          focusNode: widget.focusNode,
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
                            border: InputBorder.none,
                            enabledBorder: InputBorder.none,
                            focusedBorder: InputBorder.none,
                            errorBorder: InputBorder.none,
                            disabledBorder: InputBorder.none,
                            isDense: true,
                            isCollapsed: true,
                            contentPadding: EdgeInsets.zero,
                          ),
                          onSubmitted: (_) => _send(),
                        ),
                      ),
                    ),
                  ),
                  SizedBox(width: tokens.spacing.sm),
                  _buildTrailingButton(tokens, canSend),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTrailingButton(EaTokens tokens, bool canSend) {
    if (widget.sending) {
      return _SquareIconButton(
        icon: Symbols.stop,
        iconColor: tokens.colors.textInverse,
        background: tokens.colors.accent,
        onTap: widget.onCancel,
        duration: tokens.motion.fast,
        curve: tokens.motion.curveStandard,
        radius: tokens.radius.smAll,
      );
    }
    if (!widget.enabled) {
      return _SquareIconButton(
        icon: Symbols.refresh,
        iconColor: tokens.colors.textTertiary,
        background: tokens.colors.accentMuted,
        onTap: widget.onReconnect,
        tooltip: 'Reconnect',
        duration: tokens.motion.fast,
        curve: tokens.motion.curveStandard,
        radius: tokens.radius.smAll,
      );
    }
    return _SquareIconButton(
      icon: Symbols.arrow_upward,
      iconColor: canSend ? tokens.colors.textInverse : tokens.colors.textTertiary,
      background: canSend ? tokens.colors.accent : tokens.colors.accentMuted,
      onTap: canSend ? _send : null,
      duration: tokens.motion.fast,
      curve: tokens.motion.curveStandard,
      radius: tokens.radius.smAll,
    );
  }
}

class _SquareIconButton extends StatelessWidget {
  final IconData icon;
  final Color iconColor;
  final Color background;
  final VoidCallback? onTap;
  final String? tooltip;
  final Duration duration;
  final Curve curve;
  final BorderRadius radius;

  const _SquareIconButton({
    required this.icon,
    required this.iconColor,
    required this.background,
    required this.onTap,
    required this.duration,
    required this.curve,
    required this.radius,
    this.tooltip,
  });

  @override
  Widget build(BuildContext context) {
    final button = MouseRegion(
      cursor: onTap == null ? SystemMouseCursors.basic : SystemMouseCursors.click,
      child: GestureDetector(
        onTap: onTap,
        child: AnimatedContainer(
          duration: duration,
          curve: curve,
          width: 32,
          height: 32,
          decoration: BoxDecoration(
            color: background,
            borderRadius: radius,
          ),
          alignment: Alignment.center,
          child: Icon(icon, size: 16, color: iconColor),
        ),
      ),
    );
    if (tooltip != null) {
      return Tooltip(message: tooltip!, child: button);
    }
    return button;
  }
}
