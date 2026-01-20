# Configuration Refactoring: YAML + .env

**Date:** 2025-01-18
**Author:** Claude (Sonnet)
**Status:** ✅ Implemented

---

## Overview

Refactored Executive Assistant's configuration system to use:
1. **`config.yaml`** - Application defaults (versioned, at project root)
2. **`.env`** - Secrets and environment-specific overrides (unversioned)

This separation makes it easier to manage defaults across environments while keeping secrets secure.

---

## Motivation

### Problems Solved:
1. **`.env.example` was too large** (174 lines) - mixed defaults with secrets
2. **Users had no runtime choice** - only langchain is supported, but `AGENT_RUNTIME` setting remained
3. **Hard to review changes** - defaults buried in environment variables
4. **Legacy path confusion** - `FILES_ROOT`/`DB_ROOT` no longer used but still configured

### Benefits:
- **Cleaner `.env`** - Only secrets and deployment overrides
- **Better organization** - Nested YAML structure for related settings
- **Easier deployment** - Change defaults in YAML without touching .env
- **Clearer separation** - Everyone commits YAML, no one commits .env
- **Single source of truth** - `config.yaml` at project root is easy to find

---

## Changes Summary

### Files Created

| File | Purpose | Lines |
|------|---------|-------|
| `config.yaml` | Application defaults (project root) | ~200 |
| `src/executive_assistant/config/loader.py` | YAML + .env merger | ~200 |

### Files Modified

| File | Changes |
|------|---------|
| `src/executive_assistant/config/settings.py` | Uses ConfigLoader, removed AGENT_RUNTIME, FILES_ROOT, DB_ROOT |
| `.env.example` | Now only secrets + env overrides (174→92 lines) |
| `src/executive_assistant/channels/base.py` | Removed runtime parameter |
| `src/executive_assistant/main.py` | Simplified, always uses langchain |
| `src/executive_assistant/dev_server.py` | Simplified, always uses langchain |
| `src/executive_assistant/agent/langchain_agent.py` | Updated error message |
| `src/executive_assistant/storage/chunking.py` | Embedding model now uses config setting |
| `src/executive_assistant/storage/file_sandbox.py` | Requires root parameter, no global fallback |
| `src/executive_assistant/storage/db_storage.py` | Requires root parameter, no global fallback |
| `src/executive_assistant/tools/python_tool.py` | Removed FILES_ROOT references |
| `src/executive_assistant/storage/meta_registry.py` | Updated DBStorage usage |
| `pyproject.toml` | Added pyyaml>=6.0.0 dependency |

### Files Removed

| File | Reason |
|------|--------|
| `config/default.yaml` | Moved to `config.yaml` at project root |
| `config/` directory | Empty, removed |

---

## Configuration Structure

### `config.yaml` Organization

```yaml
llm:              # LLM provider and models
  default_provider: openai
  anthropic: { ... }
  openai: { ... }
  ollama: { ... }

storage:          # Storage backends and paths
  checkpoint: postgres
  postgres: { ... }
  paths:            # 3-level hierarchy only (no legacy paths)
    shared_root: "./data/shared"
    groups_root: "./data/groups"
    users_root: "./data/users"

middleware:       # LangChain middleware
  summarization: { ... }
  status_updates: { ... }
  ...

vector_store:     # Embedding and chunking
memory:           # User memory extraction
context:          # Context management
logging:          # Log configuration
ocr:              # OCR settings
channels:         # Channel defaults (http host/port)
admin:            # Admin access control
```

**Removed from YAML:**
- Legacy paths (`files_root`, `db_root`) - use 3-level hierarchy
- External services (`firecrawl`, `searxng_host`, `temporal`) - moved to .env

### `.env.example` Structure

```bash
# ============================================================================
# LLM Provider Configuration
# ============================================================================
DEFAULT_LLM_PROVIDER=anthropic  # Optional override
ANTHROPIC_API_KEY=sk-ant-xxx
OPENAI_API_KEY=sk-xxx
ZHIPUAI_API_KEY=your-zhipu-key
OLLAMA_CLOUD_API_KEY=your-ollama-cloud-api-key

# ============================================================================
# Channel Configuration
# ============================================================================
EXECUTIVE_ASSISTANT_CHANNELS=telegram,http
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_WEBHOOK_URL=https://your-domain.com/webhook
TELEGRAM_WEBHOOK_SECRET=your-secret
HTTP_HOST=0.0.0.0
HTTP_PORT=8000

# ============================================================================
# Database Configuration
# ============================================================================
POSTGRES_PASSWORD=executive_assistant_password
# POSTGRES_HOST=localhost  # For remote DB

# ============================================================================
# External Services
# ============================================================================
SEARXNG_HOST=https://your-searxng-instance.com
FIRECRAWL_API_KEY=fc-your-firecrawl-api-key
FIRECRAWL_API_URL=https://api.firecrawl.dev
TEMPORAL_HOST=temporal.example.com
TEMPORAL_PORT=7233
TEMPORAL_NAMESPACE=default
TEMPORAL_TASK_QUEUE=executive_assistant-workflows
TEMPORAL_WEB_UI_URL=http://localhost:8080

# ============================================================================
# Optional Overrides
# ============================================================================
USERS_ROOT=/var/lib/executive_assistant/users
GROUPS_ROOT=/var/lib/executive_assistant/groups
CHECKPOINT_STORAGE=memory
LOG_LEVEL=DEBUG
```

---

## Implementation Details

### ConfigLoader (`src/executive_assistant/config/loader.py`)

**Purpose:** Merge YAML defaults with .env overrides

**How it works:**
1. Loads `config.yaml` from project root
2. Flattens nested YAML into env-var style keys
3. Environment variables override YAML values

**Priority (highest to lowest):**
1. Environment variable (`.env`)
2. YAML default (`config.yaml`)

**Example:**
```yaml
# config.yaml
llm:
  default_provider: anthropic
```
```bash
# .env
DEFAULT_LLM_PROVIDER=ollama  # Overrides YAML
```

### Removed Settings

| Setting | Reason |
|---------|--------|
| `AGENT_RUNTIME`, `AGENT_RUNTIME_FALLBACK` | Only langchain supported |
| `FILES_ROOT`, `DB_ROOT` | Legacy paths, use 3-level hierarchy |
| `SHARED_DB_PATH` | Multiple shared DBs now supported |

### Fixed Settings

| Setting | Before | After |
|---------|--------|-------|
| `VS_EMBEDDING_MODEL` | Hardcoded in code | Uses `config.yaml` |
| External services | In `config.yaml` | In `.env` (deployment-specific) |

---

## Storage Path Refactoring

### Old Structure (Removed)
```
data/
├── files/           # FILES_ROOT (deprecated)
├── db/              # DB_ROOT (deprecated)
└── mem/             # Legacy memory storage
```

### New Structure (3-Level Hierarchy)
```
data/
├── shared/          # Level 1: Org-wide (admin write, everyone read)
│   └── shared.db
├── groups/          # Level 2: Groups (collaborative, members can access)
│   └── {group_id}/
│       ├── files/
│       ├── vs/
│       ├── db/
│       └── workflows/
└── users/           # Level 3: Users (personal, only that user)
    └── {user_id}/
        ├── files/
        ├── db/
        └── mem/
```

### Impact on Code

**FileSandbox** - Now requires explicit root:
```python
# Before: Used global FILES_ROOT fallback
sandbox = FileSandbox()

# After: Must provide root
sandbox = FileSandbox(root=settings.get_user_files_path(user_id))
```

**DBStorage** - Now requires explicit root:
```python
# Before: Used global DB_ROOT fallback
storage = DBStorage()

# After: Must provide root
storage = DBStorage(root=db_path.parent)
```

**get_sandbox()** - Raises error if no context:
```python
# Before: Returned global sandbox if no context
sandbox = get_sandbox()  # _sandbox with FILES_ROOT

# After: Requires user_id, group_id, or thread_id context
sandbox = get_sandbox()  # Raises ValueError if no context
```

---

## Migration Guide

### For Developers

1. **Sync dependencies:**
   ```bash
   uv sync
   ```

2. **Update your .env:**
   ```bash
   # Copy new .env.example
   cp .env.example .env.new

   # Merge your existing API keys into .env.new
   # Then replace .env with .env.new
   ```

3. **Config file location changed:**
   - Old: `config/default.yaml`
   - New: `config.yaml` (project root)

4. **Legacy paths removed:**
   - If you used `data/files/` or `data/db/`, migrate to `data/users/`

### For Deployments

**Production:** Edit `config.yaml` for production-specific defaults
```yaml
storage:
  postgres:
    host: prod-db.example.com
channels:
  http:
    host: 0.0.0.0
    port: 80
```

**Development:** Keep YAML defaults, override in local `.env` if needed

---

## Verification

### Test Configuration Loading

```bash
uv run python -c "
from executive_assistant.config import settings
print(f'LLM Provider: {settings.DEFAULT_LLM_PROVIDER}')
print(f'Max Iterations: {settings.MAX_ITERATIONS}')
print(f'USERS_ROOT: {settings.USERS_ROOT}')
"
```

Expected output:
```
LLM Provider: <your .env value or 'openai'>
Max Iterations: 20
USERS_ROOT: /path/to/executive_assistant/data/users
```

### Verify YAML Keys Loaded

```bash
uv run python -c "
from executive_assistant.config.loader import get_yaml_defaults
defaults = get_yaml_defaults()
print(f'YAML keys loaded: {len(defaults)}')
print(f'Has FILES_ROOT: {\"STORAGE_PATHS_FILES_ROOT\" in defaults}')
print(f'Has DB_ROOT: {\"STORAGE_PATHS_DB_ROOT\" in defaults}')
"
```

Expected output:
```
YAML keys loaded: 70
Has FILES_ROOT: False
Has DB_ROOT: False
```

### Test Embedding Model from Config

```bash
uv run python -c "
from executive_assistant.config import settings
from executive_assistant.storage.chunking import _get_embedding_model
print(f'Model from config: {settings.VS_EMBEDDING_MODEL}')
model = _get_embedding_model()
print(f'Model loaded: {model}')
"
```

---

## Backward Compatibility

### ✅ Maintained:
- All existing environment variables still work
- `.env` file format unchanged
- Pydantic Settings API unchanged

### ⚠️ Breaking Changes:
- `AGENT_RUNTIME` and `AGENT_RUNTIME_FALLBACK` removed
- `FILES_ROOT` and `DB_ROOT` removed (use 3-level hierarchy)
- `SHARED_DB_PATH` removed (use `SharedDBStorage(db_name=...)`)
- `config/default.yaml` → `config.yaml` (moved to project root)
- `FileSandbox()` and `DBStorage()` now require `root` parameter
- `get_sandbox()` and `get_db_storage()` require context

### 📝 Migration Notes:
- `.env.example`: 174 → 92 lines (added channel config, storage paths, etc.)
- Config keys: 82 → 70 (removed legacy paths, moved external services)
- Old `.env` files continue to work but may have unused settings

---

## File Structure Changes

### Before
```
executive_assistant/
├── config/
│   └── default.yaml
├── .env.example
└── src/executive_assistant/config/
```

### After
```
executive_assistant/
├── config.yaml          ← Moved from config/default.yaml
├── .env.example
└── src/executive_assistant/config/
    ├── loader.py
    └── settings.py
```

---

## Configuration Count

| Source | Keys | Purpose |
|--------|------|---------|
| `config.yaml` | 70 | Application defaults |
| `.env` (secrets) | ~15 | Secrets + deployment overrides |

---

## Testing Checklist

- [x] Settings load from YAML correctly
- [x] .env overrides YAML values
- [x] All 70 YAML keys flattened correctly
- [x] `config.yaml` at project root loads
- [x] AGENT_RUNTIME references removed
- [x] FILES_ROOT and DB_ROOT removed
- [x] Legacy path fallbacks removed
- [x] FileSandbox requires root parameter
- [x] DBStorage requires root parameter
- [x] Embedding model uses config setting
- [x] External services in .env
- [x] .env.example has channel config
- [x] pyyaml dependency added

---

## Completed Improvements (Peer Review Feedback)

### ✅ 1. Update Docstring Reference (Completed 2025-01-18)
**Location:** `src/executive_assistant/config/loader.py:88`

Updated the `ConfigLoader` docstring to reference `config.yaml` instead of `config/default.yaml`.

### ✅ 2. Add Config Verification Command (Completed 2025-01-18)
**Status:** Implemented

A CLI command for configuration validation has been added:

```bash
uv run executive_assistant config verify
```

Output:
```
Executive Assistant Configuration Verification
========================================
✓ config.yaml loaded (70 keys)
✓ SHARED_ROOT: /path/to/data/shared
✓ GROUPS_ROOT: /path/to/data/groups
✓ USERS_ROOT: /path/to/data/users
✓ LLM provider: openai
✓ LLM API key configured
✓ PostgreSQL: localhost:5432/executive_assistant_db
✓ Checkpoint storage: postgres
========================================

✅ All checks passed!
```

**Files Modified:**
- `src/executive_assistant/main.py` - Added `config_verify()` function and CLI command handling

---

## References

- YAML config: `config.yaml` (project root)
- Loader implementation: `src/executive_assistant/config/loader.py`
- Settings class: `src/executive_assistant/config/settings.py`
- Environment template: `.env.example`
