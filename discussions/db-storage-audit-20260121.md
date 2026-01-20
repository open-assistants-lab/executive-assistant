# DB Storage Architecture Audit and Unification Plan

**Date:** January 21, 2026
**Status:** Ready for Implementation

---

## Executive Summary

**Finding:** Executive Assistant currently uses inconsistent database engines across similar use cases:
- Agent DB tools → SQLite (transactional)
- `/db` command → DuckDB (non-transactional)
- Shared DB → DuckDB (non-transactional)
- `/mem` → DuckDB + FTS ✅ (correct)

**Problem:** Same database operations (`/db` command) behave differently depending on entry point, leading to:
1. Inconsistent transactional guarantees
2. Potential data loss in `/db` command (no explicit commits)
3. Confusing architecture for maintenance

**Solution:** Unify all DB operations to SQLite except `/mem` which correctly uses DuckDB + FTS.

---

## Current Architecture (As of 2026-01-21)

### Storage Components

| Component | Engine | File | Purpose | Used By | Transaction Support |
|-----------|--------|-------|---------|-------------------|
| **DB Tools** | **SQLite** | `sqlite_db_storage.py` | Agent tools (`db_tools.py:79`) | ✅ Yes |
| **/db Command** | **DuckDB** | `db_storage.py` → `get_db_storage()` | CLI management commands | ❌ No |
| **Shared DB** | **DuckDB** | `shared_db_storage.py` → extends `DBStorage` | Organization-wide data | ❌ No |
| **MEM** | **DuckDB + FTS** | `mem_storage.py` | `/mem` command | ⚠️ Implicit (FTS) |
| **VS** | **LanceDB** | `lancedb_storage.py` | `/vs` command | N/A (vector store) |

### Code Flow Analysis

**1. Agent Tools (Transaction-Critical)**
```python
# src/executive_assistant/storage/db_tools.py:79-80
def _get_db() -> SQLiteDatabase:
    """Get current context's SQLite database."""
    return get_sqlite_db()  # ✅ Uses SQLite
```

**2. CLI /db Command (Non-Transactional)**
```python
# src/executive_assistant/channels/management_commands.py
# Lines 630, 659, 687, 706, 719, 744, 764, 777
storage = get_db_storage()  # ❌ Returns DBStorage (DuckDB)

# src/executive_assistant/storage/db_storage.py
class DBStorage:
    def get_connection(self) -> duckdb.DuckDBPyConnection:
        conn = duckdb.connect(str(db_path))
        return conn  # No commit/rollback methods!
```

**3. Shared DB Storage (Non-Transactional)**
```python
# src/executive_assistant/storage/shared_db_storage.py:9
class SharedDBStorage(DBStorage):  # ❌ Extends DuckDB DBStorage
    """Shared DB storage (single DB file for all threads)."""
```

**4. MEM Command (Correct)**
```python
# src/executive_assistant/storage/mem_storage.py:13
import duckdb

# Uses DuckDB with FTS extension
conn.execute("INSTALL fts")
conn.execute("LOAD fts")
conn.execute("PRAGMA create_fts_index('memories', ...)")
```

### Engine Comparison

| Feature | SQLite | DuckDB |
|---------|---------|---------|
| **Transactions** | ✅ `commit()`, `rollback()` methods | ❌ No transaction methods in `db_storage.py` |
| **Persistence** | ✅ ACID compliant, WAL mode | ⚠️ Best-effort (no explicit commits) |
| **Concurrency** | ✅ WAL mode, excellent for multi-thread | ⚠️ Single-threaded by default |
| **Full-Text Search** | Via extensions (not used) | ✅ Built-in FTS extension (used by MEM) |
| **Analytics** | Basic SQL | ✅ OLAP-optimized |

---

## Problems Identified

### Problem 1: Inconsistent Engine Usage

**Symptom:**
- Agent creates tables in SQLite (transactional)
- `/db` command creates tables in DuckDB (non-transactional)
- Same operation, different behavior and data location

**Impact:**
1. **Data Inconsistency**: Tables created via agent cannot be accessed via `/db` command and vice versa
2. **Reliability Risk**: DuckDB has no explicit commits → potential data loss on errors/crashes
3. **User Confusion**: Users expect `/db` command to access same data as agent tools

**Example Scenario:**
```bash
User: Create timesheet table via agent
Agent: ✅ Created in SQLite (data/users/{id}/db/db.sqlite)

User: Use /db create command
/bot: ✅ Created in DuckDB (data/users/{id}/db/db.sqlite) [WRONG!]
```

### Problem 2: DuckDB Lacks Transactions

**File:** `src/executive_assistant/storage/db_storage.py`

**Missing Methods:**
```python
# SQLite (sqlite_db_storage.py:38-44)
def commit(self) -> None: ...
def rollback(self) -> None: ...

# DuckDB (db_storage.py)
# ❌ NO commit() method
# ❌ NO rollback() method
# ❌ NO transaction context manager
```

**Impact:**
- `/db` command operations have no ACID guarantees
- Concurrent writes could corrupt data
- Partial updates not rolled back on errors

### Problem 3: Shared DB Storage Unused?

**File:** `src/executive_assistant/storage/shared_db_storage.py`

**Search Results:**
```bash
grep -r "SharedDBStorage" src/
# Only found in:
# - shared_db_storage.py (definition)
# - storage/__init__.py (export)
```

**Finding:** No active consumers found. Purpose unclear.

**Questions:**
1. Is shared DB intended for organization-wide data sharing?
2. If so, why not use SQLite for consistency?
3. If not used, should it be deprecated?

### Problem 4: Historical Inconsistency

**Previous Plan:** `discussions/db-switch-to-sqlite-plan.md` (2025-01-18)
- Talks about "seekdb_storage.py" (doesn't exist)
- Outdated file references
- Incomplete implementation status

**Current State (2026-01-21):**
- `sqlite_db_storage.py` ✅ Exists and complete
- `db_tools.py` ✅ Uses SQLite
- Only `/db` command and `shared_db_storage.py` still use DuckDB

---

## Expected Architecture

### Target State

| Component | Engine | Purpose | Notes |
|-----------|--------|---------|--------|
| **DB Tools + /db Command** | **SQLite** | Transactional, permanent database operations |
| **Shared DB** | **SQLite** | Organization-wide shared data (transactional) |
| **MEM** | **DuckDB + FTS** | Embedded memories with full-text search ✅ |
| **VS** | **LanceDB** | Semantic search (unchanged) |

### Rationale

**SQLite for DB Operations:**
- ✅ Transactional (ACID compliant)
- ✅ Permanent data persistence
- ✅ WAL mode for concurrency (already enabled in sqlite_db_storage.py:333)
- ✅ Battle-tested in `sqlite_db_storage.py`
- ✅ User expects consistent behavior across entry points

**DuckDB for MEM Only:**
- ✅ Full-Text Search (FTS) is DuckDB's strength
- ✅ Memories are simple key-value + FTS
- ✅ Analytics not needed for MEM
- ✅ `/mem` command already works correctly

**Shared DB to SQLite:**
- ✅ Same transactional guarantees as user DB
- ✅ Consistent storage architecture
- ✅ Easier maintenance (single engine for all transactional DBs)

---

## Required Changes

### Change 1: Convert `/db` Command to SQLite

**File:** `src/executive_assistant/channels/management_commands.py`

**Line 23 - Import:**
```python
# BEFORE:
from executive_assistant.storage.db_storage import get_db_storage

# AFTER:
from executive_assistant.storage.sqlite_db_storage import get_sqlite_db
```

**Lines 630, 659, 687, 706, 719, 744, 764, 777:**
```python
# BEFORE:
storage = get_db_storage()

# AFTER:
storage = get_sqlite_db()
```

**Impact:** All `/db` subcommands (`create`, `insert`, `query`, `describe`, `drop`, `export`) will use SQLite with transactions.

**Testing Required:**
- `/db create` - Create table from JSON
- `/db insert` - Append to table
- `/db query` - Execute SQL
- `/db describe` - Get table schema
- `/db drop` - Drop table
- `/db export` - Export to CSV

---

### Change 2: Convert Shared DB to SQLite

**File:** `src/executive_assistant/storage/shared_db_storage.py`

**Line 6 - Import:**
```python
# BEFORE:
from executive_assistant.storage.db_storage import DBStorage

# AFTER:
from executive_assistant.storage.sqlite_db_storage import SQLiteDatabase
```

**Line 9 - Class Definition:**
```python
# BEFORE:
class SharedDBStorage(DBStorage):

# AFTER:
class SharedDBStorage(SQLiteDatabase):
    """Shared DB storage using SQLite (transactional)."""
```

**Remove Constructor:**
```python
# DELETE lines 12-23 (old constructor)
def __init__(self, db_path: Path | None = None, db_name: str = "shared.db") -> None:
    # ...old code...

# REPLACE with:
def __init__(self, db_path: Path | None = None, db_name: str = "shared.db") -> None:
    """Initialize shared DB storage.

    Args:
        db_path: Full path to shared DB file. If None, uses SHARED_ROOT/db_name.
        db_name: Name of DB file (used only if db_path is None).
    """
    if db_path is None:
        db_path = settings.SHARED_ROOT / db_name
    db_path = Path(db_path).resolve()
    path = db_path  # SQLiteDatabase expects path directly

    # Get connection from SQLite storage
    from executive_assistant.storage.sqlite_db_storage import _get_sqlite_connection

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = _get_sqlite_connection("shared", path.parent)  # Use "shared" as storage_id

    super().__init__(
        workspace_id="shared",
        conn=conn,
        path=path
    )
```

**Update _get_db_path Method:**
```python
# DELETE lines 26-29 (old method)
def _get_db_path(self, thread_id: str | None = None) -> Path:
    # ...old code...

# REPLACE with (rely on parent class constructor):
# No need - parent SQLiteDatabase already handles path
```

**Impact:** Shared DB will use SQLite with transactions.

**Testing Required:**
- Create shared table
- Insert data
- Query data
- Verify ACID guarantees (commit/rollback)

---

### Change 3: Deprecate DuckDB DB Storage

**File:** `src/executive_assistant/storage/db_storage.py`

**Options:**

**Option A: Deprecate and Keep**
```python
# Add deprecation warning at top:
"""
DEPRECATED: DuckDB for DB operations is deprecated.

Use SQLite via `sqlite_db_storage.py` instead:
- For agent tools: Already migrated (see db_tools.py)
- For /db command: See management_commands.py migration plan
- For shared DB: See shared_db_storage.py migration plan

Migration Date: 2026-01-21

This file is kept only for potential future DuckDB analytics use cases.
"""
```

**Option B: Delete Entirely**
- If no other references found in codebase
- Safer: Search first before deleting

**Recommendation:** Option A (deprecate with warning) to avoid breaking if any hidden dependencies exist.

---

### Change 4: Update Storage Module Exports

**File:** `src/executive_assistant/storage/__init__.py`

**Lines 24-29 - Review imports:**
```python
# BEFORE:
from executive_assistant.storage.db_storage import (
    DBStorage,
    SharedDBStorage,  # Actually defined in shared_db_storage.py
)

# AFTER:
from executive_assistant.storage.sqlite_db_storage import (
    SQLiteDatabase,
)

# Keep SharedDBStorage export (from shared_db_storage.py after migration):
from executive_assistant.storage.shared_db_storage import SharedDBStorage
```

**Lines 49-51 - Exports:**
```python
# BEFORE:
"DBStorage",

# AFTER:
# Remove DBStorage from exports if deprecated
"SharedDBStorage",
```

---

### Change 5: Update Documentation

**File:** `TECHNICAL_ARCHITECTURE.md`

**Section: "Storage Architecture" (Current incorrect table)**

**BEFORE (incorrect):**
```
| Storage | Engine | Purpose |
|----------|--------|---------|
| **DB** | DuckDB | Temporary analytical data |
```

**AFTER (corrected):**
```
| Storage | Engine | Purpose |
|----------|--------|---------|
| **DB** | SQLite | Transactional, permanent data (timesheets, CRM, tasks) |
| **Shared DB** | SQLite | Organization-wide shared data |
| **MEM** | DuckDB + FTS | Embedded memories with full-text search |
```

**Section: "When to Use Each"**

**BEFORE:**
```
| Storage Type | Use Case |
|--------------|-----------|
| DuckDB | Temporary structured data (timesheets, logs) |
```

**AFTER:**
```
| Storage Type | Use Case |
|--------------|-----------|
| SQLite | Transactional data (timesheets, CRM, tasks) |
| DuckDB | Full-text search for memories |
| LanceDB | Semantic search for documents |
```

---

**File:** `README.md`

**Section: "Tool Capabilities" → "Database (per-thread)"**

**BEFORE:**
```
### Database (per-thread)
- **Create tables**: From JSON/CSV with automatic schema inference
- **Query**: Full SQL support via DuckDB
```

**AFTER:**
```
### Database (per-thread)
- **Create tables**: From JSON/CSV with automatic schema inference
- **Query**: Full SQL support via SQLite (transactional)
```

---

## Execution Plan

### Phase 1: Preparation
- [ ] Verify no hidden dependencies on `db_storage.py`
- [ ] Search codebase for `get_db_storage()` usage
- [ ] Confirm `shared_db_storage.py` intended purpose

### Phase 2: Implementation
- [ ] Update `management_commands.py` imports to use `get_sqlite_db()`
- [ ] Update `shared_db_storage.py` to extend `SQLiteDatabase`
- [ ] Add deprecation warning to `db_storage.py`
- [ ] Update `storage/__init__.py` exports

### Phase 3: Testing
- [ ] Test all `/db` subcommands with SQLite
- [ ] Test shared DB operations with SQLite
- [ ] Verify ACID guarantees (transactions, rollbacks)
- [ ] Run existing test suite (`test_sqlite_db_storage.py`)
- [ ] Regression tests for agent tools (should be unaffected)

### Phase 4: Documentation
- [ ] Update `TECHNICAL_ARCHITECTURE.md`
- [ ] Update `README.md`
- [ ] Create migration guide if needed

### Phase 5: Cleanup (Optional)
- [ ] Verify no active usage of `db_storage.py`
- [ ] Consider deleting `db_storage.py` entirely

---

## Questions for Review

1. **Shared DB Usage:**
   - Is `shared_db_storage.py` actively used in production?
   - What's the intended use case for organization-wide shared data?
   - If unused, should we deprecate it entirely?

2. **DuckDB Future:**
   - Do you have plans to use DuckDB for analytics workloads?
   - If yes, should we keep `db_storage.py` deprecate with warnings?
   - If no, should we delete entirely?

3. **Testing Coverage:**
   - Should we add tests specifically for `/db` command conversion?
   - Current `test_sqlite_db_storage.py` tests SQLite class but not CLI commands

---

## Summary

**Issue:** Inconsistent database engines across similar use cases
- Agent uses SQLite (transactional) ✅
- `/db` command uses DuckDB (non-transactional) ❌
- Shared DB uses DuckDB (non-transactional) ❌

**Solution:** Unify to SQLite for all DB operations
- SQLite is transactional and battle-tested
- Only `/mem` should use DuckDB + FTS (already correct)

**Impact:**
- Consistent ACID guarantees across all DB operations
- Simplified maintenance (single engine for transactional data)
- Better user experience (consistent behavior)

**Risk:** Low
- SQLite already used by agent tools successfully
- `/db` command needs simple import changes
- Shared DB migration is straightforward

---

## Implementation Notes (2026-01-21)

- `/db` command now uses SQLite (`get_sqlite_db()`), aligning with agent DB tools and user storage routing.
- `/db` export writes to user files path (anon_* user storage), not legacy thread path.
- Shared DB storage now uses SQLite via `shared_db_storage.py`.
- `/db` supports `scope=shared` to target the shared SQLite DB.

### Files Updated
- `src/executive_assistant/channels/management_commands.py`
- `src/executive_assistant/storage/shared_db_storage.py`

### Testing

Attempted:
```
uv run pytest tests/test_sqlite_db_storage.py
```

Result:
- Test file not found (`tests/test_sqlite_db_storage.py`).
- Pytest ran with 0 items collected.

## Related Documents

- `discussions/db-switch-to-sqlite-plan.md` (historical context, outdated)
- `TECHNICAL_ARCHITECTURE.md` (needs update)
- `README.md` (needs update)

---

**Document Created:** 2026-01-21
**Last Updated:** 2026-01-21
