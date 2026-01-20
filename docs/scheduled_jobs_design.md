# Scheduled Jobs / Flow System Design

## Concept

Executive Assistant writes Python scripts that execute at scheduled times. Jobs chain via file I/O - like a simple workflow system.

## Architecture

```
User: "Schedule daily Amazon price check, notify me if < $100"

Executive Assistant creates:
  1. Script: data/files/telegram_user123/jobs/check_price.py
  2. DB record: { due_time: "tomorrow 9am", script_path: "jobs/check_price.py" }

Scheduler (every 60s):
  1. Finds due jobs (status='pending', due_time <= now)
  2. Executes each script in thread's sandbox
  3. Looks for {job_name}_message.txt → sends to Telegram if exists
  4. Marks job as 'completed' or 'failed'
  5. For recurring jobs: creates next instance
```

## Key Design Decision: Option A (Single Orchestrator Script)

**Why Option A:**
- ✅ Much simpler - scheduler just runs Python script when due
- ✅ Executive Assistant writes Python she already knows
- ✅ All logic visible in one .py file
- ✅ Conditions/loops are native Python (`if/else`, `for/while`)
- ✅ Less DB complexity

**File structure:**
```
data/files/telegram_user123/jobs/
  daily_report.py          # The full flow logic
  daily_report_output.json  # Results from last run
```

## Telegram Notification Pattern

**Problem:** Sandbox cannot directly send Telegram (bot token not exposed)

**Solution:** Message file pattern

```python
# jobs/check_price.py
import json, urllib.request

# Fetch data
response = urllib.request.urlopen("https://api.price.com/item/123")
data = json.loads(response.read())
price = data['price']

# Write output for chaining
with open('jobs/check_price_output.json', 'w') as f:
    json.dump({'price': price}, f)

# CONDITIONAL: Create message if criteria met
if price < 100:
    with open('jobs/check_price_message.txt', 'w') as f:
        f.write(f"🚨 Price alert: ${price}\nhttps://amazon.com/item/123")
```

**Scheduler flow:**
1. Execute job script in sandbox
2. Look for `{job_name}_message.txt`
3. If found → read content → send via Telegram → delete file
4. Mark job as completed

## Features

### Conditions (if/else)
Native Python `if/else` in the script:
```python
if price < 100:
    notify_user()
else:
    log_high_price()
```

### Loops
All loop types supported as native Python:

**Repeat N times:**
```python
for i in range(10):
    process_item(i)
```

**Until condition:**
```python
while True:
    result = check_status()
    if result == 'complete':
        break
    time.sleep(60)
```

**For each item:**
```python
for item in items:
    process(item)
```

### Chaining
Jobs read output from previous jobs:
```python
# job_2.py reads job_1 output
with open('jobs/job_1_output.json') as f:
    data = json.load(f)
```

## Database Schema (Simplified)

```sql
CREATE TABLE scheduled_jobs (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    thread_id VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    due_time TIMESTAMP NOT NULL,
    script_path TEXT NOT NULL,
    status VARCHAR(20) DEFAULT 'pending', -- pending, running, completed, failed, cancelled
    recurrence VARCHAR(100),              -- "daily 9am", "hourly", "weekly"
    created_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT
);

CREATE INDEX idx_scheduled_jobs_due ON scheduled_jobs(due_time, status);
```

## Security

- Reuses existing `python_tool` sandbox
- Thread-scoped directories
- 30 second timeout per job
- Path traversal protection
- File extension whitelist
- No `os.system`, `subprocess`, `eval`

## Files to Create

1. `migrations/005_scheduled_jobs.sql` - DB schema
2. `src/executive_assistant/storage/scheduled_jobs.py` - CRUD operations
3. `src/executive_assistant/tools/scheduled_job_tools.py` - User tools (schedule, list, cancel)
4. `src/executive_assistant/scheduler.py` - Modify to add job execution logic

## No New Dependencies

- APScheduler: Already installed
- Python exec(): Already used in python_tool
- Thread isolation: Already implemented in file_sandbox

## Status

**Design phase complete.** Implementation pending.
