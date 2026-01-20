# Plan: Remove FILES_ROOT + DB_ROOT (Fully)

## Goal
Eliminate `FILES_ROOT` and `DB_ROOT` from settings and runtime usage. All file/DB paths should derive from `USERS_ROOT` (per-thread), with no legacy migration logic.

## Scope
- Settings: remove `FILES_ROOT` and `DB_ROOT` fields + validators.
- Storage: update file sandbox + DB storage to use `USERS_ROOT` paths only.
- Python tool: remove dependency on `FILES_ROOT`.
- Migration helpers: remove legacy path fallbacks in `settings.get_thread_*`.
- Env: remove any reference to `FILES_ROOT`/`DB_ROOT` in docs and examples (already removed from `.env` and `.env.example`).

## Implementation Steps
1. **Settings cleanup**
   - Remove `FILES_ROOT` and `DB_ROOT` from `src/executive_assistant/config/settings.py`.
   - Delete their `@field_validator` handlers.
   - Update `get_thread_files_root` and `get_thread_db_path` to derive paths directly from `USERS_ROOT` without legacy fallback to `FILES_ROOT`/`DB_ROOT`.

2. **File sandbox**
   - Update `src/executive_assistant/storage/file_sandbox.py` to derive per-thread file roots via `settings.get_thread_files_root(thread_id)` only.
   - Remove any direct usage of `settings.FILES_ROOT`.

3. **DB storage**
   - Update `src/executive_assistant/storage/db_storage.py` to use `settings.get_thread_db_path(thread_id)` instead of `settings.DB_ROOT`.
   - Remove checks that compare against `DB_ROOT`.

4. **Python tool**
   - Update `src/executive_assistant/tools/python_tool.py` to rely on `settings.get_thread_files_root(thread_id)` or `settings.get_thread_root(thread_id)` (whichever is intended for DATA_PATH).
   - Remove direct reference to `settings.FILES_ROOT`.

5. **Docs + references**
   - Search for `FILES_ROOT` and `DB_ROOT` references across docs/tests and remove or update any mention.

## Tests
- Run existing file/DB tool tests (if any).
- Run a smoke check:
  - Create a file via file tools and confirm it lands under `data/users/{thread_id}/files/`.
  - Create a DB table via DB tools and confirm it persists under `data/users/{thread_id}/db/db.db`.

## Risks
- Legacy users with data in `data/files/{thread_id}` or `data/db/{thread_id}.db` will no longer be migrated automatically.

## Rollback
- Revert this change and restore the legacy fallback logic in `settings.get_thread_*` methods.
