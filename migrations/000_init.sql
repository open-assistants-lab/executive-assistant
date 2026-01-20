-- ================================================
-- Source: 001_initial_schema.sql
-- ================================================
-- ============================================================================
-- Executive Assistant AI Agent Platform - Complete Initial Schema
-- Version: 2026-01-17 (Workspace-based redesign)
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
-- Users (core identity)
-- ============================================================================

CREATE TABLE IF NOT EXISTS users (
  user_id TEXT PRIMARY KEY,
  status TEXT NOT NULL DEFAULT 'active',  -- active, suspended
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_aliases (
  alias_id TEXT PRIMARY KEY,  -- e.g., anon:{uuid}
  user_id TEXT NOT NULL,      -- canonical user_id
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_status ON users(status);
CREATE INDEX IF NOT EXISTS idx_user_aliases_user ON user_aliases(user_id);

-- ============================================================================
-- Groups (for group workspaces)
-- ============================================================================

CREATE TABLE IF NOT EXISTS groups (
  group_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS group_members (
  group_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'member',  -- admin, member
  joined_at TIMESTAMP DEFAULT NOW(),
  PRIMARY KEY (group_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_groups_name ON groups(name);
CREATE INDEX IF NOT EXISTS idx_group_members_user ON group_members(user_id);

-- ============================================================================
-- Workspaces (supports 3 types via ownership)
-- ============================================================================

CREATE TABLE IF NOT EXISTS workspaces (
  workspace_id TEXT PRIMARY KEY,
  type TEXT NOT NULL,  -- individual | group | public
  name TEXT NOT NULL,  -- Display name

  -- Ownership: exactly one should be set
  owner_user_id TEXT NULL,     -- For individual workspaces
  owner_group_id TEXT NULL,    -- For group workspaces
  owner_system_id TEXT NULL,   -- For public workspace (only "public" allowed)

  created_at TIMESTAMP DEFAULT NOW(),

  -- Ensure exactly one owner is set
  CONSTRAINT has_exactly_one_owner CHECK (
    (owner_user_id IS NOT NULL AND owner_group_id IS NULL AND owner_system_id IS NULL) OR
    (owner_user_id IS NULL AND owner_group_id IS NOT NULL AND owner_system_id IS NULL) OR
    (owner_user_id IS NULL AND owner_group_id IS NULL AND owner_system_id IS NOT NULL)
  ),

  -- owner_system_id is reserved for public workspace only
  CONSTRAINT valid_system_owner CHECK (
    owner_system_id IS NULL OR owner_system_id = 'public'
  )
);

CREATE TABLE IF NOT EXISTS user_workspaces (
  user_id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL UNIQUE,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS group_workspaces (
  group_id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL UNIQUE,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS thread_workspaces (
  thread_id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS workspace_members (
  workspace_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  role TEXT NOT NULL,  -- admin | editor | reader
  granted_by TEXT NULL,     -- Who granted this role
  granted_at TIMESTAMP DEFAULT NOW(),
  PRIMARY KEY (workspace_id, user_id),
  CHECK (role IN ('admin', 'editor', 'reader'))
);

CREATE TABLE IF NOT EXISTS workspace_acl (
  id SERIAL PRIMARY KEY,
  workspace_id TEXT NOT NULL,
  resource_type TEXT NOT NULL,  -- file_folder | kb_collection | db_table | reminder | workflow
  resource_id TEXT NOT NULL,
  target_user_id TEXT NULL,
  target_group_id TEXT NULL,
  permission TEXT NOT NULL,     -- read | write
  created_at TIMESTAMP DEFAULT NOW(),
  expires_at TIMESTAMP NULL,

  -- Exactly one target (user OR group)
  CONSTRAINT acl_has_exactly_one_target CHECK (
    (target_user_id IS NOT NULL AND target_group_id IS NULL) OR
    (target_user_id IS NULL AND target_group_id IS NOT NULL)
  ),

  -- Valid permissions (admin via workspace_members only)
  CONSTRAINT acl_valid_permission CHECK (permission IN ('read', 'write')),

  -- No duplicate grants
  UNIQUE (workspace_id, resource_type, resource_id, target_user_id, target_group_id)
);

CREATE INDEX IF NOT EXISTS idx_workspaces_type ON workspaces(type);
CREATE INDEX IF NOT EXISTS idx_workspaces_owner_user ON workspaces(owner_user_id);
CREATE INDEX IF NOT EXISTS idx_workspaces_owner_group ON workspaces(owner_group_id);
CREATE INDEX IF NOT EXISTS idx_thread_workspaces_workspace ON thread_workspaces(workspace_id);
CREATE INDEX IF NOT EXISTS idx_workspace_members_user ON workspace_members(user_id);
CREATE INDEX IF NOT EXISTS idx_workspace_members_role ON workspace_members(role);
CREATE INDEX IF NOT EXISTS idx_workspace_acl_workspace ON workspace_acl(workspace_id);
CREATE INDEX IF NOT EXISTS idx_workspace_acl_target_user ON workspace_acl(target_user_id);
CREATE INDEX IF NOT EXISTS idx_workspace_acl_target_group ON workspace_acl(target_group_id);
CREATE INDEX IF NOT EXISTS idx_workspace_acl_expires ON workspace_acl(expires_at) WHERE expires_at IS NOT NULL;

-- ============================================================================
-- Foreign Key Constraints (deferred to avoid circular dependency issues)
-- ============================================================================

-- Groups FK
ALTER TABLE group_members DROP CONSTRAINT IF EXISTS fk_group_members_group;
ALTER TABLE group_members DROP CONSTRAINT IF EXISTS fk_group_members_user;
ALTER TABLE group_members
  ADD CONSTRAINT fk_group_members_group
    FOREIGN KEY (group_id) REFERENCES groups(group_id) ON DELETE CASCADE;

ALTER TABLE group_members
  ADD CONSTRAINT fk_group_members_user
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE;

-- Workspaces FK
ALTER TABLE workspaces DROP CONSTRAINT IF EXISTS fk_workspaces_owner_user;
ALTER TABLE workspaces DROP CONSTRAINT IF EXISTS fk_workspaces_owner_group;
ALTER TABLE workspaces
  ADD CONSTRAINT fk_workspaces_owner_user
    FOREIGN KEY (owner_user_id) REFERENCES users(user_id) ON DELETE CASCADE;

ALTER TABLE workspaces
  ADD CONSTRAINT fk_workspaces_owner_group
    FOREIGN KEY (owner_group_id) REFERENCES groups(group_id) ON DELETE CASCADE;

-- Workspace type validation
ALTER TABLE workspaces DROP CONSTRAINT IF EXISTS valid_workspace_type;
ALTER TABLE workspaces
  ADD CONSTRAINT valid_workspace_type
    CHECK (type IN ('individual', 'group', 'public'));

-- User workspaces FK
ALTER TABLE user_workspaces DROP CONSTRAINT IF EXISTS fk_user_workspaces_workspace;
ALTER TABLE user_workspaces
  ADD CONSTRAINT fk_user_workspaces_workspace
    FOREIGN KEY (workspace_id) REFERENCES workspaces(workspace_id) ON DELETE CASCADE;

ALTER TABLE user_workspaces DROP CONSTRAINT IF EXISTS fk_user_workspaces_user;
ALTER TABLE user_workspaces
  ADD CONSTRAINT fk_user_workspaces_user
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE;

-- Group workspaces FK
ALTER TABLE group_workspaces DROP CONSTRAINT IF EXISTS fk_group_workspaces_group;
ALTER TABLE group_workspaces
  ADD CONSTRAINT fk_group_workspaces_group
    FOREIGN KEY (group_id) REFERENCES groups(group_id) ON DELETE CASCADE;

-- Group workspaces FK (to workspaces table)
ALTER TABLE group_workspaces DROP CONSTRAINT IF EXISTS fk_group_workspaces_workspace;
ALTER TABLE group_workspaces
  ADD CONSTRAINT fk_group_workspaces_workspace
    FOREIGN KEY (workspace_id) REFERENCES workspaces(workspace_id) ON DELETE CASCADE;

-- Thread workspaces FK
ALTER TABLE thread_workspaces DROP CONSTRAINT IF EXISTS fk_thread_workspaces_workspace;
ALTER TABLE thread_workspaces
  ADD CONSTRAINT fk_thread_workspaces_workspace
    FOREIGN KEY (workspace_id) REFERENCES workspaces(workspace_id) ON DELETE CASCADE;

-- Workspace members FK
ALTER TABLE workspace_members DROP CONSTRAINT IF EXISTS fk_workspace_members_workspace;
ALTER TABLE workspace_members DROP CONSTRAINT IF EXISTS fk_workspace_members_user;
ALTER TABLE workspace_members DROP CONSTRAINT IF EXISTS fk_workspace_members_granted_by;
ALTER TABLE workspace_members
  ADD CONSTRAINT fk_workspace_members_workspace
    FOREIGN KEY (workspace_id) REFERENCES workspaces(workspace_id) ON DELETE CASCADE;

ALTER TABLE workspace_members
  ADD CONSTRAINT fk_workspace_members_user
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE;

ALTER TABLE workspace_members
  ADD CONSTRAINT fk_workspace_members_granted_by
    FOREIGN KEY (granted_by) REFERENCES users(user_id) ON DELETE SET NULL;

-- User aliases FK
ALTER TABLE user_aliases DROP CONSTRAINT IF EXISTS fk_user_aliases_user;
ALTER TABLE user_aliases
  ADD CONSTRAINT fk_user_aliases_user
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE;

-- Workspace ACL FK
ALTER TABLE workspace_acl DROP CONSTRAINT IF EXISTS fk_workspace_acl_workspace;
ALTER TABLE workspace_acl DROP CONSTRAINT IF EXISTS fk_workspace_acl_target_user;
ALTER TABLE workspace_acl DROP CONSTRAINT IF EXISTS fk_workspace_acl_target_group;
ALTER TABLE workspace_acl
  ADD CONSTRAINT fk_workspace_acl_workspace
    FOREIGN KEY (workspace_id) REFERENCES workspaces(workspace_id) ON DELETE CASCADE;

ALTER TABLE workspace_acl
  ADD CONSTRAINT fk_workspace_acl_target_user
    FOREIGN KEY (target_user_id) REFERENCES users(user_id) ON DELETE CASCADE;

ALTER TABLE workspace_acl
  ADD CONSTRAINT fk_workspace_acl_target_group
    FOREIGN KEY (target_group_id) REFERENCES groups(group_id) ON DELETE CASCADE;

-- ============================================================================
-- Conversations table (metadata)
-- ============================================================================

CREATE TABLE IF NOT EXISTS conversations (
    conversation_id VARCHAR(255) PRIMARY KEY,
    user_id VARCHAR(255),
    channel VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    message_count INT DEFAULT 0,
    -- Structured summary (replaces legacy TEXT summary)
    structured_summary JSONB,
    active_request TEXT,
    status VARCHAR(20) DEFAULT 'active'  -- active, removed, archived
);

CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_channel ON conversations(channel);
CREATE INDEX IF NOT EXISTS idx_conversations_structured_summary ON conversations USING GIN (structured_summary);
CREATE INDEX IF NOT EXISTS idx_conversations_active_request ON conversations (active_request);

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

CREATE INDEX IF NOT EXISTS idx_reminders_due_time ON reminders(due_time) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_reminders_user_id ON reminders(user_id);
CREATE INDEX IF NOT EXISTS idx_reminders_status ON reminders(status);

-- ============================================================================
-- Workers table for Orchestrator-spawned worker agents
-- ============================================================================

CREATE TABLE IF NOT EXISTS workers (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    thread_id VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    tools TEXT[] NOT NULL,              -- Array of tool names assigned to this worker
    prompt TEXT NOT NULL,               -- System prompt for the worker
    status VARCHAR(20) DEFAULT 'active', -- active, archived, deleted
    created_at TIMESTAMP DEFAULT NOW(),
    archived_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_workers_user_id ON workers(user_id);
CREATE INDEX IF NOT EXISTS idx_workers_thread_id ON workers(thread_id);
CREATE INDEX IF NOT EXISTS idx_workers_status ON workers(status);

-- ============================================================================
-- Scheduled jobs table for Orchestrator-scheduled worker execution
-- ============================================================================

CREATE TABLE IF NOT EXISTS scheduled_jobs (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    thread_id VARCHAR(255) NOT NULL,
    worker_id INTEGER REFERENCES workers(id) ON DELETE SET NULL,
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
    result TEXT                          -- Output from worker execution
);

CREATE INDEX IF NOT EXISTS idx_scheduled_jobs_due_time ON scheduled_jobs(due_time) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_scheduled_jobs_user_id ON scheduled_jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_scheduled_jobs_thread_id ON scheduled_jobs(thread_id);
CREATE INDEX IF NOT EXISTS idx_scheduled_jobs_worker_id ON scheduled_jobs(worker_id);
CREATE INDEX IF NOT EXISTS idx_scheduled_jobs_status ON scheduled_jobs(status);

-- ============================================================================
-- File paths ownership tracking
-- ============================================================================

CREATE TABLE IF NOT EXISTS file_paths (
    thread_id VARCHAR(255) PRIMARY KEY,  -- Sanitized thread_id used as directory name
    user_id VARCHAR(255),  -- NULL until merge, then set to merged user_id
    channel VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_file_paths_user ON file_paths(user_id);

-- ============================================================================
-- Database ownership tracking
-- ============================================================================

CREATE TABLE IF NOT EXISTS db_paths (
    thread_id VARCHAR(255) PRIMARY KEY,  -- Thread identifier
    db_path VARCHAR(512) NOT NULL,  -- Path to the database file
    user_id VARCHAR(255),  -- NULL until merge, then set to merged user_id
    channel VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_db_paths_user ON db_paths(user_id);
CREATE INDEX IF NOT EXISTS idx_db_paths_thread ON db_paths(thread_id);

-- ============================================================================
-- User registry operations tracking (merge, split, remove)
-- ============================================================================

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

CREATE INDEX IF NOT EXISTS idx_user_registry_target_user ON user_registry(target_user_id);
CREATE INDEX IF NOT EXISTS idx_user_registry_thread_ids ON user_registry USING GIN(source_thread_ids);
CREATE INDEX IF NOT EXISTS idx_user_registry_created_at ON user_registry(created_at DESC);

-- ============================================================================
-- Comments for documentation
-- ============================================================================

COMMENT ON TABLE conversations IS 'Conversation metadata for audit and analytics';
COMMENT ON TABLE messages IS 'Message log for audit, compliance, and record keeping';
COMMENT ON TABLE file_paths IS 'File path ownership tracking for merge/remove operations';
COMMENT ON TABLE db_paths IS 'Database ownership tracking for merge/remove operations';
COMMENT ON TABLE user_registry IS 'Tracks merge/split/remove operations for audit and recovery';
COMMENT ON COLUMN user_registry.operation_type IS 'Type: merge (threads→user), split (user→threads), remove (delete)';
COMMENT ON COLUMN user_registry.source_thread_ids IS 'Thread IDs affected by this operation';
COMMENT ON COLUMN user_registry.target_user_id IS 'Target user ID for merge, or source user for split';

COMMENT ON TABLE reminders IS 'Scheduled reminders for users with optional recurrence';
COMMENT ON COLUMN reminders.thread_ids IS 'Which conversation threads to notify when reminder fires';
COMMENT ON COLUMN reminders.recurrence IS 'NULL for one-time, or pattern like "daily at 9am", "weekly"';

COMMENT ON TABLE workers IS 'Worker agents spawned by Orchestrator for specific tasks';
COMMENT ON COLUMN workers.tools IS 'Array of tool names (e.g., ["web_search", "execute_python"])';
COMMENT ON COLUMN workers.prompt IS 'System prompt that defines the worker''s behavior';
COMMENT ON COLUMN workers.status IS 'active = in use, archived = no longer needed, deleted = removed';

COMMENT ON TABLE scheduled_jobs IS 'Scheduled jobs that execute worker agents at specific times';
COMMENT ON COLUMN scheduled_jobs.worker_id IS 'Reference to the worker that executes this job';
COMMENT ON COLUMN scheduled_jobs.task IS 'Concrete task description (e.g., "Check Amazon price for B08X12345")';
COMMENT ON COLUMN scheduled_jobs.flow IS 'Execution flow (e.g., "fetch price → if < $100 notify, else log")';
COMMENT ON COLUMN scheduled_jobs.cron IS 'NULL for one-off, or cron expression for recurring jobs';
COMMENT ON COLUMN scheduled_jobs.result IS 'Output text from worker execution';

COMMENT ON COLUMN conversations.structured_summary IS 'Structured summary with topics, facts, decisions, tasks, open questions - JSONB format';
COMMENT ON COLUMN conversations.active_request IS 'Latest user request (intent-first) - always shows current dominant intent';

-- ============================================================================
-- Test Data Setup (for development and testing)
-- ============================================================================

-- Insert test users
INSERT INTO users (user_id) VALUES
  ('test:user123'),
  ('test:sandbox_user'),
  ('user1'),
  ('user2'),
  ('telegram:user123'),
  ('http:user123')
ON CONFLICT (user_id) DO NOTHING;

-- Insert test workspaces
INSERT INTO workspaces (workspace_id, type, name, owner_user_id) VALUES
  ('ws:test_workspace', 'individual', 'Test Workspace', 'test:user123'),
  ('ws:test_kb', 'individual', 'Test KB Workspace', 'test:user123'),
  ('ws:test_files', 'individual', 'Test Files Workspace', 'test:user123'),
  ('ws:integration', 'individual', 'Integration Test Workspace', 'test:user123'),
  ('ws:edge_cases', 'individual', 'Edge Cases Test Workspace', 'test:user123'),
  ('ws:test_sandbox', 'individual', 'Test Sandbox Workspace', 'test:sandbox_user'),
  ('ws:workspace_1', 'individual', 'Workspace 1', 'user1'),
  ('ws:workspace_2', 'individual', 'Workspace 2', 'user2')
ON CONFLICT (workspace_id) DO NOTHING;

-- Grant workspace members (for permission checks)
-- The owner_user_id should have admin permission automatically,
-- but we add explicit records for the permission system
INSERT INTO workspace_members (workspace_id, user_id, role) VALUES
  ('ws:test_workspace', 'test:user123', 'admin'),
  ('ws:test_kb', 'test:user123', 'admin'),
  ('ws:test_files', 'test:user123', 'admin'),
  ('ws:integration', 'test:user123', 'admin'),
  ('ws:edge_cases', 'test:user123', 'admin'),
  ('ws:test_sandbox', 'test:sandbox_user', 'admin'),
  ('ws:workspace_1', 'user1', 'admin'),
  ('ws:workspace_2', 'user2', 'admin')
ON CONFLICT (workspace_id, user_id) DO NOTHING;

-- Create user_workspaces entries
INSERT INTO user_workspaces (user_id, workspace_id) VALUES
  ('test:user123', 'ws:test_workspace'),
  ('test:user123', 'ws:test_kb'),
  ('test:user123', 'ws:test_files'),
  ('test:user123', 'ws:integration'),
  ('test:user123', 'ws:edge_cases'),
  ('test:sandbox_user', 'ws:test_sandbox'),
  ('user1', 'ws:workspace_1'),
  ('user2', 'ws:workspace_2')
ON CONFLICT (user_id) DO NOTHING;


-- ================================================
-- Source: 002_workspace_to_group_rename.sql
-- ================================================
-- ============================================================================
-- Migration 002: Rename workspace → group terminology
-- Date: 2026-01-18
-- ============================================================================
-- This migration completes the workspace→group refactoring by renaming
-- all database objects from "workspace" to "group" terminology.
--
-- Changes:
-- 1. Rename table: workspaces → groups
-- 2. Rename columns: workspace_id → group_id
-- 3. Rename tables: workspace_members → group_members, workspace_acl → group_acl
-- 4. Rename indexes and constraints
-- ============================================================================

BEGIN;

-- ----------------------------------------------------------------------------
-- Step 0: Drop foreign key constraints that reference the tables being renamed
-- ----------------------------------------------------------------------------

-- Drop FK from workspaces.owner_group_id → groups.group_id (before renaming groups)
ALTER TABLE workspaces DROP CONSTRAINT IF EXISTS fk_workspaces_owner_group;

-- Drop FK from workspace_acl.target_group_id → groups.group_id (before renaming groups)
ALTER TABLE workspace_acl DROP CONSTRAINT IF EXISTS fk_workspace_acl_target_group;

-- Drop FK from group_workspaces.group_id → groups.group_id (before renaming groups)
ALTER TABLE group_workspaces DROP CONSTRAINT IF EXISTS fk_group_workspaces_group;

-- ----------------------------------------------------------------------------
-- Step 1: Rename the main workspaces table to groups
-- ----------------------------------------------------------------------------

-- The existing "groups" table is for team groups (different concept)
-- We need to rename it first to avoid conflicts
ALTER TABLE groups RENAME TO team_groups;
ALTER TABLE group_members RENAME TO team_group_members;

-- Drop and recreate indexes that reference the old table
DROP INDEX IF EXISTS idx_groups_name;
DROP INDEX IF EXISTS idx_group_members_user;

-- Now rename workspaces to groups
ALTER TABLE workspaces RENAME TO groups;

-- ----------------------------------------------------------------------------
-- Step 2: Rename all workspace_id columns to group_id
-- ----------------------------------------------------------------------------

-- groups table (formerly workspaces) - rename the PK column
ALTER TABLE groups RENAME COLUMN workspace_id TO group_id;

-- user_workspaces table (will be renamed to user_groups)
ALTER TABLE user_workspaces RENAME COLUMN workspace_id TO group_id;

-- group_workspaces table (maps team_groups to storage groups)
-- We rename workspace_id to storage_group_id to avoid conflict with group_id (team_group)
ALTER TABLE group_workspaces RENAME COLUMN workspace_id TO storage_group_id;

-- thread_workspaces table (maps threads to groups)
ALTER TABLE thread_workspaces RENAME COLUMN workspace_id TO group_id;

-- workspace_members table (will be renamed to group_members)
ALTER TABLE workspace_members RENAME COLUMN workspace_id TO group_id;

-- workspace_acl table (will be renamed to group_acl)
ALTER TABLE workspace_acl RENAME COLUMN workspace_id TO group_id;

-- ----------------------------------------------------------------------------
-- Step 3: Rename tables to use group terminology
-- ----------------------------------------------------------------------------

ALTER TABLE workspace_members RENAME TO group_members;
ALTER TABLE workspace_acl RENAME TO group_acl;

-- Note: user_workspaces keeps its name (it's a mapping table)
-- Note: group_workspaces keeps its name (it's a mapping table from team_groups to groups)
-- Note: thread_workspaces will be renamed to thread_groups
ALTER TABLE thread_workspaces RENAME TO thread_groups;

-- ----------------------------------------------------------------------------
-- Step 4: Rename indexes to use group terminology
-- ----------------------------------------------------------------------------

-- Drop old workspace-related indexes
DROP INDEX IF EXISTS idx_workspaces_type;
DROP INDEX IF EXISTS idx_workspaces_owner_user;
DROP INDEX IF EXISTS idx_workspaces_owner_group;
DROP INDEX IF EXISTS idx_thread_workspaces_workspace;
DROP INDEX IF EXISTS idx_workspace_members_user;
DROP INDEX IF EXISTS idx_workspace_members_role;
DROP INDEX IF EXISTS idx_workspace_acl_workspace;
DROP INDEX IF EXISTS idx_workspace_acl_target_user;
DROP INDEX IF EXISTS idx_workspace_acl_target_group;
DROP INDEX IF EXISTS idx_workspace_acl_expires;

-- Create new group-related indexes
CREATE INDEX IF NOT EXISTS idx_groups_type ON groups(type);
CREATE INDEX IF NOT EXISTS idx_groups_owner_user ON groups(owner_user_id);
CREATE INDEX IF NOT EXISTS idx_groups_owner_group ON groups(owner_group_id);
CREATE INDEX IF NOT EXISTS idx_thread_groups_group_id ON thread_groups(group_id);
CREATE INDEX IF NOT EXISTS idx_group_members_user ON group_members(user_id);
CREATE INDEX IF NOT EXISTS idx_group_members_role ON group_members(role);
CREATE INDEX IF NOT EXISTS idx_group_acl_group ON group_acl(group_id);
CREATE INDEX IF NOT EXISTS idx_group_acl_target_user ON group_acl(target_user_id);
CREATE INDEX IF NOT EXISTS idx_group_acl_target_group ON group_acl(target_group_id);
CREATE INDEX IF NOT EXISTS idx_group_acl_expires ON group_acl(expires_at) WHERE expires_at IS NOT NULL;

-- ----------------------------------------------------------------------------
-- Step 5: Rename foreign key constraints
-- ----------------------------------------------------------------------------

-- Drop old FK constraints
ALTER TABLE groups DROP CONSTRAINT IF EXISTS fk_workspaces_owner_user;
ALTER TABLE groups DROP CONSTRAINT IF EXISTS fk_workspaces_owner_group;
ALTER TABLE user_workspaces DROP CONSTRAINT IF EXISTS fk_user_workspaces_workspace;
ALTER TABLE group_workspaces DROP CONSTRAINT IF EXISTS fk_group_workspaces_workspace;
ALTER TABLE thread_groups DROP CONSTRAINT IF EXISTS fk_thread_workspaces_workspace;
ALTER TABLE group_members DROP CONSTRAINT IF EXISTS fk_workspace_members_workspace;
ALTER TABLE group_acl DROP CONSTRAINT IF EXISTS fk_workspace_acl_workspace;

-- Add new FK constraints with group terminology
ALTER TABLE groups
  ADD CONSTRAINT fk_groups_owner_user
    FOREIGN KEY (owner_user_id) REFERENCES users(user_id) ON DELETE CASCADE;

ALTER TABLE groups
  ADD CONSTRAINT fk_groups_owner_group
    FOREIGN KEY (owner_group_id) REFERENCES team_groups(group_id) ON DELETE CASCADE;

ALTER TABLE user_workspaces
  ADD CONSTRAINT fk_user_workspaces_group
    FOREIGN KEY (group_id) REFERENCES groups(group_id) ON DELETE CASCADE;

ALTER TABLE group_workspaces
  ADD CONSTRAINT fk_group_workspaces_storage_group
    FOREIGN KEY (storage_group_id) REFERENCES groups(group_id) ON DELETE CASCADE;

-- Add FK for team_group reference (group_id references team_groups)
ALTER TABLE group_workspaces
  ADD CONSTRAINT fk_group_workspaces_team_group
    FOREIGN KEY (group_id) REFERENCES team_groups(group_id) ON DELETE CASCADE;

ALTER TABLE thread_groups
  ADD CONSTRAINT fk_thread_groups_group
    FOREIGN KEY (group_id) REFERENCES groups(group_id) ON DELETE CASCADE;

ALTER TABLE group_members
  ADD CONSTRAINT fk_group_members_group
    FOREIGN KEY (group_id) REFERENCES groups(group_id) ON DELETE CASCADE;

ALTER TABLE group_acl
  ADD CONSTRAINT fk_group_acl_group
    FOREIGN KEY (group_id) REFERENCES groups(group_id) ON DELETE CASCADE;

-- ----------------------------------------------------------------------------
-- Step 6: Rename CHECK constraints
-- ----------------------------------------------------------------------------

ALTER TABLE groups DROP CONSTRAINT IF EXISTS valid_workspace_type;
ALTER TABLE groups
  ADD CONSTRAINT valid_group_type
    CHECK (type IN ('individual', 'group', 'public'));

-- ----------------------------------------------------------------------------
-- Step 7: Update team_groups indexes (they reference the old "groups" table)
-- ----------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_team_groups_name ON team_groups(name);
CREATE INDEX IF NOT EXISTS idx_team_group_members_user ON team_group_members(user_id);

-- ----------------------------------------------------------------------------
-- Step 8: Update comments
-- ----------------------------------------------------------------------------

COMMENT ON TABLE groups IS 'Groups (formerly workspaces) - storage contexts for users, teams, or public access';
COMMENT ON TABLE group_members IS 'Group membership with roles (admin, editor, reader)';
COMMENT ON TABLE group_acl IS 'Group-level ACL for fine-grained resource permissions';
COMMENT ON TABLE thread_groups IS 'Maps threads to their associated groups';
COMMENT ON TABLE user_workspaces IS 'Maps users to their personal individual group';
COMMENT ON TABLE group_workspaces IS 'Maps team_groups to storage groups (groups owned by teams)';
COMMENT ON TABLE team_groups IS 'Team groups (collections of users for collaboration)';
COMMENT ON TABLE team_group_members IS 'Team group membership';

COMMIT;

-- ============================================================================
-- Verification Queries (run these after migration to verify)
-- ============================================================================

-- \d groups
-- \d group_members
-- \d group_acl
-- \d thread_groups
-- \d user_workspaces
-- \d team_groups
-- \d team_group_members


-- ================================================
-- Source: 003_add_identities_table.sql
-- ================================================
-- ============================================================================
-- Identities Table for Cross-Channel Identity Unification
-- Version: 2025-01-20
-- ============================================================================
-- Purpose: Track user identities across channels, support anonymous→verified flow
-- ============================================================================

-- ============================================================================
-- Identities table
-- ============================================================================

CREATE TABLE IF NOT EXISTS identities (
    identity_id TEXT PRIMARY KEY,          -- "anon_telegram_123456" or "user_abc123"
    persistent_user_id TEXT,               -- NULL for anon, 'user_*' after merge
    channel TEXT,                          -- 'telegram', 'email', 'http'
    thread_id TEXT NOT NULL UNIQUE,        -- Thread this identity belongs to
    created_at TIMESTAMP DEFAULT NOW(),
    merged_at TIMESTAMP,                   -- NULL until merged
    verification_status TEXT DEFAULT 'anonymous',  -- 'anonymous', 'pending', 'verified'
    verification_method TEXT,              -- 'email', 'phone', 'oauth'
    verification_contact TEXT              -- Email/phone for verification
);

-- ============================================================================
-- Indexes for common queries
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_identities_persistent_user ON identities(persistent_user_id) WHERE persistent_user_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_identities_channel ON identities(channel);
CREATE INDEX IF NOT EXISTS idx_identities_verification ON identities(verification_status);
CREATE INDEX IF NOT EXISTS idx_identities_contact ON identities(verification_contact) WHERE verification_contact IS NOT NULL;

-- ============================================================================
-- Comments for documentation
-- ============================================================================

COMMENT ON TABLE identities IS 'Track user identities across channels with anonymous→verified flow';
COMMENT ON COLUMN identities.identity_id IS 'Display ID (anon_* for anonymous, immutable after creation)';
COMMENT ON COLUMN identities.persistent_user_id IS 'Unified user ID (NULL for anon, set after merge)';
COMMENT ON COLUMN identities.thread_id IS 'Thread/conversation ID (unique per identity)';
COMMENT ON COLUMN identities.verification_status IS 'anonymous → pending → verified';
COMMENT ON COLUMN identities.verification_contact IS 'Email/phone used for verification (for pending/verified)';


-- ================================================
-- Source: 004_add_verification_codes.sql
-- ================================================
-- ============================================================================
-- Add Verification Code Support to Identities Table
-- Version: 2025-01-20
-- ============================================================================
-- Purpose: Store verification codes for identity merge flow
-- ============================================================================

-- Add verification code columns
ALTER TABLE identities
ADD COLUMN IF NOT EXISTS verification_code TEXT,
ADD COLUMN IF NOT EXISTS code_expires_at TIMESTAMP;

-- Add index for code lookups
CREATE INDEX IF NOT EXISTS idx_identities_verification_code
ON identities(verification_code, code_expires_at)
WHERE verification_code IS NOT NULL;

-- Add comments for documentation
COMMENT ON COLUMN identities.verification_code IS 'Verification code for merge (email/SMS)';
COMMENT ON COLUMN identities.code_expires_at IS 'Code expiration time (typically 15 minutes)';

