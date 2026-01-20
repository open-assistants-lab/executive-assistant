# Data Folder Migration Plan (2026-01-15 23:39)

## Target Layout
```
./data/
  users/
    {thread_id}/
      files/
      db/
        main.db
      kb/
        main.db
```

- `thread_id` is sanitized (same rules as current file/db naming).
- `files/` holds all per-thread file sandbox content.
- `db/` and `kb/` are subfolders even if they currently hold a single file.

## Plan
1) **Define naming rules**
   - Confirm sanitization and file naming (e.g., `main.db` vs `{thread_id}.db`).
   - Recommended: `main.db` to keep per-thread folder clean.

2) **Update settings + storage helpers**
   - Add helpers to resolve per-thread roots under `data/users/{thread_id}`.
   - Maintain backward compatibility: if new path doesn’t exist, read from old `data/files`, `data/db`, `data/kb`.

3) **Migration script/command**
   - Move existing `data/files/{thread_id}` → `data/users/{thread_id}/files/`.
   - Move `data/db/{thread_id}.db` → `data/users/{thread_id}/db/main.db`.
   - Move `data/kb/{thread_id}.db` → `data/users/{thread_id}/kb/main.db`.
   - Keep a dry-run mode and logs for safety.

4) **Docs + tests**
   - Update env defaults (`FILES_ROOT`, `DB_ROOT`, `KB_ROOT`) to new base.
   - Add tests for path resolution and migration safety.

## Backward Compatibility Strategy
- On startup/tool usage, if `data/users/{thread_id}/...` not found, fall back to old location.
- Optionally auto-migrate on first access with a guard flag.


---

## Reviewer Notes (2025-01-15)

### Assessment

**Good design decisions:**
1. ✅ Per-thread consolidation makes sense (all user data in one place)
2. ✅ Backward compatibility fallback prevents data loss
3. ✅ `main.db` naming is cleaner than `{thread_id}.db`
4. ✅ Dry-run mode for migration safety

### Suggested Refinements

**1. Add pre-migration validation**

Before moving any data, validate:
- No duplicate `thread_id` conflicts between old paths
- Sufficient disk space for migration
- No open file handles/connections to old databases

**2. Add rollback capability**

If migration fails partway:
- Keep original data until migration is verified successful
- Support `--rollback` flag to undo partial migration
- Store migration state in a marker file (e.g., `data/.migration_complete`)

**3. Thread ID sanitization**

Document the exact sanitization rules:
```python
# Current (implied):
safe_thread_id = thread_id.replace(":", "_").replace("/", "_")

# Consider also:
# - Handling Unicode/non-ASCII characters
# - Length limits (filesystem constraints)
```

**4. Migration state tracking**

Store migration progress to handle interruptions:
```
data/.migration/
  state.json  # {"status": "in_progress", "completed_steps": ["files"], "started_at": "..."}
```

**5. Add verification step**

After migration, verify:
- All thread_ids migrated successfully
- Database integrity checks (SQLite `PRAGMA integrity_check`)
- File counts match between old and new locations

### Implementation Order Recommendation

1. **First** - Update path resolution helpers with fallback (backward compat)
2. **Second** - Create migration script with dry-run + verification
3. **Third** - Run migration manually first, verify, then automate
4. **Fourth** - Add tests for new path resolution

### Files to Modify

| File | Change |
|------|--------|
| `src/executive_assistant/config/settings.py` | Update path defaults |
| `src/executive_assistant/storage/file_sandbox.py` | Use new path helpers with fallback |
| `src/executive_assistant/storage/db_storage.py` | Use new path helpers with fallback |
| `scripts/migrate_data.py` | New migration script |
| `tests/test_migration.py` | New tests for migration logic |
