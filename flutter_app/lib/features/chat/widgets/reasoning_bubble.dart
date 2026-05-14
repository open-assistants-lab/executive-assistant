import 'package:flutter/material.dart';
import '../../../theme/app_theme.dart';

class ReasoningBubble extends StatefulWidget {
  final String content;

  const ReasoningBubble({super.key, required this.content});

  @override
  State<ReasoningBubble> createState() => _ReasoningBubbleState();
}

class _ReasoningBubbleState extends State<ReasoningBubble> {
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
    if (widget.content.trim().isEmpty) return const SizedBox.shrink();

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: () => setState(() => _expanded = !_expanded),
          borderRadius: BorderRadius.circular(AppRadius.chip),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
            decoration: BoxDecoration(
              color: AppColors.surface.withAlpha(180),
              borderRadius: BorderRadius.circular(AppRadius.chip),
              border: Border.all(
                color: AppColors.divider.withAlpha(150),
              ),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(Icons.psychology_outlined,
                        size: 16, color: AppColors.textDim),
                    const SizedBox(width: 6),
                    Text(
                      'Agent reasoning',
                      style: AppTypography.caption.copyWith(
                        color: AppColors.textDim,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const Spacer(),
                    AnimatedRotation(
                      turns: _expanded ? 0.5 : 0.0,
                      duration: const Duration(milliseconds: 200),
                      child: Icon(Icons.expand_more,
                          size: 18, color: AppColors.textDim),
                    ),
                  ],
                ),
                if (_expanded) ...[
                  const SizedBox(height: 8),
                  Text(
                    widget.content,
                    style: AppTypography.caption.copyWith(
                      color: AppColors.textSecondary,
                      height: 1.5,
                    ),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}
