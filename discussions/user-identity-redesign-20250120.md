# User Identity Redesign Plan - 2025-01-20

## Overview

Redesign user_id system to automatically assign anonymous identities on first interaction, with clean merge flow to persistent user identities.

## Critical Architecture Change

### Path Structure

**OLD (thread-based paths)** ❌:
```
data/users/{thread_id}/
├── files/
├── db/
└── vs/
```

**NEW (user-based paths)** ✅:
```
data/users/{user_id}/
├── files/
├── db/
└── vs/
```

This means storage is organized by **user_id**, not thread_id!

**Impact**: When threads are merged, they automatically share the same storage location.

## Current Problems

1. ❌ user_id can be NULL for anonymous users
2. ❌ No clear anonymous user tracking
3. ❌ Merge process is manual and unclear
4. ❌ Thread ownership tracking is incomplete

## User Data Structure

**Current (thread-based paths)** ❌:
```
data/users/{thread_id}/
├── files/          # User files (file_sandbox.py)
├── db/             # SQLite databases (db_storage.py)
├── vs/             # Vector Store collections (vs_tools.py)
├── mem/            # Memory database (mem.db) - mem_tools.py
└── meta.json       # Thread metadata inventory (meta_registry.py)
```

**New (user-based paths)** ✅:
```
data/users/{user_id}/
├── files/          # User files (file_sandbox.py)
├── db/             # SQLite databases (db_storage.py)
├── vs/             # Vector Store collections (vs_tools.py)
├── mem/            # Memory database (mem.db) - mem_tools.py
└── meta.json       # User metadata inventory (meta_registry.py)
```

**What Each Component Stores:**
- `files/` - User-uploaded and created files
- `db/` - SQLite tables for structured data (timesheets, logs, etc.)
- `vs/` - Vector store collections for semantic search (knowledge base)
- `mem/mem.db` - Persistent memory database for user facts/preferences
- `meta.json` - Lightweight inventory of files, DB tables, VS collections, reminders

**Note**: Reminders are stored in PostgreSQL, not as files.

## Proposed Solution

### Identity Lifecycle

```
1. First interaction → anon_{sanitized_thread_id}
2. User verifies identity → user_{uuid}
3. Merge complete → all threads have same user_id
```

### Example Flow

```python
# === First Interaction ===

# User sends Telegram message
thread_id = "telegram:123456789"
user_id = "anon_telegram_123456789"  # Auto-created

# User sends email
thread_id = "email:user@example.com"
user_id = "anon_email_user_example_com"  # Auto-created

# === After Merge ===

# Both threads now point to same user
thread_id = "telegram:123456789"
user_id = "user_550e8400-e29b-41d4-a716-446655440000"

thread_id = "email:user@example.com"
user_id = "user_550e8400-e29b-41d4-a716-446655440000"
```

**Key Point**: thread_id NEVER changes, only user_id is updated.

## Phase 1: Anonymous Identity Tracking

### 1.1 Create Identity Table

```sql
CREATE TABLE identities (
    identity_id TEXT PRIMARY KEY,          -- "anon_telegram_123456" or "user_abc"
    persistent_user_id TEXT,               -- NULL for anonymous, set after merge
    channel TEXT,                          -- 'telegram', 'email', 'http'
    thread_id TEXT NOT NULL UNIQUE,        -- The thread this identity belongs to
    created_at TIMESTAMP DEFAULT NOW(),
    merged_at TIMESTAMP,                   -- NULL until merged
    verification_status TEXT DEFAULT 'anonymous',  -- 'anonymous', 'pending', 'verified'
    verification_method TEXT,              -- 'email', 'phone', 'oauth', etc.
    verification_contact TEXT               -- Email/phone for verification
);
```

### 1.2 Thread ID Sanitization

Create helper function to convert thread_id to safe user_id:

```python
def sanitize_thread_id_to_user_id(thread_id: str) -> str:
    """
    Convert thread_id to anonymous user_id.

    Examples:
        "telegram:123456789" → "anon_telegram_123456789"
        "email:user@example.com" → "anon_email_user_example_com"
        "http:session-abc-123" → "anon_http_session_abc_123"
    """
    # Extract channel and identifier
    parts = thread_id.split(":", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid thread_id format: {thread_id}")

    channel, identifier = parts

    # Sanitize identifier for use in user_id
    # Replace special chars with underscores
    safe_identifier = re.sub(r'[^a-zA-Z0-9-]', '_', identifier)

    return f"anon_{channel}_{safe_identifier}"
```

### 1.3 Auto-Create Anonymous Users

Update channel handlers to auto-create identities:

```python
# Telegram channel
async def handle_telegram_message(update):
    thread_id = f"telegram:{update.message.chat_id}"
    user_id = sanitize_thread_id_to_user_id(thread_id)

    # Create identity if not exists
    create_identity_if_not_exists(
        thread_id=thread_id,
        user_id=user_id,
        channel="telegram"
    )

    # Process message with this user_id
    await process_message(thread_id, user_id, update.message.text)

# Email channel (future)
async def handle_email_message(from_email, content):
    thread_id = f"email:{from_email}"
    user_id = sanitize_thread_id_to_user_id(thread_id)

    # Create identity if not exists
    create_identity_if_not_exists(
        thread_id=thread_id,
        user_id=user_id,
        channel="email"
    )

    # Process message
    await process_message(thread_id, user_id, content)
```

### 1.4 Update User Registry

```python
# user_registry.py

def create_identity_if_not_exists(
    thread_id: str,
    user_id: str,
    channel: str
) -> None:
    """Create anonymous identity if it doesn't exist."""
    conn = get_pg_conn()

    conn.execute("""
        INSERT INTO identities (identity_id, thread_id, channel)
        VALUES (?, ?, ?)
        ON CONFLICT (thread_id) DO NOTHING
    """, (user_id, thread_id, channel))

def get_identity_by_thread_id(thread_id: str) -> dict | None:
    """Get identity by thread_id."""
    conn = get_pg_conn()

    result = conn.execute("""
        SELECT * FROM identities WHERE thread_id = ?
    """, (thread_id,)).fetchone()

    return dict(result) if result else None
```

## Phase 2: Merge Flow

### 2.1 Verification Request

User initiates merge by providing verification contact:

```python
@tool
def request_identity_merge(
    verification_contact: str,
    method: str = "email"
) -> str:
    """
    Request to merge current anonymous identity with persistent user.

    Args:
        verification_contact: Email or phone for verification
        method: 'email' or 'phone'

    Returns:
        Confirmation with verification code sent.
    """
    thread_id = get_thread_id()
    identity = get_identity_by_thread_id(thread_id)

    if not identity:
        return "No anonymous identity found for current thread"

    if identity['verification_status'] == 'verified':
        return f"Already merged as {identity['persistent_user_id']}"

    # Generate verification code
    code = generate_verification_code()

    # Store pending verification
    store_pending_verification(
        identity_id=identity['identity_id'],
        verification_contact=verification_contact,
        code=code,
        method=method
    )

    # Send verification code
    if method == "email":
        send_email(verification_contact, f"Your code: {code}")
    elif method == "phone":
        send_sms(verification_contact, f"Your code: {code}")

    return f"Verification code sent to {verification_contact}. Use confirm_identity_merge(code='{code}') to complete merge."
```

### 2.2 Complete Merge

```python
@tool
def confirm_identity_merge(code: str) -> str:
    """
    Complete identity merge after verification.

    Args:
        code: Verification code received via email/phone

    Returns:
        Success message with new persistent user_id.
    """
    thread_id = get_thread_id()
    identity = get_identity_by_thread_id(thread_id)

    if not identity:
        return "No anonymous identity found"

    # Verify code
    verification = get_pending_verification(identity['identity_id'], code)
    if not verification:
        return "Invalid or expired verification code"

    # Create persistent user
    persistent_user_id = f"user_{uuid4()}"

    # Update identity record
    update_identity_merge(
        identity_id=identity['identity_id'],
        persistent_user_id=persistent_user_id,
        verification_status="verified",
        merged_at=NOW()
    )

    # Update thread ownership
    update_thread_user_id(thread_id, persistent_user_id)

    return f"Identity merged! Your persistent user_id: {persistent_user_id}"
```

### 2.3 Merge Multiple Identities

Allow users to merge multiple identities after first merge:

```python
@tool
def merge_additional_identity(thread_id_to_merge: str) -> str:
    """
    Merge another anonymous identity into current persistent user.

    Args:
        thread_id_to_merge: Thread ID of identity to merge

    Returns:
        Success message.
    """
    current_thread_id = get_thread_id()
    current_identity = get_identity_by_thread_id(current_thread_id)

    if not current_identity or current_identity['verification_status'] != 'verified':
        return "You must verify your identity first before merging others"

    # Get identity to merge
    identity_to_merge = get_identity_by_thread_id(thread_id_to_merge)
    if not identity_to_merge:
        return f"Identity not found: {thread_id_to_merge}"

    # Update to same persistent_user_id
    update_identity_merge(
        identity_id=identity_to_merge['identity_id'],
        persistent_user_id=current_identity['persistent_user_id'],
        verification_status="verified",
        merged_at=NOW()
    )

    # Update thread ownership
    update_thread_user_id(thread_id_to_merge, current_identity['persistent_user_id'])

    return f"Merged {thread_id_to_merge} into your persistent account"
```

## Phase 3: User-Based Path Implementation

### 3.1 Path Structure (User-Based, Fresh Install)

**Initial state (anonymous users)** ✅:
```
data/users/anon_telegram_123456/
├── files/notes.txt
├── db/timesheets.sqlite
└── vs/knowledge

data/users/anon_email_user_example_com/
├── files/report.pdf
├── db/logs.sqlite
└── vs/docs
```

**After merge** ✅:
```
data/users/user_abc123/
├── files/
│   ├── notes.txt  ← From telegram
│   └── report.pdf  ← From email
├── db/
│   ├── timesheets.sqlite  ← From telegram
│   └── logs.sqlite  ← From email
└── vs/
    ├── knowledge/  ← From telegram
    └── docs/  ← From email
```

**Note**: No migration needed - this is a fresh installation. All new data will be created with user-based paths directly.

### 3.2 Update File Sandbox

```python
# file_sandbox.py

def get_sandbox() -> FileSandbox:
    """
    Get sandbox instance for current user_id.

    Paths are now: data/users/{user_id}/
    """
    user_id = get_user_id()
    if not user_id:
        # Fallback to thread_id (shouldn't happen after migration)
        thread_id = get_thread_id()
        user_id = sanitize_thread_id_to_user_id(thread_id)

    user_path = settings.get_user_files_path(user_id)
    user_path.mkdir(parents=True, exist_ok=True)
    return FileSandbox(root=user_path)
```

### 3.4 Update DB Storage

```python
# db_storage.py

def get_db_storage() -> DBStorage:
    """
    Get DB storage for current user_id.

    Paths are now: data/users/{user_id}/db/
    """
    user_id = get_user_id()
    if not user_id:
        thread_id = get_thread_id()
        user_id = sanitize_thread_id_to_user_id(thread_id)

    db_path = settings.get_user_db_path(user_id)
    return DBStorage(db_path)
```

### 3.5 Update VS Storage

```python
# vs_tools.py

def _get_storage_id() -> str:
    """
    Get storage ID (user_id) for VS operations.

    Paths are now: data/users/{user_id}/vs/
    """
    user_id = get_user_id()
    if not user_id:
        thread_id = get_thread_id()
        user_id = sanitize_thread_id_to_user_id(thread_id)

    return user_id
```

## Phase 4: Merge Conflict Resolution

Since paths are now user-based, conflicts occur **during merge** when moving data:

### 4.1 File Conflicts During Merge

```python
def merge_user_data(source_user_id: str, target_user_id: str):
    """
    Merge data from source_user into target_user.

    Handles conflicts by renaming with source identifier.
    """
    source_path = Path(f"data/users/{source_user_id}")
    target_path = Path(f"data/users/{target_user_id}")

    # Merge files
    source_files = source_path / "files"
    target_files = target_path / "files"

    if source_files.exists():
        target_files.mkdir(parents=True, exist_ok=True)

        for file in source_files.iterdir():
            dest = target_files / file.name

            # Handle conflict
            if dest.exists():
                # Rename with source identifier
                safe_source = source_user_id.replace(':', '_')
                file.rename(target_files / f"{safe_source}_{file.name}")
            else:
                file.rename(dest)

    # Merge DBs (keep both, prefix tables)
    # Merge VS (keep both, prefix collections)
```

### 4.2 Merge Flow Update

```python
@tool
def confirm_identity_merge(code: str) -> str:
    """
    Complete identity merge after verification.

    This moves data from anon_* to user_* paths.
    """
    thread_id = get_thread_id()
    identity = get_identity_by_thread_id(thread_id)

    # Verify code...
    # Create persistent user...
    persistent_user_id = f"user_{uuid4()}"

    # OLD path
    old_path = Path(f"data/users/{identity['identity_id']}")

    # NEW path
    new_path = Path(f"data/users/{persistent_user_id}")
    new_path.mkdir(parents=True, exist_ok=True)

    # Move data (handles conflicts)
    for item in ['files', 'db', 'vs', 'mem', 'meta.json']:
        if item == 'meta.json':
            # Handle file, not directory
            old_file = old_path / 'meta.json'
            new_file = new_path / 'meta.json'

            if old_file.exists():
                if new_file.exists():
                    # Merge JSON files
                    merge_meta_json(old_file, new_file, source_id=identity['identity_id'])
                    old_file.unlink()  # Delete old after merge
                else:
                    old_file.rename(new_file)
            continue

        # Handle directories
        old_subdir = old_path / item
        new_subdir = new_path / item

        if old_subdir.exists():
            new_subdir.mkdir(parents=True, exist_ok=True)

            for subitem in old_subdir.iterdir():
                dest = new_subdir / subitem.name
                if dest.exists():
                    # Rename with source identifier
                    safe_id = identity['identity_id'].replace(':', '_')
                    subitem.rename(new_subdir / f"{safe_id}_{subitem.name}")
                else:
                    subitem.rename(dest)

    # Update metadata
    update_identity_merge(...)
    update_thread_user_id(thread_id, persistent_user_id)

    # Remove old empty path
    if old_path.exists():
        try:
            old_path.rmdir()
        except:
            pass  # Not empty, keep it

    return f"Identity merged! Data moved to {persistent_user_id}"
```

## Implementation Priority

### Phase 1: Anonymous Identity Tracking ✅ COMPLETED
- [x] Create `identities` table
- [x] Add `sanitize_thread_id_to_user_id()` function
- [x] Update Telegram channel to auto-create `anon_*` users
- [x] Update HTTP channel to auto-create `anon_*` users
- [x] Update user_registry.py functions
- [x] Add tests (manual - Cassey starts successfully)

### Phase 2: Merge Flow ✅ COMPLETED
- [x] Add `request_identity_merge()` tool
- [x] Add `confirm_identity_merge()` tool (with data moving)
- [x] Add `merge_additional_identity()` tool
- [x] Implement verification code system
- [x] Handle file/DB/VS conflicts during merge
- [x] Add `get_my_identity()` tool for debugging
- [x] Add tests (Cassey starts with 55 tools)

### Phase 3: User-Based Path Implementation ✅ COMPLETED
- [x] Update file_sandbox.py to use user_id paths
- [x] Update db_storage.py to use user_id paths
- [x] Update vs_tools.py to use user_id paths
- [x] Update mem_tools.py to use user_id paths
- [x] Update meta_registry.py to use user_id paths
- [x] Test with fresh data (no migration needed - verified working)

### Phase 4: Advanced Conflict Resolution ⏳ LOW PRIORITY (DEFERRED)
- [ ] Smart file merging (merge text content instead of renaming)
- [ ] DB table merging (combine rows from same tables)
- [ ] VS collection merging (merge documents from same collections)
- [ ] User preferences for conflict resolution

## Files to Modify

1. **Database Schema**:
   - `src/cassey/storage/user_registry.py` - Add identities table

2. **Channel Handlers**:
   - `src/cassey/channels/telegram.py` - Auto-create anon users
   - `src/cassey/channels/http.py` - Auto-create anon users (future)

3. **Storage Paths** (CRITICAL - change from thread_id to user_id):
   - `src/cassey/config/settings.py` - Already has `get_user_*_path(user_id)` functions
   - `src/cassey/storage/file_sandbox.py` - Use user_id instead of thread_id for paths
   - `src/cassey/storage/db_storage.py` - Use user_id instead of thread_id for paths
   - `src/cassey/storage/vs_tools.py` - Use user_id instead of thread_id for storage_id
   - `src/cassey/tools/mem_tools.py` - Use user_id instead of thread_id for mem.db path ⚠️ MISSED!
   - `src/cassey/storage/meta_registry.py` - Use user_id instead of thread_id for meta.json ⚠️ MISSED!

4. **Tools**:
   - `src/cassey/tools/identity_tools.py` - NEW: Merge tools

5. **Utilities**:
   - `src/cassey/storage/helpers.py` - NEW: Sanitization functions, merge data helpers

## Benefits

### Before (Current)
```python
# Anonymous user - NULL user_id
thread_id = "telegram:123456"
user_id = None  # ❌ NULL

# Can't track anonymous users
# Can't merge identities
# Ownership unclear
```

### After (Proposed)
```python
# Anonymous user - auto-created
thread_id = "telegram:123456"
user_id = "anon_telegram_123456"  # ✅ Always set

# Can track all users
# Can merge identities
# Clear ownership
```

### After Merge
```python
# Merged user - persistent identity
thread_id = "telegram:123456"
user_id = "user_550e8400-..."  # ✅ Persistent

thread_id = "email:user@example.com"
user_id = "user_550e8400-..."  # ✅ Same user

# Unified view across channels
# All data accessible
# Clear ownership history
```

## Status

- [x] Plan created (no migration needed - fresh install)
- [x] Phase 1: Anonymous identity tracking ✅ COMPLETED
- [x] Phase 2: Merge flow ✅ COMPLETED
- [x] Phase 3: User-based path implementation ✅ COMPLETED
- [ ] Phase 4: Conflict resolution (deferred)

## Summary of Completed Work

### ✅ Phase 1: Anonymous Identity Tracking
- Created `migrations/003_add_identities_table.sql` with identities table
- Added `sanitize_thread_id_to_user_id()` in `src/cassey/storage/helpers.py`
- Added identity management functions to `src/cassey/storage/user_registry.py`:
  - `create_identity_if_not_exists()`
  - `get_identity_by_thread_id()`
  - `get_persistent_user_id()`
  - `update_identity_merge()`
  - `update_identity_pending()`
- Updated Telegram channel to auto-create `anon_telegram_*` users
- Updated HTTP channel to auto-create `anon_http_*` users

### ✅ Phase 2: Merge Flow
- Created `migrations/004_add_verification_codes.sql` for verification codes
- Created `src/cassey/tools/identity_tools.py` with 4 tools:
  - `request_identity_merge()` - Initiate verification with email/phone
  - `confirm_identity_merge()` - Complete merge after verification code
  - `merge_additional_identity()` - Merge more threads to existing user
  - `get_my_identity()` - Debug tool to see current identity status
- Updated `src/cassey/tools/registry.py` to include identity tools
- Cassey now loads **55 tools** (was 51, added 4 identity tools)
- Verification code system with 15-minute expiration
- Data movement with conflict handling (renames with source identifier)
- ⚠️ **Testing**: Startup verified (tools load successfully), functional testing pending

### ✅ Phase 3: User-Based Path Implementation
Updated all 5 storage components to use user_id paths instead of thread_id paths:

1. **file_sandbox.py**: Thread fallback now converts to `anon_{channel}_{id}`
2. **db_storage.py**: Prioritizes user_id → group_id → thread_id (converted)
3. **vs_tools.py**: `_get_storage_id()` prioritizes user_id → group_id → thread_id (converted)
4. **mem_storage.py**: `_get_db_path()` prioritizes user_id → group_id → thread_id (converted)
5. **meta_registry.py**: `_meta_path()` converts thread_id to user_id

All storage now uses `data/users/{user_id}/` structure instead of `data/users/{thread_id}/`.

### ⏳ Phase 4: Conflict Resolution (Deferred)
Advanced conflict resolution features for future consideration:
- Smart file merging (merge text content instead of renaming)
- DB table merging (combine rows from same tables)
- VS collection merging (merge documents from same collections)
- User preferences for conflict resolution

---

## Testing Status

### ✅ Startup Testing (Completed)
- Cassey starts successfully with 55 tools loaded
- No import errors or runtime errors
- All tools registered correctly

### ✅ Functional Testing (Completed)
All functional tests passed using `scripts/test_identity_merge.py`:

1. **✅ Test Anonymous Identity Creation**
   - Anonymous identity auto-created for `telegram:999888`
   - Identity ID correctly generated as `anon_telegram_999888`
   - Verification status: `anonymous`
   - persistent_user_id: `NULL`

2. **✅ Test Identity Merge Flow**
   - Merge request stores verification code in database
   - Code expiration set to 15 minutes
   - Identity status changes to `pending`

3. **✅ Test Identity Merge Confirmation**
   - Verification code validated correctly
   - Test data created in `data/users/anon_telegram_999888/`
   - Data successfully moved to `data/users/user_*/`
   - Files moved: `test.txt`, `data.json`
   - Identity status changes to `verified`
   - persistent_user_id set to `user_*`

4. **✅ Test Error Cases**
   - Invalid verification codes rejected correctly
   - Already-verified identities handled correctly

### Testing Results
**Date**: 2025-01-20
**Test Script**: `scripts/test_identity_merge.py`
**Result**: 🎉 **ALL TESTS PASSED (4/4)**

```
✅ Anonymous auto-creation works
✅ Request merge generates code
✅ Confirm merge with correct code succeeds
✅ Data moves from anon_* to user_*
✅ Error cases handled correctly
```

### ⏳ Manual Testing (Optional)
The following tests can be done manually through Telegram/HTTP:

- [ ] Test via Telegram (send real message)
- [ ] Test via HTTP (send real API request)
- [ ] Test `get_my_identity()` tool
- [ ] Test `merge_additional_identity()` with multiple threads
- [ ] Test with real email/SMS sending (currently code shown in response)
