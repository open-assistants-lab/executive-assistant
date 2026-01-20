# Progress Tracking

Description: Learn how to measure change over time: establish baselines, track metrics, and analyze trends to understand progress.

Tags: core, infrastructure, progress, metrics, tracking, analysis

## Overview

This skill teaches you how to **measure change over time**. Progress tracking requires three phases:

1. **Baseline** - Establish starting point
2. **Track** - Record consistent measurements
3. **Analyze** - Identify trends and patterns

**Key Principle:** You can't improve what you don't measure. Consistent tracking enables data-driven decisions.

---

## The Progress Tracking Framework

```
┌─────────────────────────────────────────────────────────────┐
│                   Progress Tracking Cycle                     │
│                                                               │
│  ┌──────────┐    ┌──────────┐    ┌──────────────┐         │
│  │ Baseline │───▶│  Track   │───▶│   Analyze    │         │
│  └──────────┘    └──────────┘    └──────────────┘         │
│       │              │                  │                  │
│       ▼              ▼                  ▼                  │
│  Starting      Regular           Trends &                  │
│  Point         Measurements      Insights                  │
│  Reference     Consistency       Comparison                │
│  Target        Frequency         Actionable                │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Establish Baseline

**A baseline is your starting point for comparison.**

### Baseline Components

**Quantitative Baselines:**
- **Current state** - What's the situation now?
- **Starting metrics** - What are we measuring from?
- **Context** - What factors affect the metric?
- **Target** - Where do we want to go?

### Creating Baselines

**Simple Baseline (DB):**
```python
# User: "Track my exercise habits"
create_db_table(
    "exercise_log",
    columns="date,type,duration,intensity,mood"
)

# Establish baseline
insert_db_table(
    "exercise_log",
    '[{"date": "2025-01-19", "type": "running", "duration": 20, "intensity": "medium", "mood": "good"}]'
)

# Get baseline
query_db("SELECT AVG(duration) as avg_duration FROM exercise_log")
# → Baseline: 20 minutes avg
```

**Complex Baseline (Multiple Metrics):**
```python
# User: "Track my productivity"
create_db_table(
    "productivity",
    columns="date,hours_worked,tasks_completed,meetings,energy_level"
)

# Baseline week
insert_db_table("productivity", [
    {"date": "2025-01-13", "hours_worked": 8, "tasks_completed": 5, "meetings": 3, "energy_level": 7},
    {"date": "2025-01-14", "hours_worked": 7.5, "tasks_completed": 4, "meetings": 2, "energy_level": 6},
    # ... full week
])

# Baseline summary
query_db("""
    SELECT
        AVG(hours_worked) as avg_hours,
        AVG(tasks_completed) as avg_tasks,
        AVG(energy_level) as avg_energy
    FROM productivity
    WHERE date BETWEEN '2025-01-13' AND '2025-01-19'
""")
```

---

## Phase 2: Track Consistently

**Consistency is more important than perfection.**

### Tracking Frequency

**Daily Tracking:**
- Habits (exercise, meditation, reading)
- Mood/energy levels
- Time usage (timesheets)
- Financial transactions

```python
# Daily habit tracker
create_db_table(
    "habits",
    columns="date,habit,completed,notes"
)

# Log daily
insert_db_table(
    "habits",
    '[{"date": "2025-01-19", "habit": "exercise", "completed": true, "notes": "30min run"}]'
)
```

**Weekly Tracking:**
- Project milestones
- Budget reviews
- Goal progress
- Performance metrics

```python
# Weekly progress
create_db_table(
    "weekly_progress",
    columns="week,goal,progress_score,blockers,next_steps"
)
```

**Monthly Tracking:**
- Financial summaries
- KPI reviews
- Health metrics
- Strategic goals

### Tracking Best Practices

**✅ DO:**
- Track at consistent times (same day/time each week)
- Use automated reminders
- Keep tracking simple (3-5 key metrics)
- Track immediately after activity
- Use consistent units and formats

**❌ DON'T:**
- Track too many metrics (analysis paralysis)
- Change measurement methods mid-stream
- Skip tracking (gaps ruin trends)
- Track without purpose (know why you're measuring)
- Use subjective scales without calibration

---

## Phase 3: Analyze Trends

**Analysis transforms data into insights.**

### Trend Analysis Patterns

**Simple Trend (Single Metric):**
```python
# User: "Am I exercising more over time?"
query_db("""
    SELECT
        date,
        SUM(duration) as total_minutes
    FROM exercise_log
    WHERE date >= '2025-01-01'
    GROUP BY date
    ORDER BY date ASC
""")
# → See if total_minutes is increasing
```

**Comparison (Before/After):**
```python
# User: "Compare productivity before and after new routine"
query_db("""
    SELECT
        CASE
            WHEN date < '2025-01-15' THEN 'before'
            ELSE 'after'
        END as period,
        AVG(tasks_completed) as avg_tasks
    FROM productivity
    GROUP BY period
""")
```

**Moving Average (Smooth Trends):**
```python
# 7-day moving average
query_db("""
    SELECT
        date,
        AVG(tasks_completed) OVER (
            ORDER BY date
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ) as moving_avg
    FROM productivity
    ORDER BY date
""")
```

**Growth Rate:**
```python
# Week-over-week change
query_db("""
    WITH weekly AS (
        SELECT
            strftime('%Y-%W', date) as week,
            SUM(hours_worked) as total_hours
        FROM productivity
        GROUP BY week
    )
    SELECT
        week,
        total_hours,
        LAG(total_hours) OVER (ORDER BY week) as prev_week,
        ((total_hours - prev_week) / prev_week * 100) as growth_pct
    FROM weekly
""")
```

---

## Common Tracking Scenarios

### Scenario 1: Habit Formation

**Track:** Daily completion, streak length, consistency

```python
# Habit tracking
create_db_table(
    "habit_tracker",
    columns="date,habit,completed,streak"
)

# Calculate streaks
query_db("""
    WITH streaks AS (
        SELECT
            habit,
            date,
            completed,
            CASE
                WHEN completed = 0 THEN 0
                WHEN LAG(completed) OVER (PARTITION BY habit ORDER BY date) = 1 THEN 1
                WHEN LAG(completed) OVER (PARTITION BY habit ORDER BY date) = 0 THEN 1
                ELSE LAG(streak) OVER (PARTITION BY habit ORDER BY date) + 1
            END as streak
        FROM habit_tracker
    )
    SELECT habit, MAX(streak) as current_streak
    FROM streaks
    GROUP BY habit
""")
```

### Scenario 2: Financial Tracking

**Track:** Income, expenses, savings rate, net worth

```python
# Financial tracking
create_db_table(
    "finances",
    columns="date,type,category,amount"
)

# Monthly spending by category
query_db("""
    SELECT
        strftime('%Y-%m', date) as month,
        category,
        SUM(amount) as total
    FROM finances
    WHERE type = 'expense'
    GROUP BY month, category
    ORDER BY month DESC, total DESC
""")

# Savings rate
query_db("""
    WITH monthly AS (
        SELECT
            strftime('%Y-%m', date) as month,
            SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END) as income,
            SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END) as expenses
        FROM finances
        GROUP BY month
    )
    SELECT
        month,
        income,
        expenses,
        (income - expenses) as savings,
        ((income - expenses) / income * 100) as savings_rate
    FROM monthly
    ORDER BY month DESC
""")
```

### Scenario 3: Project Progress

**Track:** Tasks completed, blockers, milestones

```python
# Project tracking
create_db_table(
    "project_milestones",
    columns="project,milestone,status,target_date,actual_date"
)

# Progress report
query_db("""
    SELECT
        project,
        COUNT(*) as total_milestones,
        SUM(CASE WHEN status = 'complete' THEN 1 ELSE 0 END) as completed,
        SUM(CASE WHEN status = 'complete' THEN 1 ELSE 0 END) * 1.0 / COUNT(*) * 100 as progress_pct
    FROM project_milestones
    GROUP BY project
""")
```

---

## Analysis Techniques

### Visual Analysis

**Generate Charts:**
```python
# Export data for visualization
query_db("""
    SELECT date, total_minutes
    FROM exercise_summary
    ORDER BY date
""")

# Write to CSV for charting
export_db_table("exercise_summary", "exercise_trend.csv")
```

### Statistical Analysis

**Identify Patterns:**
```python
# Best performing days
query_db("""
    SELECT
        strftime('%w', date) as day_of_week,
        AVG(tasks_completed) as avg_tasks
    FROM productivity
    GROUP BY day_of_week
    ORDER BY avg_tasks DESC
""")

# Correlations
query_db("""
    SELECT
        energy_level,
        AVG(tasks_completed) as avg_tasks
    FROM productivity
    GROUP BY energy_level
    ORDER BY energy_level
""")
```

---

## Best Practices

### ✅ DO

- **Start simple** - Track 3-5 key metrics
- **Be consistent** - Same time, same method
- **Automate reminders** - Don't rely on memory
- **Review regularly** - Weekly or monthly check-ins
- **Adjust goals** - Update targets based on progress
- **Celebrate wins** - Acknowledge improvements
- **Learn from setbacks** - Analyze what went wrong
- **Share progress** - Accountability helps

### ❌ DON'T

- **Track too much** - More data ≠ more insights
- **Change metrics** - Consistency over time is key
- **Skip measurements** - Gaps ruin trends
- **Ignore context** - Metrics without meaning are useless
- **Compare unfairly** - Compare to your baseline, not others
- **Give up too soon** - Trends need time to emerge
- **Track without acting** - Data must drive decisions
- **Obsess over daily** - Look at weekly/monthly trends

---

## Quick Reference

| What to Track | Storage | Frequency | Key Queries |
|---------------|---------|-----------|-------------|
| Habits | DB | Daily | Streak length, completion rate |
| Finances | DB | Daily/Weekly | Spending by category, savings rate |
| Productivity | DB | Daily | Tasks completed, energy levels |
| Health | DB | Weekly | Weight, sleep, exercise minutes |
| Projects | DB | Weekly | Milestones completed, blockers |
| Goals | DB | Monthly | Progress percentage, time remaining |
| Mood | DB | Daily | Average mood, patterns by day |

**Common Analyses:**
- **Trend:** `GROUP BY date ORDER BY date`
- **Comparison:** `CASE WHEN ... THEN 'before' ELSE 'after' END`
- **Moving Average:** `AVG(...) OVER (ROWS BETWEEN ...)`
- **Growth Rate:** `((current - previous) / previous * 100)`
- **Streaks:** Window functions with `CASE WHEN completed`
- **Percentiles:** `NTILE(100) OVER (ORDER BY metric)`

---

## Summary

**Progress Tracking Cycle:**
1. **Baseline** - Establish starting point
2. **Track** - Record consistent measurements
3. **Analyze** - Identify trends and insights

**Key Principles:**
- Consistency > Perfection
- Simple metrics > Complex dashboards
- Actionable insights > Raw data
- Weekly review > Daily obsession
- Compare self to self (before/after)

**Storage Choice:**
- **DB** for all progress tracking (structured, queryable, aggregatable)
- **VS** for qualitative notes about progress
- **Files** for exported reports and visualizations

You can't improve what you don't measure. Start tracking today.
