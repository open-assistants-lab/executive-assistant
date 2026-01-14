# TODO

## Reminder Feature (In Progress)

- [ ] Install APScheduler dependency
- [ ] Create migrations/004_reminders.sql
- [ ] Create src/cassey/storage/reminder.py
- [ ] Create src/cassey/tools/reminder_tools.py (set, list, cancel, edit)
- [ ] Create src/cassey/scheduler.py (APScheduler integration)
- [ ] Create src/cassey/channels/email.py
- [ ] Add /reminders bot command
- [ ] Test reminder creation and sending

## Design (Locked In)

**Scheduler:** APScheduler + DB persistence
- Load pending reminders on startup
- Poll DB every 60s for new reminders
- Exact timing for fired jobs
- DB as source of truth for observability

**Channels:** Telegram, Email (extensible)
- Each channel implements send_notification(user_id, message)

**Reminder Tools:**
- `set_reminder(message, time, recurrence)` - Create new reminder
- `list_reminders()` - Show user's active reminders
- `cancel_reminder(reminder_id)` - Cancel a pending reminder
- `edit_reminder(reminder_id, message, time, recurrence)` - Edit existing reminder

**Database:**
```sql
CREATE TABLE reminders (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    thread_ids TEXT[],
    message TEXT NOT NULL,
    due_time TIMESTAMP NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    recurrence VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    sent_at TIMESTAMP,
    error_message TEXT
);
```
