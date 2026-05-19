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
    bgCanvas: Color(0xFF0A0A0F),
    bgSurface: Color(0xFF12121A),
    bgElevated: Color(0xFF1A1A26),
    bgField: Color(0xFF161620),
    textPrimary: Color(0xFFEEEEF0),
    textSecondary: Color(0xFF8B8BA0),
    textTertiary: Color(0xFF5C5C6E),
    textInverse: Color(0xFF0A0A0F),
    accent: Color(0xFF6C5CE7),
    accentHover: Color(0xFF7C6CF7),
    accentMuted: Color(0xFF3D3580),
    success: Color(0xFF2ED573),
    warning: Color(0xFFFFA502),
    error: Color(0xFFFF4757),
    info: Color(0xFF54A0FF),
    borderSubtle: Color(0xFF1E1E2E),
    borderDefault: Color(0xFF2A2A3C),
    borderAccent: Color(0xCC6C5CE7),
  );

  static const light = EaColors(
    bgCanvas: Color(0xFFF8F8FA),
    bgSurface: Color(0xFFFFFFFF),
    bgElevated: Color(0xFFF0F0F4),
    bgField: Color(0xFFEBEBF0),
    textPrimary: Color(0xFF12121A),
    textSecondary: Color(0xFF5C5C6E),
    textTertiary: Color(0xFF9C9CB0),
    textInverse: Color(0xFFFFFFFF),
    accent: Color(0xFF5E4ED6),
    accentHover: Color(0xFF4E3EC6),
    accentMuted: Color(0xFFE8E5FF),
    success: Color(0xFF1DB954),
    warning: Color(0xFFE89400),
    error: Color(0xFFE8404F),
    info: Color(0xFF3B8EFF),
    borderSubtle: Color(0xFFE4E4EC),
    borderDefault: Color(0xFFD0D0DC),
    borderAccent: Color(0xCC5E4ED6),
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
