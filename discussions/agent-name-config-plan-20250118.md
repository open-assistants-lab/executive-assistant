# Agent Name Configuration Plan

**Date:** 2025-01-18
**Status:** ✅ **Implemented**
**Priority:** Medium

---

## Goal

Make the agent's name configurable via `config.yaml` so developers can easily customize what their bot calls itself without code changes.

---

## Problem

Currently "Executive Assistant" is hardcoded in multiple user-facing places:
- System prompts (4 locations)
- Telegram welcome/help messages
- HTTP API documentation
- Console output

Developers who want to deploy with their own name must find and replace across multiple files.

---

## Proposed Solution

Add a single `agent.name` configuration that is referenced wherever the bot name is displayed to users.

---

## Implementation Status

### ✅ Phase 1: Configuration (Completed)

**File:** `config.yaml`

```yaml
agent:
  # Agent display name - customize this for your deployment
  name: "Executive Assistant"
  # Maximum ReAct loop iterations to prevent infinite loops
  max_iterations: 20
```

**File:** `src/executive_assistant/config/settings.py`

```python
# Agent Configuration
AGENT_NAME: str = _yaml_field("AGENT_NAME", "Executive Assistant")
MAX_ITERATIONS: int = _yaml_field("AGENT_MAX_ITERATIONS", 20)
```

---

### ✅ Phase 2: User-Facing Replacements (Completed)

| File | Status | Change |
|------|--------|--------|
| `src/executive_assistant/config/constants.py` | ✅ | Added `get_default_system_prompt()` function |
| `src/executive_assistant/agent/prompts.py` | ✅ | Refactored to `_get_telegram_prompt()`, `_get_http_prompt()`, `get_default_prompt()` |
| `src/executive_assistant/channels/telegram.py` | ✅ | `/start` and `/help` use `settings.AGENT_NAME` |
| `src/executive_assistant/channels/http.py` | ✅ | API title and root endpoint use `settings.AGENT_NAME` |

---

## Files Modified

| File | Lines Changed |
|------|---------------|
| `config.yaml` | +3 |
| `src/executive_assistant/config/settings.py` | +3 |
| `src/executive_assistant/config/constants.py` | +20 (rewritten as function) |
| `src/executive_assistant/agent/prompts.py` | ~210 (refactored to functions) |
| `src/executive_assistant/channels/telegram.py` | ~4 |
| `src/executive_assistant/channels/http.py` | ~3 |
| **Total** | **~243 lines** |

---

## Testing Results

### Configuration Test
```
=== Agent Name Configuration ===
AGENT_NAME from settings: Executive Assistant ✓

=== Telegram Prompt ===
Contains AGENT_NAME: True ✓

=== HTTP Prompt ===
Contains AGENT_NAME: True ✓

=== Default Prompt ===
Contains AGENT_NAME: True ✓
```

### Unit Tests
```
tests/test_agent.py::TestPrompts::test_get_system_prompt PASSED ✓
tests/test_agent.py::TestPrompts::test_get_system_prompt_for_unknown_channel PASSED ✓
```

---

## How to Customize

### Option 1: Edit config.yaml
```yaml
agent:
  name: "Nova"  # Change this
```

### Option 2: Environment Variable (Override)
```bash
# In .env
AGENT_NAME=Nova
```

### Option 3: Runtime Override
```bash
AGENT_NAME=Nova uv run executive_assistant
```

---

## Configuration Priority

```
1. Environment variable AGENT_NAME (highest priority - for deployment)
2. config.yaml agent.name (default for the codebase)
3. Hardcoded "Executive Assistant" fallback (lowest priority)
```

---

## Backward Compatibility

- ✅ Default value is "Executive Assistant" - existing deployments unchanged
- ✅ No breaking changes to API or behavior
- ✅ Package name remains `executive_assistant`
- ✅ Legacy `DEFAULT_SYSTEM_PROMPT` constant preserved in constants.py

---

## Internal Code (Left Unchanged)

These locations remain as "Executive Assistant" since they're internal:
- Docstrings (`"""...for Executive Assistant"""`)
- Internal class names (`ExecutiveAssistantAgentState`)
- Console messages in `main.py` (developer-facing)
- Test files
- Documentation (discussions/, docs/)

**Rationale:** The package name is `executive_assistant` and that's fine. We only need to change what *users* see.

---

## Future Enhancements (Optional)

1. **Multi-language names** - `agent.name.localized` for different locales
2. **Emoji prefix** - Configurable emoji (🤖 → 🤖)
3. **Greeting customization** - Custom welcome messages per deployment

---

## Timeline (Actual)

| Phase | Estimated | Actual |
|-------|-----------|--------|
| Phase 1 | 5 min | 5 min |
| Phase 2 | 15-20 min | 20 min |
| Testing | 10 min | 10 min |
| **Total** | **30-35 min** | **35 min** |

---

## Example: Changing to "Nova"

1. Edit `config.yaml`:
   ```yaml
   agent:
     name: "Nova"
   ```

2. Restart the bot:
   ```bash
   uv run executive_assistant
   ```

3. Verify in Telegram:
   - `/start` → "👋 Hi! I'm Nova, an AI assistant..."
   - `/help` → "🤖 *Nova Help*"
   - Agent prompts → "You are Nova, a helpful AI assistant..."

4. Verify HTTP:
   - API docs title → "Nova API"
   - Root endpoint → `"name": "Nova API"`
