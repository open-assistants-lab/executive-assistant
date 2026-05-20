import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../providers/companion_provider.dart';
import '../../theme/app_theme.dart';

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
                color: context.tokens.colors.bgSurface,
                borderRadius: BorderRadius.circular(context.tokens.radius.lg),
                border: Border(left: BorderSide(color: context.tokens.colors.warning, width: 3)),
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
                  Icon(Symbols.warning, size: 18, color: context.tokens.colors.warning),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      activeToast.message,
                      style: context.tokens.typography.textTheme.bodyLarge!.copyWith(fontSize: 13, color: context.tokens.colors.textPrimary),
                    ),
                  ),
                  const SizedBox(width: 12),
                  TextButton(
                    onPressed: () {
                      ref.read(companionNotifierProvider.notifier).dismiss(activeToast.id);
                      _dismiss();
                    },
                    child: Text('Dismiss', style: context.tokens.typography.textTheme.bodySmall!.copyWith(color: context.tokens.colors.textSecondary)),
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
