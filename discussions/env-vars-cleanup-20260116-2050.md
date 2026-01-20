# Env Vars Cleanup (FILES_ROOT/DB_ROOT)

## Change Summary
- Removed `FILES_ROOT` and `DB_ROOT` from `.env`.
- Removed `FILES_ROOT` and `DB_ROOT` from `.env.example`.
- Kept `USERS_ROOT` as the active storage root.

## Impact Check
- **No functional break expected.** Both values have defaults in settings:
  - `FILES_ROOT` defaults to `./data/files`
  - `DB_ROOT` defaults to `./data/db`
- These defaults are still used by:
  - `src/executive_assistant/storage/file_sandbox.py`
  - `src/executive_assistant/storage/db_storage.py`
  - `src/executive_assistant/tools/python_tool.py`
  - `src/executive_assistant/config/settings.py` (legacy migration helpers)
- With env entries removed, the app falls back to defaults and continues to work.

## Notes
- If you want to remove the legacy paths entirely, we’ll need a follow‑up refactor to stop referencing `FILES_ROOT`/`DB_ROOT` in code and migration paths.
