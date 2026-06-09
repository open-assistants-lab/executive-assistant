# MCP Hot-Reload Bug & Fix Design

Date: 2026-06-09

## Current State

MCP (Model Context Protocol) integration exists and works at AgentLoop creation time:

- `MCPManager` reads `.mcp.json`, starts server processes, routes tool calls
- `MCPToolBridge` converts MCP server tools into SDK `ToolDefinition` objects
- `runner.py:291-300` creates bridge and registers tools when building a new AgentLoop
- Meta-tools (`mcp_list`, `mcp_reload`, `mcp_tools`) are registered in `native_tools.py`

## Bug: mcp_reload Cannot Update Running Agent

**File:** `src/sdk/tools_core/mcp.py:72-86`
**Severity:** Critical

`_mcp_reload` calls `_loop_cache.get(user_id)` to find the running AgentLoop and re-register tools. However, `_loop_cache` keys are composite strings like:

```
user_id:workspace_id:model:keys_hash:caps_hash
```

The lookup with just `user_id` always returns `None`. The mcp servers restart, but the AgentLoop's tool registry is never updated. Changes to `.mcp.json` only take effect on the next conversation (when a new AgentLoop is created).

### Root Cause

Two separate issues:

1. **Cache key mismatch** — `_loop_cache` in `src/sdk/runner.py` uses composite keys, but `mcp_reload` only has `user_id`
2. **No access pattern** — `mcp_reload` needs the AgentLoop reference to call `register_tool()` / `unregister_tool()`, but there's no API to retrieve a running loop by user

### Fix Design

**Option A (Recommended) — AgentLoop Registry**

Add a `UserLoopRegistry` in `runner.py` that maps `user_id → AgentLoop`:

```python
# src/sdk/runner.py

_user_loops: dict[str, AgentLoop] = {}

def register_user_loop(user_id: str, loop: AgentLoop) -> None:
    _user_loops[user_id] = loop

def unregister_user_loop(user_id: str) -> None:
    _user_loops.pop(user_id, None)

def get_user_loop(user_id: str) -> AgentLoop | None:
    return _user_loops.get(user_id)
```

Set `register_user_loop(user_id, loop)` at `run_single()` / `run_stream()` entry (line 290 after loop creation), and `unregister_user_loop(user_id)` at exit (finally block).

In `_mcp_reload`, use `get_user_loop(user_id)` to obtain the loop and call `loop.register_tool(tool_def)` / `loop.unregister_tool(tool_name)`.

### Call flow (after fix)

```
User edits .mcp.json
  → Agent calls mcp_reload(user_id)
    → _mcp_reload(user_id)
      → loop = get_user_loop(user_id)
      → old_bridge = loop.tool_registry.get("mcp__*")
      → manager = MCPManager(config_path)
      → manager.restart_all()
      → new_bridge = MCPToolBridge(manager)
      → new_tools = new_bridge.get_tools()
      → for tool in new_tools: loop.register_tool(tool)
      → return {"restarted": True, "tools": len(new_tools)}
```

## Race Condition: MCPManager Idle Monitor

**File:** `src/sdk/tools_core/mcp_manager.py`
**Severity:** Major

The idle monitor timer calls `_stop_all()` without acquiring `self._lock`, while `get_tools()` and other methods access `self._connections` under the lock.

### Fix

```python
async def _stop_all(self) -> None:
    async with self._lock:
        for name, conn in self._connections.items():
            await conn.stop()
        self._connections.clear()
```

## Config Re-parsing on Every get_tools()

**File:** `src/sdk/tools_core/mcp_manager.py`
**Severity:** Major

`_config_changed()` loads and parses full JSON on every `get_tools()` call even when `mtime` is unchanged.

### Fix

```python
def _config_changed(self) -> bool:
    try:
        new_mtime = os.path.getmtime(self._config_path)
    except OSError:
        return False
    if new_mtime == self._config_mtime:
        return False  # early return before load + hash
    # ... rest of existing logic
    self._config_mtime = new_mtime
    return True
```

## Implementation Order

1. Add `UserLoopRegistry` to `src/sdk/runner.py` (register/unregister/get)
2. Wire registration in `run_single()` and `run_stream()` (around line 290-300)
3. Wire unregistration in cleanup/finally blocks
4. Refactor `_mcp_reload` in `src/sdk/tools_core/mcp.py` to use `get_user_loop()`
5. Add `_stop_all()` lock and `_config_changed()` early return in `mcp_manager.py`
6. Update tests

## Files to Change

| File | Changes |
|------|---------|
| `src/sdk/runner.py` | Add `_user_loops` dict, 3 helper functions, wire register/unregister |
| `src/sdk/tools_core/mcp.py` | Replace `_loop_cache.get()` with `get_user_loop()` |
| `src/sdk/tools_core/mcp_manager.py` | Lock in `_stop_all()`, early return in `_config_changed()` |
| `tests/sdk/test_mcp_bridge.py` | Add test for hot-reload via UserLoopRegistry |