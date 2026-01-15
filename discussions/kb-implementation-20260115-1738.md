# KB Implementation Notes (2026-01-15 17:38)

## Summary
- Added a separate KB storage root (`KB_ROOT`) that mirrors per-thread DuckDB layout used by `DB_ROOT`.
- Created a KB storage wrapper to reuse existing DBStorage behavior with the new root.
- Documented the KB storage layout and configuration.
- Created the KB directory under `data/`.

## Files Changed / Added
- `src/cassey/config/settings.py`
  - Added `KB_ROOT` setting with default `./data/kb`.
  - Added `resolve_kb_root` validator to keep paths absolute.
- `src/cassey/storage/kb_storage.py` (new)
  - `KBStorage` subclass of `DBStorage` scoped to `settings.KB_ROOT`.
  - `get_kb_storage()` global accessor.
- `src/cassey/storage/__init__.py`
  - Exported `KBStorage` and `get_kb_storage`.
- `README.md`
  - Added `KB_ROOT` env var to configuration.
  - Documented KB storage layout under `data/kb/`.
- `.env.example`
  - Added `KB_ROOT=./data/kb`.
- `data/kb/` (directory created)

## Rationale
- Keeps KB data isolated from app DB storage and avoids single-writer contention with core DB usage.
- Aligns with existing per-thread DB file organization for easy operational parity.

## Tests
- Not run (not requested).

## Follow-ups (optional)
- Add KB registry tracking similar to `db_paths` if needed.
- Add KB-specific tools or retrieval pipeline wiring when integrating search.
