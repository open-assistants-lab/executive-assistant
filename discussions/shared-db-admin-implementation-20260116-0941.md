# Shared DB (Admin Write, Everyone Read) - Implementation Summary

## Goal
Allow all users/threads to read from a shared, organization-wide DB while restricting writes to admin users.

## What Was Implemented
### 1) Shared DB Storage
- Added a shared DB storage wrapper that ignores thread_id and uses a single file path.
- File: `src/cassey/storage/shared_db_storage.py`

### 2) Shared DB Tools (Admin-Guarded Writes)
- Read tools (available to all):
  - `query_shared_db` (read-only SQL guard)
  - `list_shared_db_tables`
  - `describe_shared_db_table`
  - `export_shared_db_table`
- Write tools (admin-only):
  - `create_shared_db_table`
  - `insert_shared_db_table`
  - `drop_shared_db_table`
  - `import_shared_db_table`
  - `execute_shared_db`
- File: `src/cassey/storage/shared_db_tools.py`

### 3) Admin Detection (User Context)
- Added per-request user_id context (ContextVar + thread fallback).
- Set/clear user_id in channel base for each message.
- Files:
  - `src/cassey/storage/file_sandbox.py`
  - `src/cassey/channels/base.py`

### 4) Registry Wiring
- Shared DB tools are now registered in `get_all_tools()`.
- File: `src/cassey/tools/registry.py`

### 5) Public API Exposure
- Exported shared DB storage in storage package.
- File: `src/cassey/storage/__init__.py`

### 6) Configuration
- Added new settings:
  - `SHARED_DB_PATH` (default: `./data/shared/shared.db`)
  - `ADMIN_USER_IDS` (comma-separated)
  - `ADMIN_THREAD_IDS` (comma-separated)
- Files:
  - `src/cassey/config/settings.py`
  - `.env.example`
  - `README.md`

## Behavior Notes
- Non-admins can only run read-only SQL in `query_shared_db`; anything else returns an error.
- Admins are recognized by `ADMIN_USER_IDS` (preferred) or `ADMIN_THREAD_IDS` (fallback).
- If no admins are configured, write tools return a configuration error message.

## Files Changed / Added
- Added: `src/cassey/storage/shared_db_storage.py`
- Added: `src/cassey/storage/shared_db_tools.py`
- Updated: `src/cassey/storage/file_sandbox.py`
- Updated: `src/cassey/channels/base.py`
- Updated: `src/cassey/tools/registry.py`
- Updated: `src/cassey/storage/__init__.py`
- Updated: `src/cassey/config/settings.py`
- Updated: `.env.example`
- Updated: `README.md`

## Follow-Up Suggestions (Optional)
- Add explicit tool grouping in prompts so LLM learns shared DB semantics.
- Consider a stricter SQL parser for `query_shared_db` if you want to allow only SELECT/CTE with no PRAGMA.
