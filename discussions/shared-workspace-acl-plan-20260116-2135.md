# Shared Workspace + ACL Plan (Non‑bloat Variant)

## Verdict on Bloat
This does **not** have to be bloated if we keep the ACL model minimal and avoid per‑resource duplication. The trick is:
- **One shared workspace** (`workspace_id=shared`)
- **One ACL table** for all shareable resource types
- **No data copying** (mount shared resources virtually)

With this, the only extra overhead is a small ACL table and a simple lookup per tool call.

---

## Goals
- Introduce a **shared workspace** (not “company”).
- Admins can write to shared resources.
- Admins can selectively grant **read/write** access to users/groups for:
  - Files/folders
  - KB collections
  - DB tables
  - Reminders
  - Workflows
- Respect DuckDB’s **single writer** per DB file.

---

## Minimal Schema

### 1) Workspaces
```sql
CREATE TABLE workspaces (
  workspace_id TEXT PRIMARY KEY,
  owner_user_id TEXT NULL,  -- NULL for shared workspace
  created_at TIMESTAMP DEFAULT NOW()
);
```

### 2) Thread → Workspace mapping
```sql
CREATE TABLE thread_workspaces (
  thread_id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  workspace_id TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT NOW()
);
```

### 3) ACL (single table for all resource types)
```sql
CREATE TABLE workspace_acl (
  id SERIAL PRIMARY KEY,
  owner_workspace_id TEXT NOT NULL,   -- "shared" or user's workspace
  resource_type TEXT NOT NULL,        -- file_folder | kb_collection | db_table | reminder | workflow
  resource_id TEXT NOT NULL,          -- folder path or collection/table name or reminder/workflow id
  target_user_id TEXT NULL,
  target_group_id TEXT NULL,
  permission TEXT NOT NULL,           -- read | write
  created_at TIMESTAMP DEFAULT NOW(),
  expires_at TIMESTAMP NULL
);
```

### 4) Groups (optional, can defer)
```sql
CREATE TABLE groups (
  group_id TEXT PRIMARY KEY,
  name TEXT NOT NULL
);

CREATE TABLE group_members (
  group_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  PRIMARY KEY (group_id, user_id)
);
```

---

## Storage Layout
```
data/workspaces/
  shared/
    files/
    kb/
    db/
    reminders/
    workflows/
  {workspace_id}/
    files/
    kb/
    db/
    reminders/
    workflows/
```

---

## Access Rules (Routing)

### Resolution order per tool call
1. **Own workspace** (always allowed)
2. **Shared workspace** (read by default)
3. **Explicit ACL shares** (user/group grants)

### Files
- Share by folder path (e.g. `reports/2026/`)
- Target sees a virtual mount:
  - `Shared/{owner}/reports/2026/...`
- Write permitted only if ACL has `permission=write`.

### KB
- Share by collection name.
- Search should include:
  - own collections
  - shared collections (read)
  - ACL‑granted collections
- Writes require ACL `write`.

### DB
- Share by table name in `shared/db.db` or other workspaces.
- Enforce **single writer** queue per DB file (shared or user DB).
- Writes require ACL `write`, reads require ACL `read`.

### Reminders + Workflows
- Treated as resources with ACL.
- Shared workspace reminders/workflows can be visible to all, but:
  - Execution/editing requires ACL `write`.

---

## Admin Model
Admins are allowed to:
- Write to shared workspace by default.
- Create ACL entries that grant read/write to users/groups.

Non‑admins:
- Read from shared workspace only if ACL allows.
- Write only if ACL allows.

---

## Minimum Viable Implementation (Non‑bloat)
1. Create `workspaces` + `thread_workspaces` + `workspace_acl`.
2. Create `shared` workspace row.
3. Add ACL checks in tool routing for:
   - file list/read/write
   - kb list/search/add/delete
   - db query/insert/update/delete
   - reminder/workflow list/create/delete
4. Introduce a **shared workspace view** in UI (read‑only unless ACL write).

---

## What We Might Be Missing
- **Audit log** for share actions and shared writes.
- **Revocation**: removing ACL should immediately hide resources.
- **Expiry** for temporary shares.

---

## Why This Isn’t Bloated
- One ACL table, no special case per resource.
- No data copying or sync.
- Shared workspace is just another workspace.
- Permissions are enforced at tool boundary only.

---

## Peer Review (Structural) - 2025-01-17

### Executive Summary

The plan is **rightly focused** on being "non-bloat" with an elegant single-ACL design. However, several **structural foundations** need clarification before implementation:

| Issue | Severity | Type |
|-------|----------|------|
| thread_workspaces cardinality | **HIGH** | Schema design ambiguity |
| Missing FOREIGN KEYs | **HIGH** | Referential integrity |
| resource_id instability | **HIGH** | Data lifecycle |
| Storage layout migration | **HIGH** | Breaking change unclear |
| Missing workspace lookup step | **MEDIUM** | Incomplete access flow |
| Virtual mount unspecified | **MEDIUM** | Tool integration undefined |
| Write queue missing | **MEDIUM** | Incomplete spec |
| Admin model undefined | **MEDIUM** | Missing schema |
| Duplicate ACLs possible | **LOW** | Missing constraint |

---

### Issue 1: thread_workspaces Cardinality Ambiguity (HIGH)

**Current schema:**
```sql
CREATE TABLE thread_workspaces (
  thread_id TEXT PRIMARY KEY,  -- ← Problem: each thread → exactly ONE workspace
  user_id TEXT NOT NULL,
  workspace_id TEXT NOT NULL,
  ...
);
```

**Problem:** With `thread_id` as PRIMARY KEY, each thread can map to **exactly one** workspace. But this conflicts with likely use cases:

| Scenario | Question | Current Schema Answer |
|----------|----------|----------------------|
| User has 3 threads (web + telegram + merged) | Do they share a workspace? | **No** - each gets a separate workspace |
| Want to merge threads into one workspace | Can multiple threads share workspace? | **No** - PK prevents it |
| Want to move thread to different workspace | Can we update workspace_id? | **Yes** - but no migration guidance |

**Clarification needed:** What's the intended relationship?

- **Option A) One workspace per thread** - User with 3 threads has 3 isolated workspaces
- **Option B) One workspace per user** - All user's threads share one workspace
- **Option C) Many-to-many** - Threads can belong to multiple workspaces

**Recommended fix (for Option B - likely intended):**
```sql
-- Remove thread_workspaces, map users directly to workspaces
CREATE TABLE user_workspaces (
  user_id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL UNIQUE,
  created_at TIMESTAMP DEFAULT NOW()
);

-- Threads derive workspace from their owner user_id:
-- SELECT workspace_id FROM user_workspaces WHERE user_id = (SELECT user_id FROM conversations WHERE conversation_id = $1)
```

**OR (for Option C - most flexible):**
```sql
-- Allow many-to-many: one thread can be in multiple workspaces
CREATE TABLE thread_workspaces (
  thread_id TEXT NOT NULL,
  workspace_id TEXT NOT NULL,
  is_primary BOOLEAN DEFAULT TRUE,  -- Mark one as "home"
  created_at TIMESTAMP DEFAULT NOW(),
  PRIMARY KEY (thread_id, workspace_id)
);
```

---

### Issue 2: Missing FOREIGN KEY Constraints (HIGH)

**Current schema:**
```sql
CREATE TABLE workspace_acl (
  owner_workspace_id TEXT NOT NULL,   -- No FK constraint
  target_user_id TEXT NULL,           -- No FK constraint
  target_group_id TEXT NULL,          -- No FK constraint
  ...
);
```

**Problems:**
1. ACL entries can reference non-existent workspaces (orphaned ACLs)
2. ACL entries can reference non-existent users
3. ACL entries can reference non-existent groups
4. No CASCADE delete - if workspace is deleted, ACLs linger
5. Can set both `target_user_id` AND `target_group_id` (data inconsistency)
6. Can set NEITHER (who is this ACL for?)

**Recommended fix:**
```sql
CREATE TABLE workspace_acl (
  id SERIAL PRIMARY KEY,
  owner_workspace_id TEXT NOT NULL,
  resource_type TEXT NOT NULL,
  resource_id TEXT NOT NULL,
  target_user_id TEXT NULL,
  target_group_id TEXT NULL,
  permission TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT NOW(),
  expires_at TIMESTAMP NULL,

  -- Foreign keys for referential integrity
  CONSTRAINT fk_workspace
    FOREIGN KEY (owner_workspace_id)
    REFERENCES workspaces(workspace_id)
    ON DELETE CASCADE,

  CONSTRAINT fk_user
    FOREIGN KEY (target_user_id)
    REFERENCES conversations(user_id)
    ON DELETE CASCADE,

  CONSTRAINT fk_group
    FOREIGN KEY (target_group_id)
    REFERENCES groups(group_id)
    ON DELETE CASCADE,

  -- Ensure exactly one target is set (XOR constraint)
  CONSTRAINT has_exactly_one_target CHECK (
    (target_user_id IS NOT NULL AND target_group_id IS NULL) OR
    (target_user_id IS NULL AND target_group_id IS NOT NULL)
  )
);
```

---

### Issue 3: resource_id Instability (HIGH)

**Current design:**
```sql
resource_id TEXT NOT NULL,  -- folder path or collection/table name
```

**Problem:** `resource_id` uses **mutable identifiers** that break when resources change:

| Resource Type | Current resource_id | Breaks When |
|---------------|---------------------|-------------|
| file_folder | `reports/2026/` | Folder renamed to `archives/2026/` |
| file_folder | `data/project1/` | File moved to `data/finished/project1/` |
| kb_collection | `research_notes` | Collection renamed to `research_notes_v2` |
| db_table | `analytics` | Table renamed to `analytics_2024` |

**Result:** ACL entries become invalid on any rename/move operation. Admin must manually update all ACLs.

**Comparison with previous sharing-plan:** That plan used stable UUIDs:
```python
FILE_REF_PATTERN = "file:{owner_user_id}:{file_uuid}"  # UUID never changes
KB_REF_PATTERN = "kb:{owner_user_id}:{table_name}"     # But table name CAN change
```

**Recommended fix:**
```sql
CREATE TABLE workspace_acl (
  id SERIAL PRIMARY KEY,
  owner_workspace_id TEXT NOT NULL,
  resource_type TEXT NOT NULL,

  -- Stable identifier that never changes
  resource_uuid TEXT NOT NULL,

  -- Human-readable display name (can be updated on rename)
  resource_id TEXT NOT NULL,

  target_user_id TEXT NULL,
  target_group_id TEXT NULL,
  permission TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT NOW(),
  expires_at TIMESTAMP NULL
);

-- Unique constraint on stable ID
CREATE UNIQUE INDEX idx_acl_resource ON workspace_acl (
  owner_workspace_id, resource_type, resource_uuid, target_user_id
);

-- When resource is renamed, UPDATE resource_id but keep resource_uuid
-- Example: UPDATE workspace_acl SET resource_id = 'archives/2026/' WHERE resource_uuid = '...';
```

**Implementation notes:**
- For files: Generate UUID when folder is first shared
- For KB/DB: Use existing collection/table name as UUID (assume names are stable) OR add UUID column to those resources
- Tools must maintain UUID → current path mapping

---

### Issue 4: Storage Layout Migration Gap (HIGH)

**Plan proposes:**
```
data/workspaces/
  shared/
    files/
    kb/
    db/
  {workspace_id}/
    files/
    kb/
    db/
```

**Current layout:**
```
data/users/{thread_id}/
  files/
  db/
  kb/
  mem/
```

**Critical missing pieces:**

1. **Do we move existing data?**
   - If YES: Breaking change, need migration script, all existing user data moves
   - If NO: How do we handle legacy `data/users/` paths?

2. **Or do we mount virtually?**
   - If virtual: `FileSandbox` has no workspace awareness - major refactor
   - How does `list_files("reports/")` know to include `Shared/Alice/reports/`?

3. **What happens during transition?**
   - Are both layouts supported temporarily?
   - Or is this a flag-day migration?

**Clarification needed:**
- Is `data/workspaces/` the **new primary** storage location?
- Or is `data/users/` still primary, with workspaces being **virtual views**?

**Recommended approach (if virtual mounting):**
Keep `data/users/{thread_id}/` as primary storage. Add workspace mapping:

```python
# src/executive_assistant/storage/workspace_registry.py
class WorkspaceRegistry:
    """Maps workspaces to underlying thread/user data."""

    def resolve_workspace_path(self, workspace_id: str, resource_type: str) -> Path:
        """Resolve workspace virtual path to actual storage path."""
        if workspace_id == "shared":
            return settings.SHARED_DB_PATH.parent / resource_type
        else:
            # User workspace: find the user who owns this workspace
            user_id = self.get_workspace_owner(workspace_id)
            return settings.USERS_ROOT / user_id / resource_type
```

**Recommended approach (if physical migration):**
Add migration step to plan:
```sql
-- Migration script
INSERT INTO workspaces (workspace_id, owner_user_id)
SELECT DISTINCT 'workspace_' || user_id, user_id
FROM user_registry;

-- For each user, move their data
-- mv data/users/{user_id}/* data/workspaces/workspace_{user_id}/
```

---

### Issue 5: Access Rules Skip Critical Lookup Step (MEDIUM)

**Plan states:**
> Resolution order per tool call:
> 1. Own workspace (always allowed)
> 2. Shared workspace (read by default)
> 3. Explicit ACL shares (user/group grants)

**Missing:** How do we determine which workspace is "own"?

The lookup **should** be:
```python
def resolve_workspace_access(thread_id: str, user_id: str) -> list[str]:
    """
    Step 1: Query thread_workspaces to find workspace_id for this thread_id
    Step 2: Check if user_id is admin (for shared workspace write)
    Step 3: Query workspace_acl for any grants to this user_id or their groups
    Step 4: Return list of accessible workspace_ids
    """
    # Get primary workspace for this thread
    workspace = await db.fetchval(
        "SELECT workspace_id FROM thread_workspaces WHERE thread_id = $1",
        thread_id
    )

    # Get ACL-granted workspaces
    acl_workspaces = await db.fetch(
        """SELECT DISTINCT owner_workspace_id
           FROM workspace_acl
           WHERE target_user_id = $1 OR target_group_id IN (SELECT group_id FROM group_members WHERE user_id = $1)
           AND (expires_at IS NULL OR expires_at > NOW())""",
        user_id
    )

    return [workspace] + [w["owner_workspace_id"] for w in acl_workspaces]
```

**The plan doesn't specify:**
- Where does this lookup happen?
- Is it cached (per-request, per-session)?
- What if a thread has no workspace entry in `thread_workspaces`?

**Recommended:** Add explicit "Workspace Resolution" section to plan with pseudocode.

---

### Issue 6: Virtual Mount Path Not Specified (MEDIUM)

**Plan states:**
> Target sees a virtual mount: `Shared/{owner}/reports/2026/...`

**Unspecified details:**

1. **Where does this virtual path exist?**
   - Is it merged into `list_files()` output?
   - Or is it a separate namespace like `shared://...`?

2. **What if two users share folders with the same name?**
   - Alice shares `reports/`
   - Bob shares `reports/`
   - Does target see `Shared/Alice/reports/` and `Shared/Bob/reports/`?
   - Or do they conflict?

3. **How does path resolution work?**
   ```python
   # When user calls read_file("Shared/Alice/reports/file.txt"):
   # 1. Parse "Shared/Alice/reports/file.txt" → owner="Alice", path="reports/file.txt"
   # 2. Find Alice's workspace_id
   # 3. Find ACL entry granting read to current user
   # 4. Resolve actual storage path (data/workspaces/workspace_alice/files/reports/file.txt)
   # 5. Read file
   ```

4. **Tool changes required:**
   - `list_files()` must query ACL and merge shared folders
   - `read_file()` must detect `Shared/` prefix and route accordingly
   - `write_file()` must check ACL before writing to shared paths
   - All file tools need workspace awareness

**Recommended:** Add "Virtual Mount Implementation" section with:
- Path parsing algorithm
- Tool modification list
- Edge cases (name conflicts, nested shares, etc.)

---

### Issue 7: Write Queue Schema Missing (MEDIUM)

**Plan mentions:**
> Respect DuckDB's **single writer** per DB file.

> Enforce **single writer** queue per DB file

**But provides no schema for the queue.**

**Previous sharing-plan** had detailed queue schema:
```sql
CREATE TABLE shared_db_write_queue (
  job_id UUID PRIMARY KEY,
  share_id UUID NOT NULL,
  resource_ref TEXT NOT NULL,
  operation_type TEXT NOT NULL,
  payload JSONB NOT NULL,
  status TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  ...
);
```

**This plan needs:**
1. Queue table schema
2. Worker process design (background thread? separate service?)
3. Job status tracking
4. Error handling and retry logic
5. Tool integration (enqueue + status check)

**Recommended:**
- Either add write queue schema to this plan
- OR reference the previous sharing-plan's queue design
- OR clarify that write queue is "out of scope" for MVP

---

### Issue 8: Admin Model Undefined (MEDIUM)

**Plan states:**
> Admins are allowed to:
> - Write to shared workspace by default.
> - Create ACL entries that grant read/write to users/groups.

**Missing:** Where is admin status defined?

**Current schema has:**
- No `is_admin` column in `conversations` or `users`
- No `admins` table
- No `settings.ADMIN_USER_IDS` integration mentioned

**Options:**

**Option A: Use existing settings.ADMIN_USER_IDS**
```python
# In access check:
if settings.is_admin(user_id):
    return True  # Admin can do anything
```

**Option B: Add workspace role system**
```sql
CREATE TABLE workspace_members (
  workspace_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('owner', 'admin', 'member', 'viewer')),
  PRIMARY KEY (workspace_id, user_id),
  FOREIGN KEY (workspace_id) REFERENCES workspaces(workspace_id)
);

-- Shared workspace admins
INSERT INTO workspace_members (workspace_id, user_id, role)
VALUES ('shared', 'admin_user_id', 'admin');
```

**Option C: Add is_admin to conversations**
```sql
ALTER TABLE conversations ADD COLUMN is_admin BOOLEAN DEFAULT FALSE;
```

**Clarification needed:** Which approach?

---

### Issue 9: Duplicate ACLs Possible (LOW)

**Current schema allows:**
```sql
-- Can create multiple identical ACL entries:
INSERT INTO workspace_acl (owner_workspace_id, resource_type, resource_id, target_user_id, permission)
VALUES ('shared', 'file_folder', 'reports/', 'alice', 'read');

INSERT INTO workspace_acl (owner_workspace_id, resource_type, resource_id, target_user_id, permission)
VALUES ('shared', 'file_folder', 'reports/', 'alice', 'read');  -- Duplicate!
```

**Problems:**
- Wasted storage
- Revocation requires deleting duplicates
- Query ambiguity (which ACL entry applies?)

**Recommended fix:**
```sql
CREATE UNIQUE INDEX idx_acl_unique_user ON workspace_acl (
  owner_workspace_id, resource_type, resource_id, target_user_id
) WHERE target_group_id IS NULL;

CREATE UNIQUE INDEX idx_acl_unique_group ON workspace_acl (
  owner_workspace_id, resource_type, resource_id, target_group_id
) WHERE target_user_id IS NULL;
```

---

### Issue 10: Groups Referenced But Deferred (LOW)

**Plan states:**
> Groups (optional, can defer)

**But schema includes:**
```sql
target_group_id TEXT NULL,
```

**Problem:** ACL entries can reference groups before groups are implemented.

**Recommended:**
- Either remove `target_group_id` from initial schema (add in later migration)
- Or clarify that groups ARE implemented in MVP

**Suggested:**
```sql
-- Phase 1 (MVP): No groups
CREATE TABLE workspace_acl (
  ...
  target_user_id TEXT NOT NULL,  -- Required in MVP
  ...
);

-- Phase 2 (Groups): Add groups
-- ALTER TABLE workspace_acl ADD COLUMN target_group_id TEXT NULL;
-- ALTER TABLE workspace_acl ALTER COLUMN target_user_id DROP NOT NULL;
```

---

### Positive Notes

The plan has several **excellent design decisions**:

1. **Single ACL table** - Elegant, no per-resource duplication
2. **Virtual mounting** - Avoids data copying, keeps source of truth
3. **Workspace as first-class concept** - Clean mental model
4. **Non-bloat philosophy** - Right constraints for an MVP

The structural issues above are **fixable with clarification**. They don't indicate fundamental design flaws—just missing implementation details.

---

### Recommended Next Steps

1. **Clarify thread→workspace cardinality** - Document intended relationship (A, B, or C)

2. **Add complete schema with constraints** - FKs, unique indexes, CHECK constraints

3. **Choose storage approach** - Virtual mount vs. physical migration

4. **Define workspace resolution** - Add pseudocode for workspace lookup

5. **Specify virtual mount behavior** - Path format, tool changes, conflict resolution

6. **Add or defer write queue** - Include schema or mark as out-of-scope

7. **Define admin model** - Where is admin status stored?

8. **Update schema in plan** - Apply all fixes from this review

Once these are addressed, the plan will be ready for implementation.
