import 'dart:math';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../theme/app_colors.dart';
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
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 4),
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
      onLongPress: () {},
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: SizedBox(
          height: 32,
          child: Center(
            child: AnimatedBuilder(
              animation: _controller,
              builder: (context, _) {
                return CustomPaint(
                  size: const Size(20, 20),
                  painter: _PulsePainter(
                    progress: _controller.value,
                    paused: paused,
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

class _PulsePainter extends CustomPainter {
  final double progress;
  final bool paused;

  _PulsePainter({required this.progress, required this.paused});

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final baseRadius = size.width / 4;

    if (paused) {
      final paint = Paint()
        ..color = AppColors.textDim
        ..style = PaintingStyle.fill;
      canvas.drawCircle(center, baseRadius * 0.5, paint);
      return;
    }

    final innerPaint = Paint()
      ..color = AppColors.accent
      ..style = PaintingStyle.fill;

    final middleAlpha = ((1 - progress) * 100).toInt().clamp(0, 100);
    final middlePaint = Paint()
      ..color = AppColors.accent.withAlpha(25 + middleAlpha)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.5;

    final outerAlpha = ((sin(progress * 2 * pi) * 0.5 + 0.5) * 80).toInt();
    final outerPaint = Paint()
      ..color = AppColors.accent.withAlpha(outerAlpha)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1;

    final cyclePhase = (progress * 2 * pi);
    final middleRadius = baseRadius * 1.2 + sin(cyclePhase) * 1.5;
    final outerRadius = baseRadius * 1.6 + cos(cyclePhase * 0.7) * 2;

    canvas.drawCircle(center, baseRadius * 0.55, innerPaint);
    canvas.drawCircle(center, middleRadius, middlePaint);
    canvas.drawCircle(center, outerRadius, outerPaint);
  }

  @override
  bool shouldRepaint(_PulsePainter oldDelegate) => true;
}
