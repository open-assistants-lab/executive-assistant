# Task Tracking

Description: Learn to track timesheets, habits, and expenses effectively with structured data and regular updates.

Tags: personal, tracking, tasks, timesheets, habits, expenses

## Overview

Task tracking helps you understand where your time and money go. This skill covers three common tracking scenarios:

1. **Timesheets** - Track work hours by project
2. **Habits** - Track daily habits and streaks
3. **Expenses** - Track spending and budget

**Key Principle:** Consistent tracking provides data for insights and improvements.

---

## Timesheet Tracking

### Setup

```python
# Create timesheet table
create_db_table(
    "timesheets",
    columns="date,project,hours,description,tags"
)
```

### Daily Logging

```python
# Log work
insert_db_table(
    "timesheets",
    '[{"date": "2025-01-19", "project": "Executive Assistant", "hours": 4, "description": "Skills implementation", "tags": "development"}]'
)
```

### Reporting

```python
# Weekly summary
query_db("""
    SELECT
        project,
        SUM(hours) as total_hours,
        COUNT(*) as entries
    FROM timesheets
    WHERE date >= '2025-01-13'
    GROUP BY project
""")

# Daily breakdown
query_db("""
    SELECT
        date,
        SUM(hours) as total_hours
    FROM timesheets
    WHERE date >= '2025-01-13'
    GROUP BY date
    ORDER BY date
""")
```

---

## Habit Tracking

### Setup

```python
# Create habit tracker
create_db_table(
    "habits",
    columns="date,habit,completed,notes,streak"
)
```

### Daily Logging

```python
# Mark habits complete
insert_db_table(
    "habits",
    '[{"date": "2025-01-19", "habit": "exercise", "completed": true, "notes": "30min run", "streak": 5}]'
)
```

### Streak Calculation

```python
# Calculate streaks
query_db("""
    WITH ranked AS (
        SELECT
            habit,
            date,
            completed,
            ROW_NUMBER() OVER (PARTITION BY habit ORDER BY date DESC) as rn
        FROM habits
        WHERE completed = 1
    ),
    streaks AS (
        SELECT
            habit,
            date,
            ROW_NUMBER() OVER (PARTITION BY habit ORDER BY date ASC) as streak_num
        FROM ranked
        WHERE rn = ROW_NUMBER() OVER (PARTITION BY habit ORDER BY date DESC)
    )
    SELECT
        habit,
        MAX(streak_num) as current_streak
    FROM streaks
    GROUP BY habit
""")
```

### Habit Consistency

```python
# Completion rate by habit
query_db("""
    SELECT
        habit,
        COUNT(*) as total_days,
        SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) as completed_days,
        ROUND(SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as completion_rate
    FROM habits
    GROUP BY habit
""")
```

---

## Expense Tracking

### Setup

```python
# Create expense tracker
create_db_table(
    "expenses",
    columns="date,category,amount,description,vendor"
)
```

### Daily Logging

```python
# Log expenses
insert_db_table(
    "expenses",
    '[{"date": "2025-01-19", "category": "groceries", "amount": 45.50, "description": "Weekly shopping", "vendor": "Whole Foods"}]'
)
```

### Budget Analysis

```python
# Spending by category
query_db("""
    SELECT
        category,
        SUM(amount) as total,
        COUNT(*) as transactions
    FROM expenses
    WHERE date >= '2025-01-01'
    GROUP BY category
    ORDER BY total DESC
""")

# Monthly trend
query_db("""
    SELECT
        strftime('%Y-%m', date) as month,
        SUM(amount) as total_spent
    FROM expenses
    GROUP BY month
    ORDER BY month DESC
""")
```

### Budget Comparison

```python
# Compare to budget
budget = 500  # Monthly budget
actual = query_db("""
    SELECT SUM(amount) as total
    FROM expenses
    WHERE strftime('%Y-%m', date) = '2025-01'
""")[0]['total']

remaining = budget - actual
pct_used = (actual / budget) * 100

if pct_used > 80:
    print(f"Warning: Used {pct_used:.1f}% of budget")
```

---

## Common Queries

### Time Analysis

**Productive hours per day:**
```python
query_db("""
    SELECT
        date,
        SUM(hours) as total_hours
    FROM timesheets
    GROUP BY date
    ORDER BY date DESC
    LIMIT 7
""")
```

**Project distribution:**
```python
query_db("""
    SELECT
        project,
        SUM(hours) as total_hours,
        ROUND(SUM(hours) * 100.0 / (SELECT SUM(hours) FROM timesheets), 1) as percentage
    FROM timesheets
    WHERE date >= '2025-01-01'
    GROUP BY project
    ORDER BY total_hours DESC
""")
```

### Habit Analysis

**Best performing habits:**
```python
query_db("""
    SELECT
        habit,
        ROUND(AVG(CASE WHEN completed = 1 THEN 1 ELSE 0 END) * 100, 1) as success_rate
    FROM habits
    GROUP BY habit
    ORDER BY success_rate DESC
""")
```

**Habit streaks:**
```python
query_db("""
    SELECT
        habit,
        MAX(streak) as longest_streak
    FROM habits
    WHERE completed = 1
    GROUP BY habit
    ORDER BY longest_streak DESC
""")
```

### Expense Analysis

**Biggest expenses:**
```python
query_db("""
    SELECT
        description,
        amount,
        date
    FROM expenses
    ORDER BY amount DESC
    LIMIT 10
""")
```

**Spending trends:**
```python
query_db("""
    SELECT
        strftime('%Y-%m', date) as month,
        category,
        SUM(amount) as total
    FROM expenses
    GROUP BY month, category
    ORDER BY month DESC, total DESC
""")
```

---

## Workflows

### Daily Workflow

```python
# 1. Log timesheet entries
insert_db_table("timesheets", '[...]')

# 2. Mark habits
insert_db_table("habits", '[...]')

# 3. Log expenses
insert_db_table("expenses", '[...]')

# 4. Review progress
query_db("SELECT * FROM timesheets WHERE date = '2025-01-19'")
```

### Weekly Workflow

```python
# 1. Generate weekly timesheet report
timesheet_report = query_db("""
    SELECT project, SUM(hours) as hours
    FROM timesheets
    WHERE date >= '2025-01-13'
    GROUP BY project
""")

# 2. Check habit consistency
habit_report = query_db("""
    SELECT
        habit,
        SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) * 1.0 / COUNT(*) as rate
    FROM habits
    WHERE date >= '2025-01-13'
    GROUP BY habit
""")

# 3. Review spending
expense_report = query_db("""
    SELECT category, SUM(amount) as total
    FROM expenses
    WHERE date >= '2025-01-13'
    GROUP BY category
""")

# 4. Save weekly review
write_file("reports/weekly_review.md", format_review(timesheet_report, habit_report, expense_report))
```

---

## Best Practices

### ✅ DO

- **Track daily** - Consistency is key
- **Be specific** - Detailed descriptions help later
- **Use categories** - Organize into meaningful groups
- **Add tags** - Helps with filtering
- **Review weekly** - Check progress regularly
- **Set goals** - Track against targets
- **Automate reminders** - Don't rely on memory

### ❌ DON'T

- **Don't skip days** - Gaps ruin trends
- **Don't be vague** - "Work" is less useful than "Skills implementation"
- **Don't forget categories** - Hard to analyze without grouping
- **Don't over-complicate** - Start simple
- **Don't ignore patterns** - Look for trends in data
- **Don't track too much** - 3-5 metrics is enough

---

## Quick Reference

**Timesheet Queries:**
- Daily log: `INSERT INTO timesheets VALUES (...)`
- Weekly summary: `SELECT project, SUM(hours) GROUP BY project`
- Project breakdown: `SELECT * WHERE project = 'X'`

**Habit Queries:**
- Daily log: `INSERT INTO habits VALUES (...)`
- Streaks: `MAX(streak) GROUP BY habit`
- Completion rate: `AVG(completed) GROUP BY habit`

**Expense Queries:**
- Daily log: `INSERT INTO expenses VALUES (...)`
- By category: `SELECT category, SUM(amount) GROUP BY category`
- Monthly trend: `GROUP BY strftime('%Y-%m', date)`

**Common Workflows:**
- Daily: Log all three types
- Weekly: Generate reports and review
- Monthly: Export data and analyze trends

---

## Summary

**Track consistently** - Daily logging beats perfect weekly recall.

**Three main types:**
- **Timesheets:** Work hours by project
- **Habits:** Daily activities with streaks
- **Expenses:** Spending by category

**Key patterns:**
- Create table → Insert data → Query for insights
- Use categories for grouping
- Review weekly/monthly for patterns
- Set goals and track progress

**Storage:** Always use DB for tracking (structured, queryable, aggregatable).

What gets measured gets managed. Start tracking today.
