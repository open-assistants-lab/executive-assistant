-- Structured Summary Schema for Topic-Based Summarization
-- Addresses context contamination by maintaining separate topics with active/inactive status

-- Add structured_summary JSONB column to conversations table
ALTER TABLE conversations
ADD COLUMN IF NOT EXISTS structured_summary JSONB;

-- Create index on structured_summary for efficient queries
CREATE INDEX IF NOT EXISTS idx_conversations_structured_summary
ON conversations USING GIN (structured_summary);

-- Add column for active request (for quick access without parsing JSON)
ALTER TABLE conversations
ADD COLUMN IF NOT EXISTS active_request TEXT;

-- Create index on active_request for quick lookups
CREATE INDEX IF NOT EXISTS idx_conversations_active_request
ON conversations (active_request);

-- Comments
COMMENT ON COLUMN conversations.structured_summary IS 'Structured summary with topics, facts, decisions, tasks, open questions - JSONB format';
COMMENT ON COLUMN conversations.active_request IS 'Latest user request (intent-first) - always shows current dominant intent';
