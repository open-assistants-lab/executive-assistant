import 'dart:math';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../theme/app_theme.dart';
import '../../providers/companion_provider.dart';

class CompanionPulse extends ConsumerStatefulWidget {
  const CompanionPulse({super.key});

  @override
  ConsumerState<CompanionPulse> createState() => _CompanionPulseState();
}

class _CompanionPulseState extends ConsumerState<CompanionPulse>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;

  @override
  void initState() {
    super.initState();
    // 3.2s breath cycle — slow, calming, like inhale/exhale
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 3200),
    )..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final paused = ref.watch(companionPausedProvider);
    final tokens = context.tokens;

    return GestureDetector(
      onTap: () {
        final notifier = ref.read(companionNotifierProvider.notifier);
        if (paused) {
          notifier.resume();
          ref.read(companionPausedProvider.notifier).state = false;
        } else {
          notifier.pause();
          ref.read(companionPausedProvider.notifier).state = true;
        }
      },
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: SizedBox(
          height: 32,
          width: 32,
          child: Center(
            child: AnimatedBuilder(
              animation: _controller,
              builder: (context, _) {
                return CustomPaint(
                  size: const Size(24, 24),
                  painter: _BreathPainter(
                    progress: _controller.value,
                    paused: paused,
                    accent: tokens.colors.accent,
                    paused_color: tokens.colors.textTertiary,
                  ),
                );
              },
            ),
          ),
        ),
      ),
    );
  }
}

/// A soft breathing dot: one accent core + one soft glow that expands/contracts.
/// Uses a smooth sine eased with a sub-curve so peaks linger briefly.
class _BreathPainter extends CustomPainter {
  final double progress;
  final bool paused;
  final Color accent;
  // ignore: non_constant_identifier_names
  final Color paused_color;

  _BreathPainter({
    required this.progress,
    required this.paused,
    required this.accent,
    // ignore: non_constant_identifier_names
    required this.paused_color,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);

    if (paused) {
      final paint = Paint()..color = paused_color..style = PaintingStyle.fill;
      canvas.drawCircle(center, 3.0, paint);
      return;
    }

    // Smooth ease-in-out using a half-cosine wave. Range: 0..1..0.
    // progress 0.0 → 1.0 → 0.0 over the cycle.
    final t = 0.5 - 0.5 * cos(progress * 2 * pi);

    // Soft easing of the breath — slight pause at peaks
    final eased = t * t * (3 - 2 * t); // smoothstep

    // Core dot stays mostly constant size, just brightens.
    final coreRadius = 3.0 + eased * 0.6;
    final coreOpacity = 0.65 + eased * 0.35; // 0.65 → 1.0

    // Soft glow expands further with low opacity.
    final glowRadius = 5.0 + eased * 6.0; // 5 → 11
    final glowOpacity = 0.18 - eased * 0.12; // 0.18 → 0.06

    // Outer halo, very subtle.
    final haloRadius = 8.0 + eased * 6.0; // 8 → 14
    final haloOpacity = 0.08 - eased * 0.06; // 0.08 → 0.02

    // Draw halo first (back to front)
    final haloPaint = Paint()
      ..color = accent.withValues(alpha: haloOpacity)
      ..style = PaintingStyle.fill
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 2);
    canvas.drawCircle(center, haloRadius, haloPaint);

    final glowPaint = Paint()
      ..color = accent.withValues(alpha: glowOpacity)
      ..style = PaintingStyle.fill
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 1.5);
    canvas.drawCircle(center, glowRadius, glowPaint);

    final corePaint = Paint()
      ..color = accent.withValues(alpha: coreOpacity)
      ..style = PaintingStyle.fill;
    canvas.drawCircle(center, coreRadius, corePaint);
  }

  @override
  bool shouldRepaint(_BreathPainter oldDelegate) =>
      oldDelegate.progress != progress || oldDelegate.paused != paused;
}
