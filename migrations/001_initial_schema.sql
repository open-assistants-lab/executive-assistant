-- Initial schema for Cassey AI Agent Platform
-- Run this on a fresh PostgreSQL database

-- ============================================================================
-- LangGraph Checkpoint Tables (required by LangGraph)
-- ============================================================================

CREATE TABLE IF NOT EXISTS checkpoint_blobs (
    id SERIAL PRIMARY KEY,
    thread_id VARCHAR(255) NOT NULL,
    checkpoint_id VARCHAR(255) NOT NULL,
    checkpoint NUMERIC NOT NULL,
    blob BYTEA,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(thread_id, checkpoint_id)
);

CREATE TABLE IF NOT EXISTS checkpoint_writes (
    id SERIAL PRIMARY KEY,
    thread_id VARCHAR(255) NOT NULL,
    checkpoint_id VARCHAR(255) NOT NULL,
    checkpoint NUMERIC NOT NULL,
    task_id VARCHAR(255),
    idx NUMERIC NOT NULL,
    channel VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    type VARCHAR(255) NOT NULL
);

CREATE TABLE IF NOT EXISTS checkpoint_migrations (
    id SERIAL PRIMARY KEY,
    checkpoint NUMERIC NOT NULL,
    old_checkpoint_id VARCHAR(255),
    new_checkpoint_id VARCHAR(255),
    thread_id VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Checkpoints table for LangGraph state
CREATE TABLE IF NOT EXISTS checkpoints (
    thread_id VARCHAR(255) PRIMARY KEY,
    checkpoint NUMERIC NOT NULL,
    parent_checkpoint_id VARCHAR(255),
    checkpoint_ns VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_checkpoint_blobs_thread ON checkpoint_blobs(thread_id);
CREATE INDEX IF NOT EXISTS idx_checkpoint_blobs_checkpoint ON checkpoint_blobs(checkpoint);
CREATE INDEX IF NOT EXISTS idx_checkpoint_writes_thread ON checkpoint_writes(thread_id);
CREATE INDEX IF NOT EXISTS idx_checkpoint_writes_checkpoint ON checkpoint_writes(checkpoint);

-- ============================================================================
-- Audit and Ownership Tables
-- ============================================================================

-- Conversations table (metadata)
CREATE TABLE IF NOT EXISTS conversations (
    conversation_id VARCHAR(255) PRIMARY KEY,
    user_id VARCHAR(255),
    channel VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    message_count INT DEFAULT 0,
    summary TEXT,
    status VARCHAR(20) DEFAULT 'active'  -- active, removed, archived
);

-- Messages table (audit log)
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

-- File paths ownership tracking
CREATE TABLE IF NOT EXISTS file_paths (
    thread_id VARCHAR(255) PRIMARY KEY,  -- Sanitized thread_id used as directory name
    user_id VARCHAR(255),  -- NULL until merge, then set to merged user_id
    channel VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Database ownership tracking
CREATE TABLE IF NOT EXISTS db_paths (
    thread_id VARCHAR(255) PRIMARY KEY,  -- Thread identifier
    db_path VARCHAR(512) NOT NULL,  -- Path to the database file
    user_id VARCHAR(255),  -- NULL until merge, then set to merged user_id
    channel VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- User registry operations tracking (merge, split, remove)
CREATE TABLE IF NOT EXISTS user_registry (
    id SERIAL PRIMARY KEY,
    operation_type VARCHAR(20) NOT NULL,  -- merge, split, remove
    source_thread_ids TEXT[] NOT NULL,     -- Array of thread IDs affected
    target_user_id VARCHAR(255),           -- User ID (for merge operations)
    channel VARCHAR(50),                    -- Channel (telegram, http, etc.)
    status VARCHAR(20) DEFAULT 'pending',   -- pending, completed, failed, rolled_back
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);

-- ============================================================================
-- Indexes
-- ============================================================================

-- Messages indexes
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at DESC);

-- Conversations indexes
CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_channel ON conversations(channel);

-- File paths indexes
CREATE INDEX IF NOT EXISTS idx_file_paths_user ON file_paths(user_id);

-- Database paths indexes
CREATE INDEX IF NOT EXISTS idx_db_paths_user ON db_paths(user_id);
CREATE INDEX IF NOT EXISTS idx_db_paths_thread ON db_paths(thread_id);

-- User registry indexes
CREATE INDEX IF NOT EXISTS idx_user_registry_target_user ON user_registry(target_user_id);
CREATE INDEX IF NOT EXISTS idx_user_registry_thread_ids ON user_registry USING GIN(source_thread_ids);
CREATE INDEX IF NOT EXISTS idx_user_registry_created_at ON user_registry(created_at DESC);

-- ============================================================================
-- Triggers
-- ============================================================================

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
-- Comments
-- ============================================================================

COMMENT ON TABLE conversations IS 'Conversation metadata for audit and analytics';
COMMENT ON TABLE messages IS 'Message log for audit, compliance, and record keeping';
COMMENT ON TABLE file_paths IS 'File path ownership tracking for merge/remove operations';
COMMENT ON TABLE db_paths IS 'Database ownership tracking for merge/remove operations';
COMMENT ON TABLE user_registry IS 'Tracks merge/split/remove operations for audit and recovery';

COMMENT ON COLUMN user_registry.operation_type IS 'Type: merge (threads→user), split (user→threads), remove (delete)';
COMMENT ON COLUMN user_registry.source_thread_ids IS 'Thread IDs affected by this operation';
COMMENT ON COLUMN user_registry.target_user_id IS 'Target user ID for merge, or source user for split';
