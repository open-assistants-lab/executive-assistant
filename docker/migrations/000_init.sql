-- ================================================
-- Source: 001_initial_schema.sql
-- ================================================
-- ============================================================================
-- Executive Assistant AI Agent Platform - Complete Initial Schema
-- Version: 2026-01-17 (Thread-only redesign)
-- ============================================================================
-- Run this on a fresh PostgreSQL database
-- ============================================================================

-- ============================================================================
-- LangGraph Checkpoint Tables (required by LangGraph PostgresSaver)
-- ============================================================================

CREATE TABLE IF NOT EXISTS checkpoints (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    parent_checkpoint_id TEXT,
    type TEXT,
    checkpoint JSONB NOT NULL,
    metadata JSONB,
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
);

CREATE TABLE IF NOT EXISTS checkpoint_blobs (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    channel TEXT NOT NULL,
    version TEXT NOT NULL,
    type TEXT,
    blob BYTEA NOT NULL,
    PRIMARY KEY (thread_id, checkpoint_ns, channel, version)
);

CREATE TABLE IF NOT EXISTS checkpoint_writes (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    idx INTEGER NOT NULL,
    channel TEXT NOT NULL,
    type TEXT,
    blob BYTEA,
    task_path TEXT,
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
);

CREATE TABLE IF NOT EXISTS checkpoint_migrations (
    v INT PRIMARY KEY,
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_checkpoints_thread_id ON checkpoints(thread_id);
CREATE INDEX IF NOT EXISTS idx_checkpoint_writes_thread_id ON checkpoint_writes(thread_id);

-- ============================================================================
-- Conversations table (metadata)
-- ============================================================================

CREATE TABLE IF NOT EXISTS conversations (
    conversation_id VARCHAR(255) PRIMARY KEY,
    channel VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    message_count INT DEFAULT 0,
    -- Structured summary (replaces legacy TEXT summary)
    status VARCHAR(20) DEFAULT 'active'  -- active, removed, archived
);

CREATE INDEX IF NOT EXISTS idx_conversations_channel ON conversations(channel);

-- ============================================================================
-- Messages table (audit log)
-- ============================================================================

CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    conversation_id VARCHAR(255) NOT NULL REFERENCES conversations(conversation_id) ON DELETE CASCADE,
    message_id VARCHAR(255),  -- Channel-specific message ID
    role VARCHAR(20) NOT NULL,  -- human, assistant, system, tool
    content TEXT NOT NULL,
    metadata JSONB,  -- Channel-specific data, tool calls, etc.
    created_at TIMESTAMP DEFAULT NOW(),
    token_count INT  -- For cost tracking
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at DESC);

-- Trigger to update conversation updated_at and message_count
CREATE OR REPLACE FUNCTION update_conversation_timestamp() RETURNS TRIGGER AS $$
BEGIN
    UPDATE conversations
    SET updated_at = NOW(),
        message_count = message_count + 1
    WHERE conversation_id = NEW.conversation_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_conversation ON messages;
CREATE TRIGGER trigger_update_conversation
    AFTER INSERT ON messages
    FOR EACH ROW
    EXECUTE FUNCTION update_conversation_timestamp();

-- ============================================================================
-- Reminders table
-- ============================================================================

CREATE TABLE IF NOT EXISTS reminders (
    id SERIAL PRIMARY KEY,
    thread_id VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    due_time TIMESTAMP NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',  -- pending, sent, cancelled, failed
    recurrence VARCHAR(100),               -- NULL = one-time, or cron/interval pattern
    created_at TIMESTAMP DEFAULT NOW(),
    sent_at TIMESTAMP,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_reminders_due_time ON reminders(due_time) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_reminders_thread_id ON reminders(thread_id);
CREATE INDEX IF NOT EXISTS idx_reminders_status ON reminders(status);

-- ============================================================================
-- ============================================================================

-- ============================================================================
-- Scheduled flows table for orchestrator-managed flows
-- ============================================================================

CREATE TABLE IF NOT EXISTS scheduled_flows (
    id SERIAL PRIMARY KEY,
    thread_id VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    task TEXT NOT NULL,                  -- Concrete task description
    flow TEXT NOT NULL,                  -- Execution flow with conditions/loops
    due_time TIMESTAMP NOT NULL,
    status VARCHAR(20) DEFAULT 'pending', -- pending, running, completed, failed, cancelled
    cron VARCHAR(100),                   -- NULL = one-off, or cron expression (e.g., "0 9 * * *")
    created_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    result TEXT                          -- Output from flow execution
);

CREATE INDEX IF NOT EXISTS idx_scheduled_flows_due_time ON scheduled_flows(due_time) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_scheduled_flows_thread_id ON scheduled_flows(thread_id);
CREATE INDEX IF NOT EXISTS idx_scheduled_flows_status ON scheduled_flows(status);

-- ============================================================================
-- File paths ownership tracking
-- ============================================================================

-- Drop legacy tables if present (renamed to tdb_paths/vdb_paths)
DROP TABLE IF EXISTS db_paths;
DROP TABLE IF EXISTS vs_paths;

CREATE TABLE IF NOT EXISTS file_paths (
    thread_id VARCHAR(255) PRIMARY KEY,  -- Sanitized thread_id used as directory name
    channel VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);


-- ============================================================================
-- Transactional database ownership tracking
-- ============================================================================

CREATE TABLE IF NOT EXISTS tdb_paths (
    thread_id VARCHAR(255) PRIMARY KEY,  -- Thread identifier
    tdb_path VARCHAR(512) NOT NULL,  -- Path to the transactional database file
    channel VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tdb_paths_thread ON tdb_paths(thread_id);


-- ============================================================================
-- Vector database ownership tracking
-- ============================================================================

CREATE TABLE IF NOT EXISTS vdb_paths (
    thread_id VARCHAR(255) PRIMARY KEY,
    vdb_path VARCHAR(512) NOT NULL,
    channel VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vdb_paths_thread ON vdb_paths(thread_id);

-- ============================================================================
-- Memory DB ownership tracking
-- ============================================================================

CREATE TABLE IF NOT EXISTS mem_paths (
    thread_id VARCHAR(255) PRIMARY KEY,
    mem_path VARCHAR(512) NOT NULL,
    channel VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mem_paths_thread ON mem_paths(thread_id);

-- ============================================================================
-- Analytics DB ownership tracking
-- ============================================================================

CREATE TABLE IF NOT EXISTS adb_paths (
    thread_id VARCHAR(255) PRIMARY KEY,
    adb_path VARCHAR(512) NOT NULL,
    channel VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_adb_paths_thread ON adb_paths(thread_id);

-- ============================================================================
-- Comments for documentation
-- ============================================================================

COMMENT ON TABLE conversations IS 'Conversation metadata for audit and analytics';
COMMENT ON TABLE messages IS 'Message log for audit, compliance, and record keeping';
COMMENT ON TABLE file_paths IS 'File path ownership tracking for merge/remove operations';
COMMENT ON TABLE tdb_paths IS 'Transactional database ownership tracking per thread';
COMMENT ON TABLE vdb_paths IS 'Vector database ownership tracking per thread';
COMMENT ON TABLE mem_paths IS 'Memory DB ownership tracking for merge/remove operations';
COMMENT ON TABLE adb_paths IS 'Analytics DB ownership tracking for merge/remove operations';

COMMENT ON TABLE reminders IS 'Scheduled reminders for users with optional recurrence';
COMMENT ON COLUMN reminders.recurrence IS 'NULL for one-time, or pattern like "daily at 9am", "weekly"';


COMMENT ON TABLE scheduled_flows IS 'Scheduled flows that execute flow agents at specific times';
COMMENT ON COLUMN scheduled_flows.task IS 'Concrete task description (e.g., "Check Amazon price for B08X12345")';
COMMENT ON COLUMN scheduled_flows.flow IS 'Execution flow (e.g., "fetch price → if < $100 notify, else log")';
COMMENT ON COLUMN scheduled_flows.cron IS 'NULL for one-off, or cron expression for recurring flows';
COMMENT ON COLUMN scheduled_flows.result IS 'Output text from flow execution';
