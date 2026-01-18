# DB Terminology Fix: Standardize on "DB"

## Issue

The codebase and documentation use inconsistent terminology for the per-workspace database component:

| Term Used | Locations |
|-----------|-----------|
| "workspace db" | Comments, some docs |
| "Workspace DB" | Architecture docs |
| "db" | Directory names, code |
| "DB" | Some docs, preferred term |

**Desired terminology:** `DB` (uppercase) or `db` (lowercase, for code/paths)

---

## Current Usage Analysis

### In Code (Directory Names, Variables)

✅ **Already correct** — uses lowercase `db`:
- `data/workspaces/{workspace_id}/db/` (directory)
- `get_workspace_db_path()` (function)
- `get_db_connection()` (function)

### In Documentation

❌ **Needs fixing** — inconsistent use of "workspace DB", "workspace db", "Workspace DB":
- Architecture diagrams
- README sections
- Plan documents

---

## Files to Update

### 1. Documentation Files

| File | Current Term | Target |
|------|--------------|--------|
| `README.md` | "workspace database" | "DB" |
| `docs/architecture.md` | "Workspace DB" | "DB" |
| `docs/storage.md` (if exists) | "workspace DB" | "DB" |
| `discussions/*.md` | Various | "DB" |

### 2. Code Comments

| File | Locations |
|------|-----------|
| `src/cassey/config/settings.py` | Method docstrings |
| `src/cassey/storage/*_storage.py` | Module docstrings, comments |
| `src/cassey/tools/db_tools.py` | Tool descriptions |

---

## Replacement Patterns

| Current | Target | Context |
|---------|--------|---------|
| "workspace database" | "DB" | General text |
| "Workspace DB" | "DB" | Even at sentence start |
| "workspace db" | "DB" | Always uppercase in prose |
| "Workspace DB" | "DB" | Title case not needed |
| "workspace DB" | "DB" | Remove qualifier |

**Principle:** "DB" is sufficient context. The workspace/tenant scoping is implicit in the architecture.

---

## Examples

### Before

```
├── Workspace DB (SQLite)     → User apps, timesheets
├── KB (DuckDB + VSS)         → Knowledge base
├── mem (DuckDB + FTS)        → Embedded memories
```

### After

```
├── DB (SQLite)               → User apps, timesheets
├── KB (DuckDB + VSS)         → Knowledge base
├── mem (DuckDB + FTS)        → Embedded memories
```

---

## Search and Replace

```bash
# Case-sensitive replacements in documentation
# (Use IDE find/replace for safety)

# In .md files
"workspace database" → "DB"
"Workspace DB" → "DB"
"workspace db" → "DB"
"workspace DB" → "DB"

# Preserve code/paths that use lowercase "db"
# Don't change: `db/`, `get_db_connection()`, etc.
```

---

## Updated Terminology Reference

| Component | Term | Usage |
|-----------|------|-------|
| Per-workspace SQL database | **DB** | Prose, documentation |
| Directory name | `db` | Paths, code |
| Variable name | `db` | Python variables |
| Class name | `SQLiteDatabase` | Type names |
| Function names | `get_db_connection()` | Code (lowercase) |
| Environment variables | `DB_*` | All caps |

---

## Quick Checklist

- [ ] Update `README.md`
- [ ] Update `docs/architecture.md` (if exists)
- [ ] Update plan documents in `discussions/`
- [ ] Review code comments in `src/cassey/config/settings.py`
- [ ] Review code comments in `src/cassey/storage/`
- [ ] Review tool descriptions in `src/cassey/tools/db_tools.py`

---

## Note

This is a **documentation-only fix**. No functional changes to code behavior.
