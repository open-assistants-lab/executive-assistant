import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

class EaTextField extends StatelessWidget {
  final TextEditingController? controller;
  final String? label;
  final String? hint;
  final String? errorText;
  final bool obscureText;
  final TextInputType? keyboardType;
  final int? maxLines;
  final Widget? prefixIcon;
  final Widget? suffixIcon;
  final ValueChanged<String>? onChanged;
  final ValueChanged<String>? onSubmitted;
  final FocusNode? focusNode;

  const EaTextField({
    super.key,
    this.controller,
    this.label,
    this.hint,
    this.errorText,
    this.obscureText = false,
    this.keyboardType,
    this.maxLines = 1,
    this.prefixIcon,
    this.suffixIcon,
    this.onChanged,
    this.onSubmitted,
    this.focusNode,
  });

  @override
  Widget build(BuildContext context) {
    final t = context.tokens;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        if (label != null) ...[
          Text(
            label!,
            style: t.typography.textTheme.bodyMedium
                ?.copyWith(color: t.colors.textSecondary),
          ),
          SizedBox(height: t.spacing.xs),
        ],
        Container(
          decoration: BoxDecoration(
            color: t.colors.bgField,
            borderRadius: t.radius.smAll,
            border: Border.all(
              color:
                  errorText != null ? t.colors.error : t.colors.borderDefault,
            ),
          ),
          child: Row(
            children: [
              if (prefixIcon != null)
                Padding(
                  padding: EdgeInsets.only(left: t.spacing.md),
                  child: IconTheme(
                    data: IconThemeData(
                      color: t.colors.textTertiary,
                      size: 16,
                    ),
                    child: prefixIcon!,
                  ),
                ),
              Expanded(
                child: TextField(
                  controller: controller,
                  focusNode: focusNode,
                  obscureText: obscureText,
                  keyboardType: keyboardType,
                  maxLines: maxLines,
                  onChanged: onChanged,
                  onSubmitted: onSubmitted,
                  style: t.typography.textTheme.bodyMedium
                      ?.copyWith(color: t.colors.textPrimary),
                  decoration: InputDecoration(
                    hintText: hint,
                    hintStyle: t.typography.textTheme.bodyMedium
                        ?.copyWith(color: t.colors.textTertiary),
                    border: InputBorder.none,
                    contentPadding: EdgeInsets.symmetric(
                      horizontal: t.spacing.md,
                      vertical: t.spacing.sm + 2,
                    ),
                    isDense: true,
                  ),
                ),
              ),
              if (suffixIcon != null)
                Padding(
                  padding: EdgeInsets.only(right: t.spacing.md),
                  child: IconTheme(
                    data: IconThemeData(
                      color: t.colors.textTertiary,
                      size: 16,
                    ),
                    child: suffixIcon!,
                  ),
                ),
            ],
          ),
        ),
        if (errorText != null) ...[
          SizedBox(height: t.spacing.xs),
          Text(
            errorText!,
            style: t.typography.textTheme.labelSmall
                ?.copyWith(color: t.colors.error),
          ),
        ],
      ],
    );
  }
}

class EaSearchField extends StatelessWidget {
  final TextEditingController? controller;
  final String? hint;
  final ValueChanged<String>? onChanged;
  final ValueChanged<String>? onSubmitted;

  const EaSearchField({
    super.key,
    this.controller,
    this.hint,
    this.onChanged,
    this.onSubmitted,
  });

  @override
  Widget build(BuildContext context) {
    return EaTextField(
      controller: controller,
      hint: hint ?? 'Search...',
      onChanged: onChanged,
      onSubmitted: onSubmitted,
      prefixIcon: const Icon(Symbols.search, size: 16),
      suffixIcon: controller != null && controller!.text.isNotEmpty
          ? GestureDetector(
              onTap: () {
                controller!.clear();
                onChanged?.call('');
              },
              child: const Icon(Symbols.close, size: 16),
            )
          : null,
    );
  }
}
