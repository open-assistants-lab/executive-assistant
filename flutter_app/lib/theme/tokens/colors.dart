import 'package:flutter/material.dart';

// ignore_for_file: non_constant_identifier_names

@immutable
class EaColors {
  final Color bgCanvas;
  final Color bgSurface;
  final Color bgElevated;
  final Color bgField;
  final Color textPrimary;
  final Color textSecondary;
  final Color textTertiary;
  final Color textInverse;
  final Color accent;
  final Color accentHover;
  final Color accentMuted;
  final Color success;
  final Color warning;
  final Color error;
  final Color info;
  final Color borderSubtle;
  final Color borderDefault;
  final Color borderAccent;

  const EaColors({
    required this.bgCanvas,
    required this.bgSurface,
    required this.bgElevated,
    required this.bgField,
    required this.textPrimary,
    required this.textSecondary,
    required this.textTertiary,
    required this.textInverse,
    required this.accent,
    required this.accentHover,
    required this.accentMuted,
    required this.success,
    required this.warning,
    required this.error,
    required this.info,
    required this.borderSubtle,
    required this.borderDefault,
    required this.borderAccent,
  });

  static const dark = EaColors(
    bgCanvas: Color(0xFF08090A),
    bgSurface: Color(0xFF0E0F11),
    bgElevated: Color(0xFF131416),
    bgField: Color(0xFF1A1B1E),
    textPrimary: Color(0xFFE6E6E6),
    textSecondary: Color(0xFF9B9B9B),
    textTertiary: Color(0xFF6B6B6B),
    textInverse: Color(0xFF08090A),
    accent: Color(0xFF239766),
    accentHover: Color(0xFF2EAD78),
    accentMuted: Color(0xFF0D2B22),
    success: Color(0xFF3DBC83),
    warning: Color(0xFFE0A04B),
    error: Color(0xFFE55B5B),
    info: Color(0xFF5B95E0),
    borderSubtle: Color(0xFF1F1F22),
    borderDefault: Color(0xFF2A2B2E),
    borderAccent: Color(0x66239766),
  );

  static const light = EaColors(
    bgCanvas: Color(0xFFFAFAFA),
    bgSurface: Color(0xFFFFFFFF),
    bgElevated: Color(0xFFF3F3F3),
    bgField: Color(0xFFF0F0F0),
    textPrimary: Color(0xFF0E0F11),
    textSecondary: Color(0xFF5B5B5B),
    textTertiary: Color(0xFF9B9B9B),
    textInverse: Color(0xFFFFFFFF),
    accent: Color(0xFF1B7A52),
    accentHover: Color(0xFF15633F),
    accentMuted: Color(0xFFE6F4ED),
    success: Color(0xFF1B7A52),
    warning: Color(0xFFD18A2F),
    error: Color(0xFFCC4747),
    info: Color(0xFF3273DC),
    borderSubtle: Color(0xFFE8E8E8),
    borderDefault: Color(0xFFD4D4D4),
    borderAccent: Color(0x661B7A52),
  );

  // ── Migration shims (always dark — removed in Phase 4) ──
  // During migration, existing code using AppColors statically
  // continues to work. New code uses context.tokens.colors.*.
  // TODO(migration): Remove all static getters below after Phase 3.

  @Deprecated('Use context.tokens.colors.bgCanvas instead')
  static Color get background => dark.bgCanvas;

  @Deprecated('Use context.tokens.colors.bgSurface instead')
  static Color get surface => dark.bgSurface;

  @Deprecated('Use context.tokens.colors.bgCanvas instead')
  static Color get primary => dark.bgCanvas;

  @Deprecated('Use context.tokens.colors.accent instead')
  static Color get accent_color => dark.accent;

  @Deprecated('Use context.tokens.colors.success instead')
  static Color get success_color => dark.success;

  @Deprecated('Use context.tokens.colors.warning instead')
  static Color get warning_color => dark.warning;

  @Deprecated('Use context.tokens.colors.error instead')
  static Color get danger => dark.error;

  @Deprecated('Use context.tokens.colors.textTertiary instead')
  static Color get textDim => dark.textTertiary;

  @Deprecated('Use context.tokens.colors.borderDefault instead')
  static Color get border => dark.borderDefault;

  @Deprecated('Use context.tokens.colors.borderSubtle instead')
  static Color get divider => dark.borderSubtle;

  @Deprecated('Use context.tokens.colors.accentMuted instead')
  static Color get userBubble => dark.accentMuted;

  @Deprecated('Use context.tokens.colors.bgSurface instead')
  static Color get assistantBubble => dark.bgSurface;

  @Deprecated('Use context.tokens.colors.bgField instead')
  static Color get toolChipBg => dark.bgField;

  @Deprecated('Use context.tokens.colors.textPrimary instead')
  static Color get toolChipText => dark.textPrimary;

  @Deprecated('Use context.tokens.colors.accent instead')
  static Color get companionPulse => dark.accent;

  @Deprecated('Use context.tokens.colors.bgField instead')
  static Color get inputBg => dark.bgField;
}
