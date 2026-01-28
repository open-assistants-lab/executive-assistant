# Organization

Description: Learn to manage your calendar, set reminders, maintain task lists, and create structure for your day and week.

Tags: personal, organization, calendar, reminders, scheduling, structure

## Overview

Organization systems help you stay on top of commitments and find time for what matters. This skill covers:

1. **Calendar Management** - Events, appointments, time blocking
2. **Reminders** - Time-based notifications
3. **Task Lists** - Todo tracking and prioritization
4. **Daily Structure** - Routines and time management

**Key Principle:** Your calendar reflects your priorities. Organize proactively, not reactively.

---

## Calendar Management

### Time Blocking

**Reserve blocks of time for specific activities.**

```python
# Create calendar events table
create_tdb_table(
    "calendar_events",
    columns="date,start_time,end_time,title,category,notes"
)

# Add time blocks
insert_tdb_table("calendar_events", [
    {"date": "2025-01-20", "start_time": "09:00", "end_time": "11:00", "title": "Deep Work - Project X", "category": "work", "notes": "No interruptions"},
    {"date": "2025-01-20", "start_time": "11:00", "end_time": "12:00", "title": "Team Standup", "category": "meeting", "notes": ""},
    {"date": "2025-01-20", "start_time": "13:00", "end_time": "14:00", "title": "Exercise", "category": "personal", "notes": "Gym"},
    {"date": "2025-01-20", "start_time": "14:00", "end_time": "16:00", "title": "Admin Tasks", "category": "work", "notes": "Email, planning"},
    {"date": "2025-01-20", "start_time": "16:00", "end_time": "17:00", "title": "Learning", "category": "growth", "notes": "Read documentation"}
])
```

### Daily Schedule Query

```python
# View today's schedule
query_tdb("""
    SELECT
        start_time,
        end_time,
        title,
        category
    FROM calendar_events
    WHERE date = '2025-01-20'
    ORDER BY start_time
""")
```

### Weekly Overview

```python
# Week at a glance
query_tdb("""
    SELECT
        date,
        category,
        SUM(strftime('%s', end_time) - strftime('%s', start_time)) / 3600.0 as hours
    FROM calendar_events
    WHERE date >= '2025-01-20' AND date < '2025-01-27'
    GROUP BY date, category
    ORDER BY date, category
""")
```

---

## Reminder System

### Setting Reminders

**Use flexible dateparser syntax.**

```python
# Set various reminders
reminder_set("Team standup", "today 11am")
reminder_set("Submit weekly report", "every Friday 5pm", recurrence="weekly")
reminder_set("Pay rent", "1st of every month", recurrence="monthly")
reminder_set("Quarterly review", "every 3 months", recurrence="quarterly")
reminder_set("Doctor appointment", "2025-02-15 10:00")
```

### Reminder Categories

**Personal Reminders:**
```python
# Health & Wellness
reminder_set("Take vitamins", "every day 8am", recurrence="daily")
reminder_set("Gym workout", "Mon, Wed, Fri 6pm", recurrence="weekly")

# Bills & Deadlines
reminder_set("Credit card payment", "15th of every month", recurrence="monthly")
reminder_set("Quarterly taxes", "2025-04-15", recurrence="quarterly")

# Special Events
reminder_set("Birthday party", "2025-03-20 7pm")
reminder_set("Conference", "2025-05-10 9am")
```

### Managing Reminders

```python
# List pending reminders
reminder_list()

# List all reminders (including completed)
reminder_list(status="all")

# Cancel reminder
reminder_cancel("reminder_id")

# Edit reminder
reminder_edit("reminder_id", new_time="tomorrow 3pm")
```

---

## Task Management

### Todo Lists

**Track actionable tasks.**

```python
# Create tasks table
create_tdb_table(
    "tasks",
    columns="title,priority,status,due_date,category,notes"
)

# Add tasks
insert_tdb_table("tasks", [
    {"title": "Finish project proposal", "priority": "high", "status": "pending", "due_date": "2025-01-25", "category": "work"},
    {"title": "Call dentist", "priority": "medium", "status": "pending", "due_date": "2025-01-22", "category": "personal"},
    {"title": "Review code PR", "priority": "high", "status": "pending", "due_date": "2025-01-20", "category": "work"}
])
```

### Prioritization

**View tasks by priority:**
```python
# High priority tasks due soon
query_tdb("""
    SELECT *
    FROM tasks
    WHERE priority = 'high'
    AND status = 'pending'
    ORDER BY due_date ASC
""")
```

### Daily Task Workflow

```python
# 1. Check today's tasks
today_tasks = query_tdb("""
    SELECT *
    FROM tasks
    WHERE date(due_date) = CURRENT_DATE
    AND status = 'pending'
    ORDER BY priority DESC, due_date ASC
""")

# 2. Set reminders for deadlines
for task in today_tasks:
    if task['due_date']:
        # Parse time and set reminder
        reminder_set(f"Task due: {task['title']}", task['due_date'])

# 3. Mark complete when done
# query_tdb("UPDATE tasks SET status = 'complete' WHERE id = X")
```

---

## Daily Structure

### Morning Routine

```python
# Morning template
morning_events = [
    {"time": "07:00", "activity": "Wake up", "duration": 0},
    {"time": "07:30", "activity": "Exercise", "duration": 60},
    {"time": "08:30", "activity": "Shower & breakfast", "duration": 30},
    {"time": "09:00", "activity": "Deep work block", "duration": 120}
]
```

### Time Templates

**Work Day Structure:**
```python
# Create day templates
work_day = {
    "09:00-11:00": "Deep work (no meetings)",
    "11:00-12:00": "Collaboration time",
    "12:00-13:00": "Lunch break",
    "13:00-15:00": "Meetings and calls",
    "15:00-16:30": "Focus work",
    "16:30-17:00": "Admin and planning",
    "17:00-18:00": "Learning time"
}
```

### Weekly Template

```python
# Weekly structure
weekly_template = {
    "Monday": "Planning + Deep work",
    "Tuesday": "Meetings + Collaboration",
    "Wednesday": "Deep work blocks",
    "Thursday": "Focus work + Learning",
    "Friday": "Admin + Review + Next week planning",
    "Saturday": "Personal projects",
    "Sunday": "Rest + Family"
}
```

---

## Workflow Integration

### Daily Organization Workflow

```python
# 1. Check today's calendar
calendar = query_tdb("""
    SELECT * FROM calendar_events
    WHERE date = CURRENT_DATE
    ORDER BY start_time
""")

# 2. Check today's reminders
reminders = reminder_list(status="pending")

# 3. Check today's tasks
tasks = query_tdb("""
    SELECT * FROM tasks
    WHERE due_date = CURRENT_DATE
    ORDER BY priority DESC
""")

# 4. Generate daily agenda
agenda = f"""# Daily Agenda - {date.today()}

## Schedule
{format_calendar(calendar)}

## Reminders
{format_reminders(reminders)}

## Tasks
{format_tasks(tasks)}
"""

write_file(f"agenda/{date.today()}.md", agenda)
```

### Weekly Review Workflow

```python
# 1. Review past week
past_week = query_tdb("""
    SELECT
        strftime('%Y-%W', date) as week,
        category,
        SUM(hours) as total_hours
    FROM calendar_events
    WHERE date >= '2025-01-13' AND date < '2025-01-20'
    GROUP BY week, category
""")

# 2. Review task completion
tasks_done = query_tdb("""
    SELECT
        date(due_date) as day,
        COUNT(*) as completed,
        category
    FROM tasks
    WHERE due_date >= '2025-01-13' AND due_date < '2025-01-20'
    AND status = 'complete'
    GROUP BY day, category
""")

# 3. Plan next week
next_week_tasks = query_tdb("""
    SELECT *
    FROM tasks
    WHERE due_date >= '2025-01-20' AND due_date < '2025-01-27'
    ORDER BY due_date ASC
""")

# 4. Update calendar
# Add time blocks for next week based on priorities
```

---

## Best Practices

### ✅ DO

- **Time block proactively** - Schedule important work first
- **Set reminders early** - Don't rely on memory
- **Prioritize tasks** - Not everything is urgent
- **Maintain routines** - Consistent daily structure
- **Plan tomorrow tonight** - Wake up with clear plan
- **Review weekly** - Adjust based on what works
- **Protect deep work time** - No meetings, focus blocks
- **Include buffer time** - Things take longer than expected

### ❌ DON'T

- **Don't over-schedule** - Leave white space
- **Don't ignore priorities** - Not all tasks equal
- **Don't forget breaks** - Rest is productive too
- **Don't react only** - Proactive vs reactive calendar
- **Don't multitask** - One thing at a time
- **Don't skip reviews** - Weekly check-ins matter
- **Don't plan every minute** - Leave flexibility
- **Don't forget personal time** - Work-life balance

---

## Quick Reference

**Calendar Queries:**
- Today's schedule: `WHERE date = CURRENT_DATE ORDER BY start_time`
- Week overview: `GROUP BY date, category ORDER BY date`
- Time used: `SUM(end_time - start_time) GROUP BY category`

**Reminder Commands:**
- Set: `reminder_set("task", "time")`
- List: `reminder_list()`
- Cancel: `reminder_cancel("id")`
- Edit: `reminder_edit("id", new_time="...")`

**Task Queries:**
- Due today: `WHERE due_date = CURRENT_DATE`
- High priority: `WHERE priority = 'high' ORDER BY due_date`
- Overdue: `WHERE due_date < CURRENT_DATE AND status = 'pending'`

**Daily Workflow:**
1. Check calendar events
2. Check reminders
3. Check tasks
4. Execute schedule
5. Mark completions
6. Plan tomorrow

**Weekly Workflow:**
1. Review past week (calendar, tasks)
2. Check pending reminders
3. Review goal progress
4. Plan next week
5. Update calendar
6. Adjust as needed

---

## Summary

**Organization Systems:**
- **Calendar** - Events, time blocking, structure
- **Reminders** - Notifications, deadlines, recurring tasks
- **Tasks** - Todo lists, prioritization, tracking
- **Routines** - Daily/weekly templates

**Key Principles:**
- Proactive scheduling (plan ahead)
- Clear priorities (not all urgent)
- Consistent routines (daily structure)
- Regular reviews (weekly adjustment)
- Protect deep work (focus blocks)
- Include personal time (balance)

**Tools:**
- `calendar_events` table for schedule
- `reminder_set` for notifications
- `tasks` table for todo tracking
- Queries to view schedule, filter tasks
- Daily/weekly workflows

**Remember:** Your calendar reflects your priorities. Organize intentionally.

Good organization = less stress, more focus, better results.
