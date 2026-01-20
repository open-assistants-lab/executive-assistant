# User Identity Schema Design - Elaborated

**Date:** 2025-01-20
**Status:** Schema refinement for cross-channel identity unification

---

## Core Design Principle

**thread_id as the entity identifier**

Each thread (conversation channel) has exactly ONE identity record that:
1. Starts as anonymous (auto-created)
2. Can be upgraded to verified (after merge)
3. Points to a persistent user_id for data consolidation

---

## Schema Design

### 1. Primary Schema: identities Table

```sql
CREATE TABLE identities (
    -- Primary key: thread_id (one identity per thread)
    thread_id TEXT PRIMARY KEY,
    
    -- Identity metadata
    identity_id TEXT NOT NULL,           -- "anon_telegram_123456" or "user_abc123"
    channel TEXT NOT NULL,               -- 'telegram', 'email', 'http'
    identifier TEXT NOT NULL,            -- Raw channel ID: '123456', 'user@example.com'
    
    -- Verification/merge state
    persistent_user_id TEXT,             -- NULL for anon, 'user_*' after merge
    verification_status TEXT DEFAULT 'anonymous',  -- 'anonymous', 'pending', 'verified'
    verification_method TEXT,            -- 'email', 'phone', 'oauth'
    verification_contact TEXT,           -- Email/phone used for verification
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    verified_at TIMESTAMP,
    merged_at TIMESTAMP,
    
    -- Relationships
    merged_from_thread_id TEXT,          -- If this is result of merge, what was original thread_id
    merged_into_thread_id TEXT,          -- If this thread was merged, where did it go?
    
    -- Constraints
    UNIQUE(identity_id),                  -- Each identity_id is unique
    UNIQUE(persistent_user_id)            -- Each persistent user is unique (NULL allowed)
);

-- Indexes for lookups
CREATE INDEX idx_identities_persistent_user ON identities(persistent_user_id) WHERE persistent_user_id IS NOT NULL;
CREATE INDEX idx_identities_channel ON identities(channel);
CREATE INDEX idx_identities_verification ON identities(verification_status);
CREATE INDEX idx_identities_contact ON identities(verification_contact) WHERE verification_contact IS NOT NULL;
```

---

## Key Design Decisions

### Decision 1: thread_id as PRIMARY KEY

**Why**: Each conversation thread has exactly one identity record.

**Examples**:
```
thread_id = "telegram:123456"        → 1 identity record
thread_id = "email:user@example.com" → 1 identity record
thread_id = "http:session_abc123"    → 1 identity record
```

**Benefit**: Clean 1:1 relationship between threads and identities.

---

### Decision 2: identity_id vs persistent_user_id Separation

**Two identity fields with different purposes**:

| Field | Type | Purpose | Example |
|-------|------|---------|---------|
| `identity_id` | TEXT | Current display ID | "anon_telegram_123456" |
| `persistent_user_id` | TEXT | Final merged ID | "user_abc123" |

**Flow**:
```
Stage 1 (Anonymous):
  identity_id = "anon_telegram_123456"
  persistent_user_id = NULL

Stage 2 (Verified):
  identity_id = "anon_telegram_123456"  (unchanged)
  persistent_user_id = "user_abc123"     (now set)
```

**Why both?**
- `identity_id`: The original "native" ID (never changes, keeps history)
- `persistent_user_id`: The unified "final" ID (shared across threads after merge)

**Query patterns**:
```python
# Get all threads for a persistent user
threads = db.query("""
    SELECT thread_id, identity_id, channel
    FROM identities
    WHERE persistent_user_id = ?
""", "user_abc123")

# Result:
# thread_id = "telegram:123456", identity_id = "anon_telegram_123456", channel = "telegram"
# thread_id = "email:user@example.com", identity_id = "anon_email_user_example_com", channel = "email"
```

---

### Decision 3: Auto-Generated identity_id

**Rule**: `identity_id` = `anon_{channel}_{sanitized_identifier}`

```python
def generate_identity_id(thread_id: str) -> str:
    """
    Generate identity_id from thread_id.
    
    Examples:
        "telegram:123456" → "anon_telegram_123456"
        "email:user@example.com" → "anon_email_user_example_com"
        "http:session_abc-123" → "anon_http_session_abc_123"
    """
    channel, identifier = thread_id.split(":", 1)
    sanitized = re.sub(r'[^a-zA-Z0-9-]', '_', identifier)
    return f"anon_{channel}_{sanitized}"
```

**Properties**:
- Deterministic (same thread_id always generates same identity_id)
- Human-readable (can see channel and identifier)
- Filesystem-safe (only alphanumeric, underscore, hyphen)
- Unique per thread (thread_id is unique)

---

## Identity Lifecycle

### Stage 1: Anonymous User (Auto-Created)

```sql
-- When first message arrives on telegram:123456
INSERT INTO identities (
    thread_id,
    identity_id,
    channel,
    identifier,
    verification_status
) VALUES (
    'telegram:123456',
    'anon_telegram_123456',  -- Auto-generated
    'telegram',
    '123456',
    'anonymous'
);
```

**State**:
- Storage: `data/users/anon_telegram_123456/`
- Can use system, create files, databases
- Cannot merge threads yet

---

### Stage 2: Verification Requested

```python
@tool
def request_identity_merge(verification_contact: str, method: str = "email"):
    """Request to merge anonymous identity."""
    thread_id = get_thread_id()  # "telegram:123456"
    
    # Check current state
    identity = db.query("""
        SELECT * FROM identities WHERE thread_id = ?
    """, thread_id)
    
    if identity['verification_status'] == 'verified':
        return f"Already verified as {identity['persistent_user_id']}"
    
    # Generate verification code
    code = generate_code()
    
    # Store pending verification
    db.execute("""
        UPDATE identities
        SET verification_status = 'pending',
            verification_method = ?,
            verification_contact = ?
        WHERE thread_id = ?
    """, method, verification_contact, thread_id)
    
    # Send code
    send_email(verification_contact, f"Your code: {code}")
    
    return f"Verification code sent to {verification_contact}"
```

**Database state**:
```
thread_id = "telegram:123456"
identity_id = "anon_telegram_123456"
verification_status = "pending"
verification_contact = "user@example.com"
```

---

### Stage 3: Verified & Merged

```python
@tool
def confirm_identity_merge(code: str):
    """Complete identity merge after verification."""
    thread_id = get_thread_id()
    
    # Verify code
    if not verify_code(thread_id, code):
        return "Invalid code"
    
    # Check if user already exists with this email
    existing_user = db.query("""
        SELECT persistent_user_id FROM identities
        WHERE verification_contact = (
            SELECT verification_contact FROM identities WHERE thread_id = ?
        )
        AND persistent_user_id IS NOT NULL
    """, thread_id)
    
    if existing_user:
        # Merge into existing user
        persistent_user_id = existing_user['persistent_user_id']
    else:
        # Create new persistent user
        persistent_user_id = f"user_{uuid4()}"
    
    # Update identity
    db.execute("""
        UPDATE identities
        SET persistent_user_id = ?,
            verification_status = 'verified',
            verified_at = NOW(),
            merged_at = NOW()
        WHERE thread_id = ?
    """, persistent_user_id, thread_id)
    
    # Move data (covered in Phase 4)
    move_user_data(
        from_id=identity['identity_id'],
        to_id=persistent_user_id
    )
    
    return f"Merged! Your persistent ID: {persistent_user_id}"
```

**Database state after merge**:
```
thread_id = "telegram:123456"
identity_id = "anon_telegram_123456"  (unchanged - keeps history)
persistent_user_id = "user_abc123"     (NOW SET - unified identity)
verification_status = "verified"
verified_at = 2025-01-20 00:15:00
```

---

## Multi-Thread Merge

### Scenario: Same User, Multiple Channels

**Initial state (3 separate threads)**:
```
Row 1: thread_id="telegram:123456", identity_id="anon_telegram_123456", persistent_user_id=NULL
Row 2: thread_id="email:user@example.com", identity_id="anon_email_user_example_com", persistent_user_id=NULL
Row 3: thread_id="http:session_xyz", identity_id="anon_http_session_xyz", persistent_user_id=NULL
```

**Step 1: Verify telegram thread**:
```
Row 1: thread_id="telegram:123456", identity_id="anon_telegram_123456", persistent_user_id="user_abc123"
Row 2: thread_id="email:user@example.com", identity_id="anon_email_user_example_com", persistent_user_id=NULL
Row 3: thread_id="http:session_xyz", identity_id="anon_http_session_xyz", persistent_user_id=NULL
```

**Step 2: Merge email thread**:
```python
@tool
def merge_additional_identity(thread_id_to_merge: str):
    """Merge another thread into current user."""
    current_thread_id = get_thread_id()  # "telegram:123456"
    
    # Get current user's persistent ID
    current = db.query("""
        SELECT persistent_user_id FROM identities WHERE thread_id = ?
    """, current_thread_id)
    
    if not current['persistent_user_id']:
        return "You must verify your identity first"
    
    # Update target thread to point to same persistent user
    db.execute("""
        UPDATE identities
        SET persistent_user_id = ?,
            verification_status = 'verified',
            merged_at = NOW(),
            merged_into_thread_id = ?
        WHERE thread_id = ?
    """, current['persistent_user_id'], current_thread_id, thread_id_to_merge)
    
    # Move data
    source_identity = db.query("SELECT identity_id FROM identities WHERE thread_id = ?", thread_id_to_merge)
    move_user_data(
        from_id=source_identity['identity_id'],
        to_id=current['persistent_user_id']
    )
    
    return f"Merged {thread_id_to_merge} into your account"
```

**After merging email**:
```
Row 1: thread_id="telegram:123456", identity_id="anon_telegram_123456", persistent_user_id="user_abc123"
Row 2: thread_id="email:user@example.com", identity_id="anon_email_user_example_com", persistent_user_id="user_abc123"
Row 3: thread_id="http:session_xyz", identity_id="anon_http_session_xyz", persistent_user_id=NULL
```

**After merging http**:
```
Row 1: thread_id="telegram:123456", identity_id="anon_telegram_123456", persistent_user_id="user_abc123"
Row 2: thread_id="email:user@example.com", identity_id="anon_email_user_example_com", persistent_user_id="user_abc123"
Row 3: thread_id="http:session_xyz", identity_id="anon_http_session_xyz", persistent_user_id="user_abc123"
```

**Key insight**: All 3 threads now have different `identity_id` but same `persistent_user_id`.

---

## Query Patterns

### Pattern 1: Get All Threads for User

```python
def get_user_threads(persistent_user_id: str) -> list[dict]:
    """Get all threads belonging to a persistent user."""
    return db.query("""
        SELECT 
            thread_id,
            identity_id,
            channel,
            identifier,
            verified_at,
            merged_at
        FROM identities
        WHERE persistent_user_id = ?
        ORDER BY created_at
    """, persistent_user_id)
```

**Example result**:
```python
[
    {
        'thread_id': 'telegram:123456',
        'identity_id': 'anon_telegram_123456',
        'channel': 'telegram',
        'identifier': '123456',
        'verified_at': datetime(2025, 1, 20, 0, 15),
        'merged_at': datetime(2025, 1, 20, 0, 15)
    },
    {
        'thread_id': 'email:user@example.com',
        'identity_id': 'anon_email_user_example_com',
        'channel': 'email',
        'identifier': 'user@example.com',
        'verified_at': datetime(2025, 1, 20, 0, 20),
        'merged_at': datetime(2025, 1, 20, 0, 20)
    }
]
```

---

### Pattern 2: Get User Data Across All Channels

```python
def get_unified_user_data(persistent_user_id: str) -> dict:
    """Get all data (files, DBs, VS, mem, meta) across all user's channels."""
    threads = get_user_threads(persistent_user_id)

    unified_data = {
        'files': [],
        'databases': [],
        'vector_stores': [],
        'memories': [],  # ⚠️ ADDED: Memory database
        'metadata': {}   # ⚠️ ADDED: meta.json
    }

    for thread in threads:
        # Each thread's data is at: data/users/{identity_id}/
        base_path = Path(f"data/users/{thread['identity_id']}")

        # Collect files
        if (base_path / "files").exists():
            for file in (base_path / "files").iterdir():
                unified_data['files'].append({
                    'path': file,
                    'channel': thread['channel'],
                    'thread_id': thread['thread_id']
                })

        # Collect databases
        if (base_path / "db").exists():
            for db_file in (base_path / "db").glob("*.sqlite"):
                unified_data['databases'].append({
                    'path': db_file,
                    'channel': thread['channel'],
                    'thread_id': thread['thread_id']
                })

        # Collect vector stores
        if (base_path / "vs").exists():
            for vs in (base_path / "vs").iterdir():
                unified_data['vector_stores'].append({
                    'path': vs,
                    'channel': thread['channel'],
                    'thread_id': thread['thread_id']
                })

        # ⚠️ ADDED: Collect memory database
        mem_db = base_path / "mem" / "mem.db"
        if mem_db.exists():
            unified_data['memories'].append({
                'path': mem_db,
                'channel': thread['channel'],
                'thread_id': thread['thread_id']
            })

        # ⚠️ ADDED: Collect metadata
        meta_file = base_path / "meta.json"
        if meta_file.exists():
            import json
            with open(meta_file) as f:
                meta = json.load(f)
                unified_data['metadata'][thread['thread_id']] = meta

    return unified_data
```

**Note**: After physical merge, all data is consolidated to `data/users/{persistent_user_id}/`, so this function is only needed during transition or for analysis.

---

### Pattern 3: Resolve Identity from Thread

```python
def resolve_identity(thread_id: str) -> dict:
    """Get identity info for a thread."""
    return db.query("""
        SELECT 
            thread_id,
            identity_id,
            channel,
            identifier,
            persistent_user_id,
            verification_status,
            verified_at
        FROM identities
        WHERE thread_id = ?
    """, thread_id)
```

**Before merge**:
```python
{
    'thread_id': 'telegram:123456',
    'identity_id': 'anon_telegram_123456',
    'channel': 'telegram',
    'identifier': '123456',
    'persistent_user_id': None,
    'verification_status': 'anonymous',
    'verified_at': None
}
```

**After merge**:
```python
{
    'thread_id': 'telegram:123456',
    'identity_id': 'anon_telegram_123456',
    'channel': 'telegram',
    'identifier': '123456',
    'persistent_user_id': 'user_abc123',  # NOW SET
    'verification_status': 'verified',
    'verified_at': datetime(2025, 1, 20, 0, 15)
}
```

---

## Storage Path Mapping

### Path Resolution Logic

```python
def get_user_storage_path(thread_id: str) -> Path:
    """
    Get storage path for a thread's data.
    
    Paths are user-scoped: data/users/{identity_id}/
    """
    identity = resolve_identity(thread_id)
    
    # Use identity_id for path (anon_* or user_*)
    # After merge, data is moved from anon_* to user_*
    user_id = identity['persistent_user_id'] or identity['identity_id']
    
    return Path(f"data/users/{user_id}")
```

**Examples**:
```
Before merge:
  thread_id = "telegram:123456"
  identity_id = "anon_telegram_123456"
  persistent_user_id = NULL
  Path = data/users/anon_telegram_123456/

After merge:
  thread_id = "telegram:123456"
  identity_id = "anon_telegram_123456"
  persistent_user_id = "user_abc123"
  Path = data/users/user_abc123/
```

---

## Migration Strategy

### Current State → Target State

**Current (after storage refactoring)**:
```
data/users/telegram_123456/
data/users/email_user_example_com/
```

**Problem**: These are channel-based paths, not identity-based.

**Migration needed**:
```
Step 1: Create identity records
  INSERT INTO identities (thread_id, identity_id, channel, identifier)
  VALUES 
    ('telegram:123456', 'anon_telegram_123456', 'telegram', '123456'),
    ('email:user@example.com', 'anon_email_user_example_com', 'email', 'user@example.com')

Step 2: Rename directories to match identity_id
  mv data/users/telegram_123456/ data/users/anon_telegram_123456/
  mv data/users/email_user_example_com/ data/users/anon_email_user_example_com/

Step 3: After user verification, merge:
  mv data/users/anon_telegram_123456/ data/users/user_abc123/
  mv data/users/anon_email_user_example_com/ data/users/user_abc123/
```

---

## Benefits of This Schema

### 1. Clean Separation of Concerns

- `thread_id`: Identifies the conversation channel
- `identity_id`: Identifies the pre-merge identity (anon_*)
- `persistent_user_id`: Identifies the post-merge unified user (user_*)

### 2. Full History Preservation

```python
# Can trace back to original thread even after merge
original_thread = db.query("""
    SELECT thread_id, channel, identifier 
    FROM identities 
    WHERE persistent_user_id = ?
    ORDER BY created_at
""", "user_abc123")

# Result shows all threads that were merged:
# - Started as telegram:123456
# - Added email:user@example.com
# - Added http:session_xyz
```

### 3. Flexible Query Patterns

```python
# All anonymous users (not yet verified)
anons = db.query("""
    SELECT * FROM identities 
    WHERE verification_status = 'anonymous'
""")

# All verified users
users = db.query("""
    SELECT DISTINCT persistent_user_id 
    FROM identities 
    WHERE persistent_user_id IS NOT NULL
""")

# All threads for a user (cross-channel)
threads = db.query("""
    SELECT * FROM identities 
    WHERE persistent_user_id = ?
""", "user_abc123")
```

### 4. Supports Future Enhancements

```sql
-- Add user preferences
CREATE TABLE user_preferences (
    persistent_user_id TEXT PRIMARY KEY REFERENCES identities(persistent_user_id),
    timezone TEXT DEFAULT 'UTC',
    language TEXT DEFAULT 'en',
    theme TEXT DEFAULT 'dark'
);

-- Add user profile
CREATE TABLE user_profiles (
    persistent_user_id TEXT PRIMARY KEY REFERENCES identities(persistent_user_id),
    display_name TEXT,
    bio TEXT,
    avatar_url TEXT
);
```

---

## Open Questions

1. **Should identity_id be updatable?**
   - Current design: NO (immutable, set at creation)
   - Alternative: Allow renaming? (e.g., anon_123456 → user_chosen_name)
   - Trade-off: Simplicity vs flexibility

2. **Should we support deleting/ anonymizing users?**
   - GDPR right to be forgotten
   - How to handle merged identities?
   - Cascading deletes vs anonymization

3. **Should persistent_user_id be in a separate table?**
   - Current: In identities table (denormalized)
   - Alternative: users table with 1:N relationship
   - Trade-off: Query simplicity vs normalization

---

## Summary

**Core principle**: thread_id as PRIMARY KEY, identity_id as display name, persistent_user_id as unified identifier

**Key properties**:
- One identity record per thread
- Auto-generated identity_id (anon_*) for anonymous users
- Upgradable to persistent_user_id (user_*) after verification
- Multiple threads can share same persistent_user_id (cross-channel unification)
- Full history preserved (identity_id never changes)

**Next steps**:
1. Implement Phase 1: Create identities table, auto-create anonymous users
2. Implement Phase 2: Verification and merge flow
3. Implement Phase 3: Physical data migration with conflict resolution
4. Implement Phase 4: Advanced merge features (smart merging, preferences)
