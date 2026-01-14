-- Reminders table for scheduled notifications
-- Run this after 001_initial_schema.sql

CREATE TABLE IF NOT EXISTS reminders (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    thread_ids TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    message TEXT NOT NULL,
    due_time TIMESTAMP NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',  -- pending, sent, cancelled, failed
    recurrence VARCHAR(100),               -- NULL = one-time, or cron/interval pattern
    created_at TIMESTAMP DEFAULT NOW(),
    sent_at TIMESTAMP,
    error_message TEXT
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_reminders_due_time ON reminders(due_time) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_reminders_user_id ON reminders(user_id);
CREATE INDEX IF NOT EXISTS idx_reminders_status ON reminders(status);

-- Comments for documentation
COMMENT ON TABLE reminders IS 'Scheduled reminders for users with optional recurrence';
COMMENT ON COLUMN reminders.thread_ids IS 'Which conversation threads to notify when reminder fires';
COMMENT ON COLUMN reminders.recurrence IS 'NULL for one-time, or pattern like "daily at 9am", "weekly"';
