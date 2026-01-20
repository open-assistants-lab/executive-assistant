# Tool Cleanup Plan - 2025-01-19

## Overview
Clean up deprecated and redundant tools in Executive Assistant to reduce complexity and tool count from 60+ to ~45 tools.

---

## Phase 1: Remove Deprecated/Redundant Tools [✅ COMPLETED]

### 1.1 Remove calculator tool [✅ DONE]
**Location**: `src/executive_assistant/tools/registry.py`
- [x] Delete calculator tool from `get_standard_tools()` (lines 201-228)
- [x] Remove "calculator" from docstring (line 250)

**Rationale**: Redundant - Python execution can handle math

### 1.2 Remove orchestrator tools (already archived) [✅ DONE]
**Location**: `src/executive_assistant/tools/orchestrator_tools.py`
- [x] Delete `src/executive_assistant/tools/orchestrator_tools.py`
- [x] Remove `get_orchestrator_tools()` from registry.py (lines 115-117)

**Rationale**: Already disabled/archived (`ORCHESTRATOR_ARCHIVED = True`)

### 1.3 Remove sqlite_helper tool (deprecated) [✅ DONE]
**Location**: `src/executive_assistant/skills/sqlite_helper.py`
- [x] Delete `src/executive_assistant/skills/sqlite_helper.py`
- [x] Remove `get_sqlite_helper_tools()` from registry.py (lines 120-123, 267)

**Rationale**: Deprecated - skills system replaces it

### 1.4 Remove task_state_tools (redundant with TodoListMiddleware) [✅ DONE]
**Locations**:
- `src/executive_assistant/tools/task_state_tools.py`
- `src/executive_assistant/agent/nodes.py`
- `src/executive_assistant/agent/state.py`

Tasks:
- [x] Delete `src/executive_assistant/tools/task_state_tools.py`
- [x] Remove `get_task_state_tools()` from registry.py (lines 92-95, 291)
- [x] Remove task_state handling from `nodes.py` (lines 247-255)
- [x] Remove `task_state` from `AgentState` in `state.py` (line 37)
- [x] Remove TaskState TypedDict from state.py

**Rationale**: TodoListMiddleware handles todo tracking; task_state infrastructure exists but tools are unused

---

## Phase 2: Merge Shared DB into Thread DB [DEFERRED]

**Status**: Moved to Phase 3 - will implement later

### 2.1 Add `scope` parameter to DB tools
- Modify all DB tools in `db_tools.py` to add: `scope: Literal["thread", "shared"] = "thread"`
- Implement logic for shared vs thread scope
- Update tool descriptions

### 2.2 Deprecate shared_db_tools.py
- Delete `src/executive_assistant/storage/shared_db_tools.py`
- Delete `src/executive_assistant/storage/shared_db_storage.py`
- Remove `get_shared_db_tools()` from registry.py

---

## Phase 3: Cleanup [✅ COMPLETED]

- [x] Remove unused imports from modified files
- [x] Update plan file with completion status
- [x] Update tests (removed TaskState tests, task_state references from test_agent.py)
- [ ] Update documentation (tool inventory, README)

---

## Files Deleted (3 files) [✅ DONE]
1. [x] `src/executive_assistant/tools/orchestrator_tools.py`
2. [x] `src/executive_assistant/tools/task_state_tools.py`
3. [x] `src/executive_assistant/skills/sqlite_helper.py`

## Files Modified (3 files) [✅ DONE]
1. [x] `src/executive_assistant/tools/registry.py` - Removed tool registrations (calculator, orchestrator, sqlite_helper, task_state)
2. [x] `src/executive_assistant/agent/nodes.py` - Removed task_state handling
3. [x] `src/executive_assistant/agent/state.py` - Removed task_state from AgentState and TaskState TypedDict

## Tool Count Reduction
- **Before**: 60+ tools
- **After Phase 1+3**: ~51 tools (removed ~9 tools)
- **After Phase 2**: ~45 tools (additional ~6 tools)
- **Total removed**: 15 tools

---

## Status Tracking
- [x] Phase 1.1 - Remove calculator ✅
- [x] Phase 1.2 - Remove orchestrator ✅
- [x] Phase 1.3 - Remove sqlite_helper ✅
- [x] Phase 1.4 - Remove task_state ✅
- [x] Phase 3 - Cleanup ✅
- [ ] Phase 2 - Merge shared DB (DEFERRED - moved to later)

## Summary
**Phases 1 & 3 completed successfully!**

**Tools removed**: 9 tools total
- 1 calculator tool
- 5 orchestrator tools (already archived, now fully removed)
- 1 sqlite_helper tool (deprecated)
- 4 task_state tools (redundant with TodoListMiddleware)
- 2 task_state-related functions (get_task_state_tools, orchestrator_tools)

**Files deleted**: 3
- orchestrator_tools.py
- task_state_tools.py
- sqlite_helper.py

**Files modified**: 4
- registry.py - Removed tool registrations
- nodes.py - Removed task_state handling
- state.py - Removed task_state from AgentState and TaskState TypedDict
- tests/test_agent.py - Removed TaskState tests and all task_state references

**Tests**: All 31 tests pass ✅

**Next**: Phase 2 (Merge Shared DB into Thread DB) is deferred for later implementation.
