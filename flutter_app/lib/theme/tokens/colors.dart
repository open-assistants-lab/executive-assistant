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
    bgCanvas: Color(0xFF0A0A0A),
    bgSurface: Color(0xFF141414),
    bgElevated: Color(0xFF1C1C1C),
    bgField: Color(0xFF181818),
    textPrimary: Color(0xFFEDEDED),
    textSecondary: Color(0xFF8A8A8A),
    textTertiary: Color(0xFF5A5A5A),
    textInverse: Color(0xFF0A0A0A),
    accent: Color(0xFFD4D4D4),
    accentHover: Color(0xFFE8E8E8),
    accentMuted: Color(0xFF3A3A3A),
    success: Color(0xFF2ED573),
    warning: Color(0xFFFFA502),
    error: Color(0xFFFF4757),
    info: Color(0xFF54A0FF),
    borderSubtle: Color(0xFF1E1E1E),
    borderDefault: Color(0xFF2A2A2A),
    borderAccent: Color(0xCCD4D4D4),
  );

  static const light = EaColors(
    bgCanvas: Color(0xFFF8F8F8),
    bgSurface: Color(0xFFFFFFFF),
    bgElevated: Color(0xFFF0F0F0),
    bgField: Color(0xFFEBEBEB),
    textPrimary: Color(0xFF141414),
    textSecondary: Color(0xFF5A5A5A),
    textTertiary: Color(0xFF9A9A9A),
    textInverse: Color(0xFFFFFFFF),
    accent: Color(0xFF2A2A2A),
    accentHover: Color(0xFF1A1A1A),
    accentMuted: Color(0xFFE8E8E8),
    success: Color(0xFF1DB954),
    warning: Color(0xFFE89400),
    error: Color(0xFFE8404F),
    info: Color(0xFF3B8EFF),
    borderSubtle: Color(0xFFE4E4E4),
    borderDefault: Color(0xFFD0D0D0),
    borderAccent: Color(0xCC2A2A2A),
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
