import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

class EaPageTransitions extends PageTransitionsBuilder {
  const EaPageTransitions();

  @override
  Widget buildTransitions<T>(
    PageRoute<T> route,
    BuildContext context,
    Animation<double> animation,
    Animation<double> secondaryAnimation,
    Widget child,
  ) {
    final tokens = context.tokens;
    final slide = Tween<Offset>(
      begin: const Offset(0.02, 0),
      end: Offset.zero,
    ).animate(CurvedAnimation(parent: animation, curve: tokens.motion.curveStandard));
    return FadeTransition(
      opacity: animation,
      child: SlideTransition(position: slide, child: child),
    );
  }
}

class EaPageTransitionsTheme extends PageTransitionsTheme {
  const EaPageTransitionsTheme()
      : super(builders: const {
          TargetPlatform.macOS: EaPageTransitions(),
          TargetPlatform.linux: EaPageTransitions(),
          TargetPlatform.windows: EaPageTransitions(),
        });
}
