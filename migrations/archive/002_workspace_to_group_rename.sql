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
