import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

export 'package:material_symbols_icons/symbols.dart';

export 'app_colors.dart';
export 'app_typography.dart';
export 'app_spacing.dart';
export 'app_radius.dart';

import 'tokens/colors.dart';
import 'tokens/typography.dart';
import 'tokens/spacing.dart';
import 'tokens/radius.dart';
import 'tokens/motion.dart';
import '../core/page_transitions.dart';

@immutable
class EaTokens extends ThemeExtension<EaTokens> {
  final EaColors colors;
  final EaTypography typography;
  final EaSpacing spacing;
  final EaRadius radius;
  final EaMotion motion;
  final Brightness brightness;

  const EaTokens({
    required this.colors,
    required this.typography,
    required this.spacing,
    required this.radius,
    required this.motion,
    required this.brightness,
  });

  bool get isDark => brightness == Brightness.dark;

  factory EaTokens.dark() {
    return EaTokens(
      colors: EaColors.dark,
      typography: EaTypography.build(Brightness.dark),
      spacing: EaSpacing.standard,
      radius: EaRadius.standard,
      motion: EaMotion.standard,
      brightness: Brightness.dark,
    );
  }

  factory EaTokens.light() {
    return EaTokens(
      colors: EaColors.light,
      typography: EaTypography.build(Brightness.light),
      spacing: EaSpacing.standard,
      radius: EaRadius.standard,
      motion: EaMotion.standard,
      brightness: Brightness.light,
    );
  }

  @override
  EaTokens copyWith({
    EaColors? colors,
    EaTypography? typography,
    EaSpacing? spacing,
    EaRadius? radius,
    EaMotion? motion,
    Brightness? brightness,
  }) {
    return EaTokens(
      colors: colors ?? this.colors,
      typography: typography ?? this.typography,
      spacing: spacing ?? this.spacing,
      radius: radius ?? this.radius,
      motion: motion ?? this.motion,
      brightness: brightness ?? this.brightness,
    );
  }

  @override
  EaTokens lerp(EaTokens? other, double t) => this;
}

extension EaTokensBuildContext on BuildContext {
  EaTokens get tokens => Theme.of(this).extension<EaTokens>()!;
}

class AppTheme {
  AppTheme._();

  static ThemeData _build(Brightness brightness) {
    final tokens = brightness == Brightness.dark ? EaTokens.dark() : EaTokens.light();

    return ThemeData(
      brightness: brightness,
      useMaterial3: true,
      scaffoldBackgroundColor: tokens.colors.bgCanvas,
      colorScheme: ColorScheme(
        brightness: brightness,
        primary: tokens.colors.accent,
        onPrimary: tokens.colors.textInverse,
        secondary: tokens.colors.accentMuted,
        onSecondary: tokens.colors.textPrimary,
        surface: tokens.colors.bgSurface,
        onSurface: tokens.colors.textPrimary,
        error: tokens.colors.error,
        onError: tokens.colors.textInverse,
        outline: tokens.colors.borderDefault,
        outlineVariant: tokens.colors.borderSubtle,
      ),
      textTheme: tokens.typography.textTheme,
      cardTheme: CardThemeData(
        color: tokens.colors.bgSurface,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: tokens.radius.lgAll,
          side: BorderSide(color: tokens.colors.borderSubtle),
        ),
        margin: EdgeInsets.zero,
      ),
      appBarTheme: AppBarTheme(
        backgroundColor: tokens.colors.bgCanvas,
        foregroundColor: tokens.colors.textPrimary,
        elevation: 0,
        scrolledUnderElevation: 0,
      ),
      bottomNavigationBarTheme: BottomNavigationBarThemeData(
        backgroundColor: tokens.colors.bgSurface,
        selectedItemColor: tokens.colors.accent,
        unselectedItemColor: tokens.colors.textTertiary,
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: tokens.colors.bgField,
        labelStyle: tokens.typography.textTheme.bodySmall?.copyWith(color: tokens.colors.textSecondary),
        hintStyle: tokens.typography.textTheme.bodySmall?.copyWith(color: tokens.colors.textTertiary),
        border: OutlineInputBorder(
          borderRadius: tokens.radius.mdAll,
          borderSide: BorderSide(color: tokens.colors.borderDefault),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: tokens.radius.mdAll,
          borderSide: BorderSide(color: tokens.colors.borderDefault),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: tokens.radius.mdAll,
          borderSide: BorderSide(color: tokens.colors.accent, width: 1.5),
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      ),
      canvasColor: tokens.colors.bgElevated,
      popupMenuTheme: PopupMenuThemeData(
        color: tokens.colors.bgElevated,
        textStyle: tokens.typography.textTheme.bodyMedium?.copyWith(
          color: tokens.colors.textPrimary,
        ),
        shape: RoundedRectangleBorder(
          borderRadius: tokens.radius.smAll,
          side: BorderSide(color: tokens.colors.borderDefault, width: 1),
        ),
        elevation: 0,
      ),
      dropdownMenuTheme: DropdownMenuThemeData(
        textStyle: tokens.typography.textTheme.bodyMedium?.copyWith(
          color: tokens.colors.textPrimary,
        ),
        inputDecorationTheme: InputDecorationTheme(
          filled: true,
          fillColor: tokens.colors.bgField,
          border: OutlineInputBorder(
            borderRadius: tokens.radius.mdAll,
            borderSide: BorderSide(color: tokens.colors.borderDefault),
          ),
        ),
        menuStyle: MenuStyle(
          backgroundColor: WidgetStatePropertyAll(tokens.colors.bgElevated),
          surfaceTintColor: const WidgetStatePropertyAll(Colors.transparent),
          shape: WidgetStatePropertyAll(
            RoundedRectangleBorder(
              borderRadius: tokens.radius.smAll,
              side: BorderSide(color: tokens.colors.borderDefault, width: 1),
            ),
          ),
        ),
      ),
      menuTheme: MenuThemeData(
        style: MenuStyle(
          backgroundColor: WidgetStatePropertyAll(tokens.colors.bgElevated),
          surfaceTintColor: const WidgetStatePropertyAll(Colors.transparent),
          shape: WidgetStatePropertyAll(
            RoundedRectangleBorder(
              borderRadius: tokens.radius.smAll,
              side: BorderSide(color: tokens.colors.borderDefault, width: 1),
            ),
          ),
        ),
      ),
      bottomSheetTheme: BottomSheetThemeData(
        backgroundColor: tokens.colors.bgSurface,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(
            top: Radius.circular(tokens.radius.lg),
          ),
        ),
      ),
      dividerTheme: DividerThemeData(
        color: tokens.colors.borderSubtle,
        thickness: 1,
      ),
      pageTransitionsTheme: const EaPageTransitionsTheme(),
      extensions: [tokens],
    );
  }

  static ThemeData get dark => _build(Brightness.dark);
  static ThemeData get light => _build(Brightness.light);
}

final themeModeProvider = StateNotifierProvider<ThemeModeNotifier, ThemeMode>((ref) {
  return ThemeModeNotifier();
});

class ThemeModeNotifier extends StateNotifier<ThemeMode> {
  ThemeModeNotifier() : super(ThemeMode.dark) {
    _load();
  }

  Future<void> _load() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final mode = prefs.getString('themeMode') ?? 'dark';
      state = mode == 'light' ? ThemeMode.light : ThemeMode.dark;
    } catch (_) {
      state = ThemeMode.dark;
    }
  }

  Future<void> toggle() async {
    state = state == ThemeMode.dark ? ThemeMode.light : ThemeMode.dark;
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('themeMode', state == ThemeMode.dark ? 'dark' : 'light');
    } catch (_) {}
  }
}
