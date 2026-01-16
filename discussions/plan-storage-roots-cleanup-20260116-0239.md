# Plan: Stop Legacy Root Dirs + Deprecate FILES_ROOT/DB_ROOT/KB_ROOT (2026-01-16 02:39)

## Observed Behavior
- `./data/db` and `./data/kb` are created on every restart even when the new per‑thread layout under `./data/users/{thread_id}/...` is intended.
- `.env` still exposes `FILES_ROOT`, `DB_ROOT`, `KB_ROOT`, which are legacy paths and cause confusion.

## Root Cause
- `DBStorage.__init__` and `KBStorage.__init__` eagerly `mkdir` their root paths during import (`db_tools` and `kb_tools` instantiate storage at import time), creating `./data/db` and `./data/kb`.
- Several code paths still write to `settings.FILES_ROOT` directly (Telegram uploads, db_import/export), bypassing the new `settings.get_thread_files_path()` helper.

## Proposed Changes
### 1) Lazy‑create DB/KB roots
- Remove eager `mkdir` from `DBStorage.__init__` and `KBStorage.__init__`.
- Create parent directories only when a DB/KB file is actually opened (`_get_db_path` / `get_connection`).

### 2) Route all file operations through thread-aware helpers
- Replace direct `settings.FILES_ROOT / safe_thread_id` with `settings.get_thread_files_path(thread_id)` in:
  - `src/cassey/channels/telegram.py` (file uploads)
  - `src/cassey/channels/management_commands.py` (file ops)
  - `src/cassey/storage/db_tools.py` (db_import/export)
  - `src/cassey/tools/python_tool.py` (sandbox root)
- This ensures only `./data/users/{thread_id}/files/` is created.

### 3) Deprecate legacy env vars (but keep fallback)
- Keep `FILES_ROOT`, `DB_ROOT`, `KB_ROOT` in `settings.py` for backward compatibility.
- Remove these from `.env.example` and `README.md` (mark as deprecated).
- Optional: add `ENABLE_LEGACY_PATHS=true` to allow fallback checks in `get_thread_*_path` (default on for now; can flip later).

### 4) Optional cleanup (manual)
- If no legacy data is needed, delete `./data/db` and `./data/kb` manually.
- Do **not** auto‑delete in code to avoid data loss.

## Implementation Steps
1. Update `DBStorage.__init__` to remove eager `mkdir`.
2. Update file path usage in `telegram.py`, `management_commands.py`, `db_tools.py`, `python_tool.py` to use `settings.get_thread_files_path()`.
3. Update `.env.example` and `README.md` to remove legacy roots (note deprecation).
4. (Optional) Add `ENABLE_LEGACY_PATHS` flag and guard legacy fallback in `settings.get_thread_*_path()`.

## Acceptance Criteria
- Restarting Cassey does **not** create `./data/db` or `./data/kb` unless legacy fallback is actually used.
- All user files, db, kb live under `./data/users/{thread_id}/...`.
- `.env.example` no longer advertises legacy roots.
