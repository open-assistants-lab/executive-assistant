-- Drop Legacy Summary Column (2026-01-16)
-- The codebase now uses structured_summary (JSONB) exclusively.
-- This migration removes the legacy TEXT summary column.

-- Drop the summary column from conversations table
ALTER TABLE conversations DROP COLUMN IF EXISTS summary;

-- Note: structured_summary column remains and is the source of truth
-- for all conversation summarization going forward.
