import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_typography.dart';
import '../../theme/app_radius.dart';
import '../../providers/companion_provider.dart';

class CompanionToastOverlay extends ConsumerStatefulWidget {
  const CompanionToastOverlay({super.key});

  @override
  ConsumerState<CompanionToastOverlay> createState() => _CompanionToastOverlayState();
}

class _CompanionToastOverlayState extends ConsumerState<CompanionToastOverlay>
    with SingleTickerProviderStateMixin {
  late AnimationController _slideController;
  late Animation<Offset> _slideAnimation;
  Timer? _dismissTimer;
  String? _currentId;

  @override
  void initState() {
    super.initState();
    _slideController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 400),
    );
    _slideAnimation = Tween<Offset>(
      begin: const Offset(0, -1),
      end: Offset.zero,
    ).animate(CurvedAnimation(
      parent: _slideController,
      curve: Curves.easeOutBack,
    ));
  }

  @override
  void dispose() {
    _slideController.dispose();
    _dismissTimer?.cancel();
    super.dispose();
  }

  void _show() {
    _slideController.reset();
    _slideController.forward();
    _dismissTimer?.cancel();
    _dismissTimer = Timer(const Duration(seconds: 8), _dismiss);
  }

  void _dismiss() {
    _dismissTimer?.cancel();
    _slideController.reverse().then((_) {
      if (mounted) ref.read(companionActiveToastProvider.notifier).state = null;
    });
    _currentId = null;
  }

  @override
  Widget build(BuildContext context) {
    final activeToast = ref.watch(companionActiveToastProvider);

    if (activeToast == null) {
      _dismissTimer?.cancel();
      _currentId = null;
      return const SizedBox.shrink();
    }

    if (activeToast.id != _currentId) {
      _currentId = activeToast.id;
      Future.microtask(_show);
    }

    return Align(
      alignment: Alignment.topCenter,
      child: SlideTransition(
        position: _slideAnimation,
        child: GestureDetector(
          onVerticalDragEnd: (details) {
            if (details.primaryVelocity != null && details.primaryVelocity! < -200) {
              _dismiss();
            }
          },
          child: Padding(
            padding: const EdgeInsets.only(top: 12),
            child: Container(
              width: 420,
              margin: const EdgeInsets.symmetric(horizontal: 16),
              decoration: BoxDecoration(
                color: AppColors.surface,
                borderRadius: BorderRadius.circular(AppRadius.card),
                border: const Border(left: BorderSide(color: AppColors.warning, width: 3)),
                boxShadow: [
                  BoxShadow(
                    blurRadius: 16,
                    offset: const Offset(0, 4),
                    color: Colors.black.withAlpha(40),
                  ),
                ],
              ),
              padding: const EdgeInsets.all(16),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(Icons.warning_amber_rounded, size: 18, color: AppColors.warning),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      activeToast.message,
                      style: AppTypography.body.copyWith(fontSize: 13, color: AppColors.textPrimary),
                    ),
                  ),
                  const SizedBox(width: 12),
                  TextButton(
                    onPressed: () {
                      ref.read(companionNotifierProvider.notifier).dismiss(activeToast.id);
                      _dismiss();
                    },
                    child: Text('Dismiss', style: AppTypography.caption.copyWith(color: AppColors.textSecondary)),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
