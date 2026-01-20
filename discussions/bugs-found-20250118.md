# Bugs Found - Code Review (2025-01-18)

This document tracks bugs discovered during code review of the Executive Assistant codebase.

## Bug #1: Double fetchone() in `export_db_table`

**Location:** `src/executive_assistant/storage/db_tools.py:374`

**Severity:** High - Logic error causes incorrect row count reporting

**Current Code:**
```python
count_result = db.execute(f"SELECT COUNT(*) FROM {table_name}")
row_count = count_result.fetchone()[0] if count_result.fetchone() else 0
```

**Problem:** `fetchone()` is called twice. The first call fetches the row, the second call returns `None`. This means `row_count` will always be 0.

**Fix:**
```python
row = count_result.fetchone()
row_count = row[0] if row else 0
```

---

## Bug #2: Hardcoded Vector Dimension in SQL Query

**Location:** `src/executive_assistant/storage/duckdb_storage.py:146`

**Severity:** Medium - Breaks if embedding dimension changes

**Current Code:**
```python
array_distance(v.embedding, ?::FLOAT[384]) as distance
```

**Problem:** The vector dimension `384` is hardcoded in the SQL query. If a different embedding model is used (e.g., 768 dimensions), the query will fail.

**Fix:** Use the collection's dimension property:
```python
array_distance(v.embedding, ?::FLOAT[{self.dimension}]) as distance
```

This same issue appears in multiple locations:
- Line 146: `search_vector()`
- Line 207: `_search_hybrid()`
- Line 219: `_search_hybrid()` fallback

---

## Bug #3: Missing Import for SecurityError

**Location:** `src/executive_assistant/storage/kb_tools.py:426`

**Severity:** Medium - Unbound exception type

**Current Code:**
```python
try:
    validated_path = sandbox._validate_path(file_path)
    content = validated_path.read_text(encoding="utf-8")
except SecurityError as e:
    return f"Security error: {e}"
```

**Problem:** `SecurityError` is never imported. This will raise a `NameError` when a security error actually occurs.

**Fix:** Import `SecurityError` from the appropriate module:
```python
from executive_assistant.storage.file_sandbox import SecurityError
```

---

## Bug #4: Table Name Parsing Edge Case

**Location:** `src/executive_assistant/storage/duckdb_storage.py:593-602`

**Severity:** Low - Edge case could cause incorrect collection names

**Current Code:**
```python
if table_name.startswith(prefix):
    suffix = table_name[len(prefix):-5]
    if suffix:
        suffix = suffix.rstrip('"')
```

**Problem:** If a table name contains quotes in the middle (not just at the end), this logic will incorrectly strip them. The quote removal should only happen if the suffix actually ends with a quote.

**Fix:**
```python
if table_name.startswith(prefix):
    suffix = table_name[len(prefix):-5]
    if suffix:
        # Only remove trailing quote if present
        suffix = suffix[:-1] if suffix.endswith('"') else suffix
```

---

## Bug #5: SQL Injection Risk - Quote Character Not Sanitized

**Location:** `src/executive_assistant/storage/duckdb_storage.py:267`

**Severity:** Medium - Potential for SQL injection or query breakage

**Current Code:**
```python
return f'"{self.workspace_id.replace("-", "_").replace(":", "_")}__{safe_name}_docs"'
```

**Problem:** The quote character `"` is not in the replacement list. If `workspace_id` contains quotes, it will break out of the quoted identifier.

**Fix:**
```python
safe_workspace = self.workspace_id.replace("-", "_").replace(":", "_").replace('"', "_')
return f'"{safe_workspace}__{safe_name}_docs"'
```

This same pattern appears in multiple methods:
- `_table_name()` (line 267)
- `_table_name_unquoted()` (line 271-272)
- `_vector_table_name()` (line 278)
- `_fts_table_name()` (line 289)

---

## Additional Concerns (Non-Bugs)

### Resource Management - Unclosed DuckDB Connections

**Location:** `src/executive_assistant/storage/duckdb_storage.py:364-388`

The `_get_duckdb_connection()` function caches connections with `@lru_cache` but never explicitly closes them. In long-running processes, this could lead to:
- File descriptor exhaustion
- DuckDB resource limits
- Memory leaks

**Recommendation:** Implement connection cleanup or use a connection pool with proper lifecycle management.

### Silent Error Handling

Multiple locations catch exceptions and silently pass, making debugging difficult:
- `duckdb_storage.py:102-103` - FTS index refresh
- `duckdb_storage.py:216` - FTS fallback
- `duckdb_storage.py:508` - FTS creation

**Recommendation:** At minimum log these errors, even if continuing execution.

### Context Propagation in Async

The codebase relies on `contextvars.ContextVar` for thread_id/group_id. With LangGraph's async execution, ensure all `asyncio.create_task()` calls use `asyncio.create_task(coro(), context=contextvar.copy_context())` to propagate context.

### Naming Inconsistency

The codebase uses multiple terms for similar concepts:
- `workspace_id`
- `group_id`
- `storage_id`

**Recommendation:** Standardize on one term (appears to be migrating to `group_id`) and update references.

---

## Status

| Bug # | Description | Severity | Status |
|-------|-------------|----------|--------|
| 1 | Double fetchone() in export_db_table | High | **Fixed** |
| 2 | Hardcoded vector dimension | Medium | **Fixed** |
| 3 | Missing SecurityError import | Medium | **Fixed** |
| 4 | Table name parsing edge case | Low | **Fixed** |
| 5 | SQL injection - quote not sanitized | Medium | **Fixed** |

---

## Fix Details (2025-01-18)

### Bug #1 Fix: Double fetchone() in export_db_table

**File:** `src/executive_assistant/storage/db_tools.py:373-375`

**Before:**
```python
count_result = db.execute(f"SELECT COUNT(*) FROM {table_name}")
row_count = count_result.fetchone()[0] if count_result.fetchone() else 0
```

**After:**
```python
row = count_result.fetchone()
row_count = row[0] if row else 0
```

**Explanation:** `fetchone()` advances the cursor. Calling it twice meant the first call got the actual row, and the second call returned `None`. Storing the result of the first call fixes the bug.

**Test verification:** All DuckDB KB tests (19 tests) pass.

---

### Bug #2 Fix: Hardcoded vector dimension

**File:** `src/executive_assistant/storage/duckdb_storage.py`

**Locations fixed:**
1. Line 146 - `search_vector()`
2. Line 207 - `_search_hybrid()`
3. Line 219 - `_search_hybrid()` fallback

**Before:**
```python
array_distance(v.embedding, ?::FLOAT[384]) as distance
```

**After:**
```python
array_distance(v.embedding, ?::FLOAT[{self.dimension}]) as distance
```

**Explanation:** The hardcoded `384` only works for the `all-MiniLM-L6-v2` embedding model. Using `{self.dimension}` makes the code work with any embedding model dimension (e.g., 768 for `all-mpnet-base-v2`).

**Test verification:** All DuckDB KB tests pass, including `test_search`, `test_vector_search`, `test_hybrid_search`.

---

### Bug #3 Fix: Missing SecurityError import

**File:** `src/executive_assistant/storage/kb_tools.py:12`

**Before:**
```python
from executive_assistant.storage.file_sandbox import get_thread_id
```

**After:**
```python
from executive_assistant.storage.file_sandbox import SecurityError, get_thread_id
```

**Explanation:** The `add_file_to_kb` tool catches `SecurityError` (line 426) but never imported it. This would cause `NameError` when a security error actually occurs.

**Test verification:** Python tool tests pass, including `test_path_traversal_blocked` and `test_disallowed_file_extension`.

---

### Bug #4 Fix: Table name parsing edge case

**File:** `src/executive_assistant/storage/duckdb_storage.py:601-604`

**Before:**
```python
suffix = table_name[len(prefix):-5]
if suffix:
    suffix = suffix.rstrip('"')
```

**After:**
```python
suffix = table_name[len(prefix):-5]
if suffix:
    # Only remove trailing quote if present
    suffix = suffix[:-1] if suffix.endswith('"') else suffix
```

**Explanation:** `rstrip('"')` strips ALL trailing quotes, not just one. If a collection name legitimately ended with multiple quotes or had quotes in the middle, this would corrupt the name. The new code only removes a single trailing quote if present.

**Test verification:** `test_table_names` passes.

---

### Bug #5 Fix: SQL injection - quote character not sanitized

**File:** `src/executive_assistant/storage/duckdb_storage.py`

**Locations fixed:**
1. Line 267 - `_table_name()`
2. Line 272 - `_table_name_unquoted()`
3. Line 279 - `_vector_table_name()`
4. Line 291 - `_fts_table_name()`

**Before:**
```python
safe_workspace = self.workspace_id.replace("-", "_").replace(":", "_")
```

**After:**
```python
safe_workspace = self.workspace_id.replace("-", "_").replace(":", "_").replace('"', "_")
```

**Explanation:** The double quote `"` character was not being sanitized. Since table names are quoted identifiers (e.g., `"ws__collection_docs"`), a quote in `workspace_id` would break out of the identifier and allow SQL injection or query syntax errors.

**Test verification:** All DuckDB KB tests pass.

---

## Test Results

All 57 tests for DuckDB KB and Python tool pass:
- `test_duckdb_kb.py`: 19 tests PASSED
- `test_python_tool.py`: 38 tests PASSED

Unrelated test failures exist in PostgreSQL integration tests due to pending schema migration (missing `workspaces` table).
