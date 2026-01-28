# Report Generation

Description: Learn to analyze data, create summaries, and generate reports using queries, aggregations, and formatted output.

Tags: personal, reports, analysis, data, summarization, visualization

## Overview

Report generation transforms raw data into actionable insights. This skill covers:

1. **Data Aggregation** - Summarizing large datasets
2. **Trend Analysis** - Identifying patterns over time
3. **Comparison** - Before/after, category breakdowns
4. **Formatting** - Creating readable, professional reports

**Key Principle:** Good reports tell a story with data.

---

## Report Generation Process

```
┌─────────────────────────────────────────────────────────────┐
│                  Report Generation Process                    │
│                                                               │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────┐ │
│  │ Query   │───▶│ Analyze  │───▶│ Format  │───▶│Save  │ │
│  └──────────┘    └──────────┘    └──────────┘    └──────┘ │
│       │              │               │            │      │
│       ▼              ▼               ▼            ▼      │
│  Raw Data      Aggregations       Markdown     File    │
│  Multiple       Calculations      Tables       Share   │
│  Sources       Trends            Charts       Action  │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## Common Report Types

### Type 1: Summary Report

**Weekly Timesheet Summary**

```python
# Query data
data = query_tdb("""
    SELECT
        project,
        SUM(hours) as total_hours,
        COUNT(*) as entries,
        MIN(date) as first_day,
        MAX(date) as last_day
    FROM timesheets
    WHERE date >= '2025-01-13'
    GROUP BY project
    ORDER BY total_hours DESC
""")

# Format report
report = f"""# Weekly Timesheet Report
**Period:** 2025-01-13 to 2025-01-19

## Summary by Project

| Project | Hours | Entries | Period |
|---------|-------|---------|--------|
"""

for row in data:
    report += f"| {row['project']} | {row['total_hours']} | {row['entries']} | {row['first_day']} to {row['last_day']} |\n"

report += f"\n**Total Hours:** {sum(r['total_hours'] for r in data)}\n"

# Save report
write_file("reports/timesheets_weekly_2025-01-19.md", report)
```

---

### Type 2: Trend Report

**Monthly Expense Trends**

```python
# Query monthly data
data = query_tdb("""
    SELECT
        strftime('%Y-%m', date) as month,
        category,
        SUM(amount) as total
    FROM expenses
    WHERE date >= '2025-01-01'
    GROUP BY month, category
    ORDER BY month, total DESC
""")

# Format with trends
report = "# Monthly Expense Trends\\n\\n"

current_month = None
for row in data:
    if row['month'] != current_month:
        current_month = row['month']
        report += f"## {current_month}\\n\\n"
    report += f"- {row['category']}: ${row['total']:.2f}\\n"

write_file("reports/expense_trends.md", report)
```

---

### Type 3: Comparison Report

**Before/After Analysis**

```python
# Compare two periods
data = query_tdb("""
    WITH periods AS (
        SELECT
            CASE
                WHEN date < '2025-01-15' THEN 'before'
                ELSE 'after'
            END as period,
            hours,
            tasks_completed
        FROM productivity
    )
    SELECT
        period,
        AVG(hours) as avg_hours,
        AVG(tasks_completed) as avg_tasks
    FROM periods
    GROUP BY period
""")

# Format comparison
report = "# Before/After Comparison\\n\\n## New Routine Impact\\n\\n"

for row in data:
    report += f"### {row['period'].title()}\\n"
    report += f"- Average Hours: {row['avg_hours']:.1f}\\n"
    report += f"- Average Tasks: {row['avg_tasks']:.1f}\\n\\n"

write_file("reports/routine_comparison.md", report)
```

---

### Type 4: Progress Report

**Project Milestone Progress**

```python
# Gather data
milestones = query_tdb("""
    SELECT
        project,
        COUNT(*) as total,
        SUM(CASE WHEN status = 'complete' THEN 1 ELSE 0 END) as completed,
        ROUND(SUM(CASE WHEN status = 'complete' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as progress
    FROM project_milestones
    GROUP BY project
""")

blockers = search_vdb("blockers obstacles issues", "meetings")

# Create report
report = f"""# Project Progress Report
**Generated:** {date.today()}

## Milestone Progress

| Project | Completed | Total | Progress |
|---------|-----------|-------|----------|
"""

for row in milestones:
    progress_bar = "█" * int(row['progress'] / 10) + "░" * (10 - int(row['progress'] / 10))
    report += f"| {row['project']} | {row['completed']} | {row['total']} | {row['progress']}% {progress_bar} |\\n"

report += f"\\n## Current Blockers\\n\\n{blockers}"

write_file("reports/project_progress.md", report)
```

---

## Report Templates

### Template 1: Daily Summary

```python
def generate_daily_summary():
    # Gather data
    tasks_completed = query_tdb("SELECT COUNT(*) as count FROM tasks WHERE status = 'complete' AND date = '2025-01-19'")
    hours_worked = query_tdb("SELECT SUM(hours) as total FROM timesheets WHERE date = '2025-01-19'")
    expenses = query_tdb("SELECT SUM(amount) as total FROM expenses WHERE date = '2025-01-19'")
    habits = query_tdb("SELECT * FROM habits WHERE date = '2025-01-19' AND completed = 1")

    # Format
    report = f"""# Daily Summary - {date.today()}

## 📊 Metrics
- Tasks Completed: {tasks_completed[0]['count']}
- Hours Worked: {hours_worked[0]['total'] or 0}
- Money Spent: ${expenses[0]['total'] or 0:.2f}

## ✅ Completed Tasks
{format_tasks(query_tdb("SELECT * FROM tasks WHERE status = 'complete' AND date = '2025-01-19'"))}

## 💰 Expenses
{format_expenses(query_tdb("SELECT * FROM expenses WHERE date = '2025-01-19'"))}

## 🎯 Habits
{format_habits(habits)}
"""
    return report
```

### Template 2: Weekly Review

```python
def generate_weekly_review():
    # Time distribution
    time_data = query_tdb("""
        SELECT project, SUM(hours) as hours
        FROM timesheets
        WHERE date >= '2025-01-13'
        GROUP BY project
    """)

    # Task completion
    task_data = query_tdb("""
        SELECT
            DATE(date) as day,
            SUM(CASE WHEN status = 'complete' THEN 1 ELSE 0 END) as completed,
            COUNT(*) as total
        FROM tasks
        WHERE date >= '2025-01-13'
        GROUP BY DATE(date)
    """)

    # Financial summary
    expense_data = query_tdb("""
        SELECT category, SUM(amount) as total
        FROM expenses
        WHERE date >= '2025-01-13'
        GROUP BY category
    """)

    # Format
    report = f"""# Weekly Review - Week of {get_week_start()}

## ⏰ Time Distribution
{format_table(time_data)}

## ✅ Task Completion
{format_chart(task_data)}

## 💰 Spending
{format_table(expense_data)}

## 📝 Notes & Reflections
{format_notes(search_vdb("week reflection lessons", "journal"))}
"""
    return report
```

### Template 3: Monthly Dashboard

```python
def generate_monthly_dashboard():
    # Key metrics
    metrics = {
        'total_hours': query_tdb("SELECT SUM(hours) FROM timesheets WHERE date LIKE '2025-01%'")[0]['total'],
        'total_expenses': query_tdb("SELECT SUM(amount) FROM expenses WHERE date LIKE '2025-01%'")[0]['total'],
        'tasks_completed': query_tdb("SELECT COUNT(*) FROM tasks WHERE status = 'complete' AND date LIKE '2025-01%'")[0]['count'],
        'habit_success': query_tdb("SELECT ROUND(AVG(completed) * 100, 1) FROM habits WHERE date LIKE '2025-01%'")[0]['avg_completed']
    }

    # Trends
    hourly_trend = query_tdb("""
        SELECT DATE(date) as day, SUM(hours) as hours
        FROM timesheets
        WHERE date LIKE '2025-01%'
        GROUP BY DATE(date)
        ORDER BY day
    """)

    # Format
    report = f"""# Monthly Dashboard - {date.today().strftime('%B %Y')}

## 📊 Key Metrics
- **Total Hours:** {metrics['total_hours']:.1f}
- **Total Expenses:** ${metrics['total_expenses']:.2f}
- **Tasks Completed:** {metrics['tasks_completed']}
- **Habit Success Rate:** {metrics['habit_success']}%

## 📈 Hourly Trend
{format_trend_chart(hourly_trend)}

## 🎯 Top Projects
{format_top_projects()}

## 💡 Insights & Recommendations
{generate_insights(metrics)}
"""
    return report
```

---

## Data Visualization

### Text-Based Charts

**Bar Chart:**
```python
def create_bar_chart(data, label_col, value_col):
    chart = ""
    max_val = max(row[value_col] for row in data)
    for row in data:
        bar_length = int(row[value_col] / max_val * 40)
        bar = "█" * bar_length
        chart += f"{row[label_col]}: {bar} {row[value_col]}\\n"
    return chart
```

**Trend Line:**
```python
def create_trend(data, value_col):
    max_val = max(row[value_col] for row in data)
    trend = ""
    for row in data:
        dots = int(row[value_col] / max_val * 40)
        trend += "." * dots + "\\n"
    return trend
```

### Tables

**Markdown Tables:**
```python
def format_table(data, columns):
    table = "| " + " | ".join(columns) + " |\\n"
    table += "| " + " | ".join(["---"] * len(columns)) + " |\\n"
    for row in data:
        table += "| " + " | ".join(str(row[col]) for col in columns) + " |\\n"
    return table
```

---

## Advanced Reports

### Report with Python Analysis

```python
# Use Python for complex calculations
analysis = execute_python("""
import pandas as pd
import numpy as np

# Load data
df_timesheets = pd.DataFrame(timesheets_data)
df_expenses = pd.DataFrame(expenses_data)

# Calculate correlations
correlation = df_timesheets['hours'].corr(df_expenses['amount'])

# Find outliers
z_scores = np.abs((df_timesheets['hours'] - df_timesheets['hours'].mean()) / df_timesheets['hours'].std())
outliers = df_timesheets[z_scores > 2]

return {
    'correlation': correlation,
    'outliers': outliers.to_dict('records')
}
""")

# Add insights to report
report += f"\\n## Advanced Insights\\n\\n"
report += f"- Work hours vs expenses correlation: {analysis['correlation']:.2f}\\n"
report += f"- Outlier days: {format_outliers(analysis['outliers'])}\\n"
```

### Multi-Source Report

```python
# Combine data from multiple sources
db_data = query_tdb("SELECT * FROM metrics")
vs_insights = search_vdb("performance improvements", "journal")
file_data = read_file("notes/weekly_observations.md")

# Create comprehensive report
report = f"""# Comprehensive Performance Report

## Quantitative Data
{format_data(db_data)}

## Qualitative Insights
{vs_insights}

## Observations
{file_data}

## Synthesis
{synthesize_insights(db_data, vs_insights, file_data)}
"""
```

---

## Export and Sharing

### Export Formats

```python
# Markdown (for viewing)
write_file("report.md", markdown_content)

# CSV (for data analysis)
export_tdb_table("data", "report.csv")

# JSON (for APIs)
json_data = query_tdb("SELECT * FROM data WHERE ...")
write_file("report.json", json.dumps(json_data))
```

### Scheduling Reports

```python
# Generate report daily/weekly
# Use reminders to prompt report generation

# Set weekly reminder
reminder_set("Generate weekly report", "every Friday 5pm", recurrence="weekly")

# When triggered:
report = generate_weekly_review()
write_file(f"reports/weekly_{date.today().isoformat()}.md", report)
```

---

## Best Practices

### ✅ DO

- **Start with question** - What insight do you need?
- **Know your audience** - Executive, team, personal?
- **Tell a story** - Data → Insight → Action
- **Keep it simple** - 3-5 key metrics
- **Use visuals** - Charts, graphs, progress bars
- **Provide context** - Compare to baseline/goals
- **Be consistent** - Same format each time
- **Include recommendations** - Not just data

### ❌ DON'T

- **Don't include everything** - Summarize
- **Don't forget units** - Hours, dollars, percentages
- **Don't ignore context** - What do numbers mean?
- **Don't hide insights** - Highlight key findings
- **Don't make it too long** - Executive summary first
- **Don't use jargon** - Clear, simple language
- **Don't forget actions** - What should reader do?
- **Don't skip validation** - Check data quality first

---

## Quick Reference

**Common Queries:**
- **Totals:** `SELECT SUM(amount) GROUP BY category`
- **Counts:** `SELECT COUNT(*), status GROUP BY status`
- **Averages:** `SELECT AVG(value) GROUP BY category`
- **Trends:** `GROUP BY strftime('%Y-%m', date)`
- **Rankings:** `ORDER BY value DESC LIMIT 10`

**Report Structure:**
1. **Title & Period** - What and when
2. **Summary** - 3-5 key metrics
3. **Details** - Tables, charts, breakdowns
4. **Insights** - What does it mean?
5. **Actions** - What should we do?

**Formatting:**
- Tables for comparison
- Charts for trends
- Progress bars for completion
- Highlights for key points
- Context (vs baseline, vs goal)

---

## Summary

**Report Generation Process:**
1. **Query** - Get raw data
2. **Analyze** - Aggregate, calculate trends
3. **Format** - Create readable output
4. **Save** - Write to file

**Key Report Types:**
- **Summary** - Totals and highlights
- **Trend** - Changes over time
- **Comparison** - Before/after, by category
- **Progress** - Milestones, completion status

**Good Reports:**
- Tell a story with data
- Provide clear insights
- Include actionable recommendations
- Use consistent formatting
- Consider the audience

**Tools Used:**
- `query_tdb` - Aggregate data
- `execute_python` - Complex analysis
- `write_file` - Save report
- `export_tdb_table` - CSV export

Transform data into insights. Make reports actionable.
