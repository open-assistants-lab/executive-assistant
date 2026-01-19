# Plan: Remove "Personal Groups" Architecture

## Problem Statement

**Current Architecture (Confusing):**
```
Every user gets a "personal group" automatically:
- User alice → group_abc (type='individual')
- User bob → group_xyz (type='individual')

Files stored at: data/groups/group_abc/files/
This looks like a "group" but only alice can access it.
```

**Target Architecture (Clear):**
```
Two distinct scopes, no overlap:
- data/users/{user_id}/  → Individual data (only that user)
- data/groups/{group_id}/ → Team data (shared by multiple users)
```

**Why This Matters:**
1. **Clarity**: "Individual" groups are architecturally confusing
2. **Correctness**: Personal data should live under `/users/`, not `/groups/`
3. **Simplicity**: Remove unnecessary abstraction layer (user_workspaces → groups)

---

## Current Implementation Analysis

### How Personal Groups Work

**Creation Flow:**
1. User sends first message via Telegram/HTTP
2. `ensure_user()` creates user record
3. `ensure_user_group()` creates group with type='individual'
4. Entry in `user_workspaces`: user_id → group_id
5. `thread_groups` table maps thread_id → group_id

**Key Files:**
- `src/cassey/storage/group_storage.py:278-320` - `ensure_user_group()`
- `src/cassey/storage/group_storage.py:322-352` - `ensure_thread_group()`
- `src/cassey/channels/telegram.py:836-868` - File upload context setting
- `src/cassey/storage/file_sandbox.py:230-270` - Path resolution priority
- `src/cassey/storage/db_tools.py:41-44` - DB tools (BUG: uses thread_id, ignores group_id)
- `src/cassey/storage/db_storage.py:66-87` - DB path resolution logic

**Database Tables:**
```sql
-- Maps users to their "personal group"
user_workspaces (
  user_id TEXT PRIMARY KEY,
  group_id TEXT NOT NULL UNIQUE,
  created_at TIMESTAMP
)

-- Maps threads to groups (can be personal or team)
thread_groups (
  thread_id TEXT PRIMARY KEY,
  group_id TEXT NOT NULL,
  user_id TEXT,
  created_at
)

groups (
  group_id TEXT PRIMARY KEY,
  type TEXT,  -- 'individual', 'group', 'public'
  name TEXT,
  owner_user_id TEXT,  -- For individual groups
  ...
)
```

**Context Priority (file_sandbox.py:230-270):**
1. user_id (explicit) → `/data/users/{user_id}/`
2. group_id (context) → `/data/groups/{group_id}/`
3. thread_id (fallback) → `/data/users/{thread_id}/` (legacy)

**Problem:** Telegram channel sets `group_id` context for everyone (including individuals), so priority #2 is used.

---

## Critical Bug: Split Storage (Files vs DB)

**Discovery Date:** 2025-01-19

**Symptom:**
Individual users have their data split across TWO different directories:
```
data/groups/group_71db35b4-11f1-44f8-96d8-599e39a17f58/files/photo.jpg  ← Files
data/groups/telegram_6282871705/db/db.sqlite                          ← Database
```

**Root Cause:**
DB tools (`src/cassey/storage/db_tools.py`) are hardcoded to use `thread_id` path, ignoring the `group_id` context that file uploads use.

**Code Analysis:**
```python
# File uploads (telegram.py:855-859) - Uses group_id ✓
group_id = await ensure_thread_group(thread_id, user_id)
set_workspace_context(group_id)
group_dir = settings.get_group_files_path(group_id)  # → data/groups/group_71db35b4.../files/

# DB tools (db_tools.py:87-90) - Uses thread_id ✗
thread_id = _get_current_thread_id()
db = _get_db()
record_db_path(thread_id, settings.get_thread_db_path(thread_id))  # → data/groups/telegram_6282871705/db/
```

**Impact:**
1. **Data fragmentation**: User's files and DB are in different "group" directories
2. **Confusion**: Two different "groups" for the same user (UUID-based vs telegram_id-based)
3. **Broken assumptions**: Code expects single group per user, but creates two
4. **Migration complexity**: Future cleanup must merge these split directories

**Quick Fix Needed:**
Update DB tools to respect `group_id` context, just like file uploads do.

**Long-term Fix:**
Remove "personal groups" entirely, use `/data/users/{user_id}/` for individuals.

---

## Proposed Solution

### Design Principle

**Clear separation:**
- **Users/** = Individual ownership (1 person)
- **Groups/** = Collaborative ownership (2+ people)

**No more "individual groups"** - groups are ONLY for teams.

### New Architecture

#### Storage Paths

```
data/
├── users/
│   └── {user_id}/
│       ├── files/       # Personal files
│       ├── db/          # Personal databases
│       ├── mem/         # Personal memories
│       └── reminders/   # Personal reminders
└── groups/
    └── {group_id}/
        ├── files/       # Shared files
        ├── db/          # Shared databases
        ├── mem/         # Shared memories
        └── reminders/   # Shared reminders
```

#### Context Model

**Individual Mode (Telegram users):**
```python
# When alice sends Telegram message:
set_user_id("telegram:123456")  # Alice's user_id
# No group_id set
# Files → /data/users/telegram:123456/files/
# DBs   → /data/users/telegram:123456/db/
```

**Team Mode (HTTP web app, team chat):**
```python
# When team accesses shared workspace:
set_group_id("group_acme_marketing")  # Team's group_id
set_user_id("user:alice")             # Alice's user_id
# Files → /data/groups/group_acme_marketing/files/
# DBs   → /data/groups/group_acme_marketing/db/
```

#### Database Schema Changes

**Option 1: Remove user_workspaces entirely**
```sql
-- DROP TABLE user_workspaces;

-- Update thread_groups to allow NULL group_id
ALTER TABLE thread_groups
  ALTER COLUMN group_id DROP NOT NULL,
  ADD COLUMN user_id TEXT;

-- For individual threads, store user_id directly
-- For team threads, store group_id
CREATE UNIQUE INDEX idx_thread_groups_context
  ON thread_groups (COALESCE(group_id, user_id));
```

**Option 2: Repurpose user_workspaces**
```sql
-- Keep table but change semantics
-- Now stores user preferences/settings instead of group mapping
ALTER TABLE user_workspaces
  ADD COLUMN preferences JSONB,
  ADD COLUMN settings JSONB;

-- Remove group_id column
ALTER TABLE user_workspaces
  DROP COLUMN group_id;
```

**Recommendation:** Option 1 (simpler, clearer)

---

## Implementation Steps

### Phase 1: Update Path Resolution (Core Fix)

**File:** `src/cassey/storage/file_sandbox.py`

**Current logic (lines 230-270):**
```python
def get_sandbox(user_id: str | None = None):
    # 1. Explicit user_id → /data/users/{user_id}/
    # 2. Context group_id → /data/groups/{group_id}/
    # 3. Context thread_id → /data/users/{thread_id}/
```

**New logic:**
```python
def get_sandbox(user_id: str | None = None):
    # 1. Explicit user_id → /data/users/{user_id}/
    if user_id:
        return FileSandbox(root=settings.get_user_files_path(user_id))

    # 2. Context user_id → /data/users/{user_id}/
    user_id_val = get_user_id()
    if user_id_val:
        return FileSandbox(root=settings.get_user_files_path(user_id_val))

    # 3. Context group_id → /data/groups/{group_id}/ (ONLY for teams)
    group_id_val = get_workspace_id()
    if group_id_val:
        return FileSandbox(root=settings.get_group_files_path(group_id_val))

    # 4. Context thread_id → Check if thread has group
    thread_id_val = get_thread_id()
    if thread_id_val:
        # Check if thread belongs to a group
        group_id = await get_thread_group(thread_id_val)
        if group_id:
            return FileSandbox(root=settings.get_group_files_path(group_id))
        else:
            # Individual thread → use user_id from thread
            return FileSandbox(root=settings.get_thread_files_path(thread_id_val))
```

**Key change:** Check `user_id` context BEFORE `group_id` context.

---

### Phase 2: Update Telegram Channel

**File:** `src/cassey/channels/telegram.py`

**Current behavior (lines 836-868):**
```python
# Always creates personal group for threads
group_id = await ensure_thread_group(thread_id, str(update.effective_user.id))
set_workspace_context(group_id)
```

**New behavior:**
```python
# Set user_id context for individual access
set_user_id(str(update.effective_user.id))

# Only create/group map if this thread belongs to a team
# For individual Telegram users, skip group creation
```

**What this means:**
- Telegram files → `/data/users/telegram:6282871705/files/`
- No more "personal group" for Telegram users
- If user joins a team later, that team uses `/data/groups/team_xyz/`

---

### Phase 3: Update Group Storage

**File:** `src/cassey/storage/group_storage.py`

**Functions to modify:**

1. **Remove `ensure_user_group()`** (lines 278-320)
   - Delete or deprecate this function
   - No longer create personal groups

2. **Update `ensure_thread_group()`** (lines 322-352)
   ```python
   async def ensure_thread_group(thread_id: str, user_id: str) -> str | None:
       """Ensure thread belongs to a group. Returns group_id or None.

       For individual users (Telegram), returns None (no group).
       For team workspaces, creates or returns group_id.
       """
       # Check if thread already has a group
       existing = await conn.fetchval(
           "SELECT group_id FROM thread_groups WHERE thread_id = $1",
           thread_id
       )
       if existing:
           return existing

       # Don't auto-create groups for individual users
       # Groups should be explicitly created by team setup
       return None
   ```

3. **Add new function: `get_user_storage_id()`**
   ```python
   def get_user_storage_id(user_id: str) -> str:
       """Get storage ID for user (used for path resolution)."""
       return user_id  # Direct mapping, no group indirection
   ```

4. **Update path helpers:**
   ```python
   def get_user_files_path(user_id: str) -> Path:
       """Get user's files directory."""
       return settings.USERS_ROOT / sanitize_user_id(user_id) / "files"

   def get_user_db_path(user_id: str) -> Path:
       """Get user's database directory."""
       return settings.USERS_ROOT / sanitize_user_id(user_id) / "db"
   ```

---

### Phase 4: Update Database & Vector Store Routing

**File:** `src/cassey/storage/db_storage.py`

**Current logic (lines 60-85):**
```python
def _get_db_path(thread_id=None, workspace_id=None):
    if workspace_id is None:
        workspace_id = get_workspace_id()
    if workspace_id:
        return settings.get_workspace_db_path(workspace_id)
    # Fallback to thread_id
    return settings.get_thread_db_path(thread_id)
```

**New logic:**
```python
def _get_db_path(thread_id=None, workspace_id=None, user_id=None):
    # 1. Explicit workspace_id (team mode)
    if workspace_id:
        return settings.get_group_db_path(workspace_id)

    # 2. Explicit user_id (individual mode)
    if user_id:
        return settings.get_user_db_path(user_id)

    # 3. Context group_id (team mode)
    group_id_val = get_workspace_id()
    if group_id_val:
        return settings.get_group_db_path(group_id_val)

    # 4. Context user_id (individual mode)
    user_id_val = get_user_id()
    if user_id_val:
        return settings.get_user_db_path(user_id_val)

    # 5. Legacy thread_id fallback
    if thread_id:
        return settings.get_thread_db_path(thread_id)
```

**Apply same logic to:**
- `src/cassey/storage/lancedb_storage.py` (vector stores)
- `src/cassey/storage/memory_storage.py` (memories)
- `src/cassey/storage/reminder.py` (reminders)

**CRITICAL FIX: Update db_tools.py**
**File:** `src/cassey/storage/db_tools.py`

**Current bug (lines 41-44, 87-90):**
```python
def _get_db() -> SQLiteDatabase:
    """Get the current thread's SQLite database."""
    thread_id = _get_current_thread_id()  # ← Ignores group_id context!
    return get_sqlite_db(thread_id)

# In create_db_table():
thread_id = _get_current_thread_id()
db = _get_db()
record_db_path(thread_id, settings.get_thread_db_path(thread_id))  # ← Hardcoded thread_id path!
```

**Fix:**
```python
def _get_db() -> SQLiteDatabase:
    """Get the current context's SQLite database (group or user)."""
    # Use DBStorage which respects group_id context
    from cassey.storage.db_storage import get_db_storage
    return get_sqlite_db_from_storage(get_db_storage())

# In create_db_table():
db = _get_db()
# Get current context ID (group_id or thread_id fallback)
from cassey.storage.group_storage import get_workspace_id, get_thread_id
workspace_id = get_workspace_id()
thread_id = get_thread_id()
current_id = workspace_id if workspace_id else thread_id

# Record the correct path (respects group_id context)
from cassey.storage.db_storage import get_db_storage
storage = get_db_storage()
record_db_path(current_id, storage._get_db_path())
```

**Why this fixes split storage:**
- Before: DB tools always used `thread_id` → `data/groups/telegram_6282871705/db/`
- After: DB tools use `group_id` context (when set) → `data/groups/group_71db35b4.../db/`
- Result: Files and DB use the same group directory!

---

### Phase 5: Database Migration

**Migration File:** `migrations/005_remove_personal_groups.sql`

```sql
-- ===== STEP 1: Add user_id to thread_groups =====
ALTER TABLE thread_groups
  ADD COLUMN IF NOT EXISTS user_id TEXT;

-- Migrate existing individual thread data
UPDATE thread_groups tg
SET user_id = (
    SELECT uw.user_id
    FROM user_workspaces uw
    JOIN groups g ON g.group_id = tg.group_id
    WHERE g.type = 'individual'
      AND uw.user_id IS NOT NULL
)
WHERE tg.group_id IN (
    SELECT g.group_id FROM groups g WHERE g.type = 'individual'
);

-- ===== STEP 2: Make group_id nullable =====
ALTER TABLE thread_groups
  ALTER COLUMN group_id DROP NOT NULL;

-- Add constraint: either group_id OR user_id must be set
ALTER TABLE thread_groups
  ADD CONSTRAINT thread_groups_context_check
  CHECK (group_id IS NOT NULL OR user_id IS NOT NULL);

-- ===== STEP 3: Drop individual groups =====
DELETE FROM groups WHERE type = 'individual';

-- ===== STEP 4: Drop user_workspaces table =====
DROP TABLE IF EXISTS user_workspaces;

-- ===== STEP 5: Clean up groups table =====
ALTER TABLE groups
  DROP COLUMN IF EXISTS type,
  DROP COLUMN IF EXISTS owner_user_id;

-- Groups table now ONLY for team collaboration
```

**Rollback Migration:** `migrations/rollback/005_remove_personal_groups.sql`
```sql
-- Re-create user_workspaces
CREATE TABLE user_workspaces (
  user_id TEXT PRIMARY KEY,
  group_id TEXT NOT NULL UNIQUE,
  created_at TIMESTAMP DEFAULT NOW()
);

-- Re-add type column to groups
ALTER TABLE groups
  ADD COLUMN IF NOT EXISTS type TEXT NOT NULL DEFAULT 'group',
  ADD COLUMN IF NOT EXISTS owner_user_id TEXT;

-- Cannot easily restore individual groups after deletion
-- Data loss warning in documentation
```

---

### Phase 6: Update Settings & Path Helpers

**File:** `src/cassey/config/settings.py`

**Remove:**
```python
WORKSPACE_ROOT: Path = _yaml_field(...)  # Deprecated
```

**Keep:**
```python
GROUPS_ROOT: Path = _yaml_field("STORAGE_PATHS_GROUPS_ROOT", Path("./data/groups"))
USERS_ROOT: Path = _yaml_field("STORAGE_PATHS_USERS_ROOT", Path("./data/users"))
```

**Add new path helpers:**
```python
def get_user_files_path(user_id: str) -> Path:
    """Get user's files directory."""
    return USERS_ROOT / sanitize_user_id(user_id) / "files"

def get_user_db_path(user_id: str) -> Path:
    """Get user's database directory."""
    return USERS_ROOT / sanitize_user_id(user_id) / "db"

def get_user_mem_path(user_id: str) -> Path:
    """Get user's memory directory."""
    return USERS_ROOT / sanitize_user_id(user_id) / "mem"

def get_user_reminders_path(user_id: str) -> Path:
    """Get user's reminders directory."""
    return USERS_ROOT / sanitize_user_id(user_id) / "reminders"

# Group paths (updated names)
def get_group_files_path(group_id: str) -> Path:
    """Get group's files directory."""
    return GROUPS_ROOT / sanitize_group_id(group_id) / "files"

def get_group_db_path(group_id: str) -> Path:
    """Get group's database directory."""
    return GROUPS_ROOT / sanitize_group_id(group_id) / "db"

# ... similar for mem, reminders
```

---

### Phase 7: Backward Compatibility Strategy

**Problem:** Existing users have data in `/data/groups/group_{individual}/`

**Solution:** Migration script to move data

**File:** `scripts/migrate_personal_groups_to_users.py`

```python
"""
Migration script: Move personal group data to user directories.

Before: data/groups/group_abc123/files/ (alice's personal group)
After:  data/users/telegram:6282871705/files/ (alice's user dir)

WARNING: This is a ONE-WAY migration. Backup first!
"""

import asyncio
import shutil
from pathlib import Path
from sqlalchemy import text

from cassey.storage.database import get_db
from cassey.config.settings import settings

USERS_ROOT = settings.USERS_ROOT
GROUPS_ROOT = settings.GROUPS_ROOT


async def get_personal_groups():
    """Get all individual groups with their users."""
    async with get_db() as conn:
        query = text("""
            SELECT
                g.group_id,
                g.name,
                g.owner_user_id,
                uw.user_id
            FROM groups g
            JOIN user_workspaces uw ON g.group_id = uw.group_id
            WHERE g.type = 'individual'
        """)
        return await conn.fetch(query)

def migrate_group_data(group_id: str, user_id: str):
    """Move data from group dir to user dir."""
    group_dir = GROUPS_ROOT / group_id
    user_dir = USERS_ROOT / user_id

    if not group_dir.exists():
        print(f"  No data found for {group_id}")
        return

    print(f"  Migrating {group_dir} → {user_dir}")

    # Move each subdirectory
    for subdir in ["files", "db", "mem", "reminders", "kb", "vs", "workflows"]:
        group_subdir = group_dir / subdir
        user_subdir = user_dir / subdir

        if group_subdir.exists():
            user_subdir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(group_subdir), str(user_subdir))
            print(f"    ✓ Moved {subdir}/")

    # Remove empty group directory
    try:
        group_dir.rmdir()
        print(f"  ✓ Removed empty group directory")
    except OSError:
        print(f"  ! Group directory not empty, manual cleanup needed")

async def migrate():
    """Main migration function."""
    print("Starting personal group migration...")
    print("⚠️  BACKUP YOUR DATA FIRST!")

    # Get all personal groups
    groups = await get_personal_groups()
    print(f"Found {len(groups)} personal groups")

    for group in groups:
        group_id = group['group_id']
        user_id = group['user_id']
        print(f"\nMigrating: {group_id} (user: {user_id})")
        migrate_group_data(group_id, user_id)

    print("\n✅ Migration complete!")
    print("\nNext steps:")
    print("1. Test the application")
    print("2. If everything works, apply migration 005_remove_personal_groups.sql")
    print("3. Delete empty group directories manually")

if __name__ == "__main__":
    asyncio.run(migrate())
```

---

### Phase 8: Testing Strategy

**Unit Tests to Update:**

1. **Test path resolution:**
   - `tests/test_file_sandbox.py` - Test user_id vs group_id priority
   - `tests/test_group_storage.py` - Test personal group removal

2. **Test Telegram channel:**
   - Verify files go to `/data/users/{user_id}/files/`
   - Verify no group creation for individual users

3. **Test DB/VS routing:**
   - Individual mode: `/data/users/{user_id}/db/`
   - Team mode: `/data/groups/{group_id}/db/`

**Integration Test:**
```python
async def test_individual_vs_team_storage():
    # Individual user (Telegram)
    set_user_id("telegram:123456")
    sandbox = get_sandbox()
    assert sandbox.root == USERS_ROOT / "telegram:123456" / "files"

    # Team workspace
    clear_user_id()
    set_group_id("group_acme")
    sandbox = get_sandbox()
    assert sandbox.root == GROUPS_ROOT / "group_acme" / "files"
```

---

## Rollout Plan

### Stage 1: Preparation (Week 1)
- [ ] Create detailed migration script
- [ ] Write migration SQL (forward + rollback)
- [ ] Document data loss risks

### Stage 2: Code Changes (Week 2)
- [ ] Update `file_sandbox.py` path resolution
- [ ] Update `telegram.py` context setting
- [ ] Update `group_storage.py` (remove personal groups)
- [ ] Update `db_storage.py`, `lancedb_storage.py`, etc.

### Stage 3: Testing (Week 2)
- [ ] Unit tests for all changes
- [ ] Integration tests for individual vs team modes
- [ ] Manual testing with Telegram bot

### Stage 4: Data Migration (Week 3)
- [ ] **BACKUP DATA FIRST**
- [ ] Run migration script to move personal data
- [ ] Verify data moved correctly
- [ ] Test application with migrated data

### Stage 5: Database Cleanup (Week 3)
- [ ] Apply SQL migration 005
- [ ] Drop `user_workspaces` table
- [ ] Remove individual groups from database

### Stage 6: Cleanup (Week 4)
- [ ] Remove deprecated functions
- [ ] Update documentation
- [ ] Delete empty group directories

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Data loss during migration** | HIGH | Comprehensive backup before migration; test migration script on staging |
| **Breaking existing workflows** | HIGH | Maintain backward compatibility with legacy thread paths; gradual rollout |
| **Permission system relies on groups** | MEDIUM | Update permission checks to support user_id context |
| **HTTP channel assumes groups** | LOW | HTTP channel can continue using groups (team workspaces) |
| **Vector store embeddings** | LOW | Re-indexing may be needed after path changes |

---

## Success Criteria

✅ **Clear architecture:**
- `/data/users/{user_id}/` = Individual ownership
- `/data/groups/{group_id}/` = Team ownership
- No "individual groups" exist

✅ **Telegram users work correctly:**
- Files stored at `/data/users/telegram:123456/files/`
- No group auto-creation for individual users

✅ **Teams work correctly:**
- Files stored at `/data/groups/team_acme/files/`
- Multiple team members can access shared data

✅ **No data loss:**
- All existing personal data migrated to user directories
- All team data remains in group directories

✅ **Code is cleaner:**
- `user_workspaces` table removed
- `ensure_user_group()` function removed
- Simpler path resolution logic

---

## Open Questions

1. **HTTP web app authentication:**
   - How will users authenticate to team workspaces?
   - Need OAuth/team invitation system?

2. **Group creation:**
   - How are team groups created now?
   - Manual admin action? Self-service?

3. **Permission system:**
   - Current system uses `group_members` for permissions
   - For individual users (no group), how are permissions handled?
   - Solution: Individual users have full access to their own `/data/users/{user_id}/` directory

4. **Legacy thread support:**
   - Keep thread-based paths for backward compatibility?
   - Or require all threads to have user_id or group_id?

---

## Files to Modify

| File | Changes |
|------|----------|
| `src/cassey/storage/file_sandbox.py` | Update path resolution priority (user_id first) |
| `src/cassey/channels/telegram.py` | Set user_id context, not group_id for individuals |
| `src/cassey/storage/group_storage.py` | Remove `ensure_user_group()`, update `ensure_thread_group()` |
| `src/cassey/storage/db_storage.py` | Support user_id-based paths |
| `src/cassey/storage/db_tools.py` | **CRITICAL:** Fix split storage bug (use group_id context) |
| `src/cassey/storage/lancedb_storage.py` | Support user_id-based paths |
| `src/cassey/storage/memory_storage.py` | Support user_id-based paths |
| `src/cassey/storage/reminder.py` | Support user_id-based paths |
| `src/cassey/config/settings.py` | Add `get_user_*path()` helpers |
| `migrations/005_remove_personal_groups.sql` | Drop `user_workspaces`, individual groups |
| `scripts/migrate_personal_groups_to_users.py` | Data migration script |
| `tests/test_file_sandbox.py` | Update tests for new path logic |
| `tests/test_group_storage.py` | Update tests for personal group removal |

---

## Estimated Timeline

- **Preparation:** 3-5 days
- **Code changes:** 5-7 days
- **Testing:** 3-5 days
- **Data migration:** 2-3 days (including backup/verification)
- **Documentation:** 1-2 days
- **Total:** ~3-4 weeks

---

## References

- Current architecture discussion: `workspace-to-group-refactoring-plan.md`
- Group storage implementation: `src/cassey/storage/group_storage.py`
- File sandbox implementation: `src/cassey/storage/file_sandbox.py`
- Telegram channel: `src/cassey/channels/telegram.py`
