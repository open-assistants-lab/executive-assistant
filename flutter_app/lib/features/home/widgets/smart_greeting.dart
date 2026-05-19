import 'package:flutter/material.dart';
import '../../../theme/app_theme.dart';

class SmartGreeting extends StatelessWidget {
  const SmartGreeting({super.key});

  @override
  Widget build(BuildContext context) {
    final hour = DateTime.now().hour;
    final greeting = hour < 12
        ? 'Good morning'
        : hour < 17
            ? 'Good afternoon'
            : 'Good evening';

    final dayName = _dayName(DateTime.now().weekday);
    final month = _monthName(DateTime.now().month);
    final day = DateTime.now().day;

    return Padding(
      padding: EdgeInsets.symmetric(
        horizontal: context.tokens.spacing.xl,
        vertical: context.tokens.spacing.md,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            greeting,
            style: context.tokens.typography.textTheme.displayLarge!.copyWith(
              color: context.tokens.colors.accent,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            '$dayName, $month $day',
            style: context.tokens.typography.textTheme.bodyLarge!.copyWith(
              color: context.tokens.colors.textSecondary,
            ),
          ),
        ],
      ),
    );
  }

  String _dayName(int weekday) {
    const days = [
      '',
      'Monday',
      'Tuesday',
      'Wednesday',
      'Thursday',
      'Friday',
      'Saturday',
      'Sunday'
    ];
    return days[weekday];
  }

  String _monthName(int month) {
    const months = [
      '',
      'January',
      'February',
      'March',
      'April',
      'May',
      'June',
      'July',
      'August',
      'September',
      'October',
      'November',
      'December'
    ];
    return months[month];
  }
}