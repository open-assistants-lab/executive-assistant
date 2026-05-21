# Hook Middleware System — Design Spec

**Date:** 2026-05-03
**Status:** Draft

---

## Context

The codebase has a custom SDK with an in-process middleware system. Currently 5 hook points
(`before_agent`, `after_agent`, `before_model`, `after_model`, `wrap_tool_call`) served by 4
concrete middlewares (Memory, Summarization, Progress, Instruction). Claude Code has a 28-event
external process hook system with matchers, `if` conditions, and 5 handler types (command, HTTP,
MCP tool, prompt, agent).

The question: should we implement a Claude Code-style hook system, extend the existing middleware,
or do something else to give users extensibility?

---

## Current Architecture

### Middleware ABC (`src/sdk/middleware.py`)

```
before_agent → before_model → [LLM call] → after_model → [tool exec] → (repeat) → after_agent
                                                                                    ↑
                                                                           wrap_tool_call
```

- 70-line ABC, 5 hook points, sync + async variants
- Returns `dict[str, Any] | None` — state updates applied via `AgentState.update()`
- `_run_hooks(hook_name, state)` iterates `self.middlewares`, calls via `getattr`, catches errors
- No filtering — every middleware runs at every hook
- Constructor-injected into AgentLoop, fixed per user session

### Concrete Middlewares

| Middleware | Hooks Used | Purpose |
|---|---|---|
| MemoryMiddleware | `before_agent`, `after_agent` | Inject memory context, extract patterns |
| SummarizationMiddleware | `abefore_model` | Check token count, generate summaries |
| ProgressMiddleware | `abefore_model` | Update work_queue progress, doom loop detection |
| InstructionMiddleware | `abefore_model` | Check cancel/instructions before LLM call |

### AgentLoop Dispatch (`src/sdk/loop.py`)

```python
async def _run_hooks(self, hook_name: str, state: AgentState) -> None:
    for mw in self.middlewares:
        method = getattr(mw, hook_name, None)
        if method is None:
            continue
        try:
            updates = await method(state)
            self._apply_updates(state, updates)
        except TaskCancelledError:
            raise
        except Exception:
            logger.warning(f"{hook_name} error in {mw.name}", exc_info=True)
```

`wrap_tool_call` is called separately (not via `_run_hooks`) in 4 places: `_execute_single_tool`,
`_execute_tool_batch`, `_execute_single_tool_streaming`, `_execute_tool_batch_streaming`.

### Runner Assembly (`src/sdk/runner.py`)

```python
middlewares = []
if summary_enabled:
    middlewares.append(SummarizationMiddleware(...))
middlewares.append(MemoryMiddleware(...))
loop = AgentLoop(middlewares=middlewares, ...)
```

User middleware is not currently supported. All middlewares are hard-coded imports.

---

## Proposed Design: Extended Middleware + User Discovery

### Hook Point Additions

```python
class Middleware(ABC):
    # === Existing ===
    before_agent / abefore_agent      # Once per run
    after_agent  / aafter_agent       # Once per run
    before_model / abefore_model      # Before each LLM call
    after_model  / aafter_model       # After each LLM, before tool execution
    wrap_tool_call(tool_name, args)   # Per tool, can modify args

    # === New ===
    matcher: str | None = None

    async def abefore_tool(self, state, tool_name: str, tool_input: dict) -> dict | None: ...
    async def aafter_tool(self, state, tool_name: str, tool_call_id: str, result: ToolResult) -> dict | None: ...
    async def aon_user_prompt(self, state, prompt: str) -> dict | None: ...
    async def aon_interrupt(self, state, tool_call: ToolCall) -> str | None: ...
    async def aon_error(self, state, error: Exception, phase: str) -> dict | None: ...

    # Note: abefore_summarize / aafter_summarize were proposed but removed after
    # peer review — SummarizationMiddleware._on_summarize callback is sufficient.
```

### Matcher Filtering

`matcher` is a pipe-delimited list of tool names or a regex pattern. Evaluated in `_run_hooks`:

```python
def _matches(pattern: str, tool_name: str) -> bool:
    """Check if tool_name matches a pipe-delimited glob or regex pattern."""
    if "|" in pattern:
        return any(_matches(p.strip(), tool_name) for p in pattern.split("|"))
    if pattern.startswith("re:"):
        import re
        return bool(re.search(pattern[3:], tool_name))
    import fnmatch
    return fnmatch.fnmatch(tool_name, pattern)


async def _run_hooks(self, hook_name: str, state: AgentState, tool_name: str | None = None) -> None:
    for mw in self.middlewares:
        method = getattr(mw, hook_name, None)
        if method is None:
            continue
        if mw.matcher and tool_name:
            if not _matches(mw.matcher, tool_name):
                continue
        updates = await method(state)
        self._apply_updates(state, updates)
```

When `hook_name` maps to a per-tool event (`abefore_tool`, `aafter_tool`), passes `tool_name`.
When it maps to a session-level event (`before_agent`), passes `None` → matcher is ignored.

### User Middleware Discovery

```
~/.ea/middleware/       # Per-user, cross-project
.ea/middleware/          # Per-project
```

At init time, `UserMiddlewareLoader` scans these directories for `.py` files, imports them,
finds `Middleware` subclasses, and instantiates them. Added to the middleware list in `runner.py`
alongside built-in middlewares.

Configuration:
```yaml
# config.yaml
user_middleware:
  paths: ["~/.ea/middleware", ".ea/middleware"]
  disabled: []  # class names to skip
```

### Injection Points in AgentLoop

| Hook | Where in `run()` | Where in `run_stream()` |
|---|---|---|
| `aon_user_prompt` | `_run_impl` before `abefore_agent` call | `run_stream` before `abefore_agent` call |
| `abefore_tool` | At start of `_execute_single_tool`, after `wrap_tool_call` loop | Same in `_execute_single_tool_streaming` |
| `aafter_tool` | After tool execution returns, before `Message.tool_result` is added to state | Same in streaming variants |
| `aon_interrupt` | In the interrupt classification block, before creating interrupt `ToolResult` messages | Same location in `_run_stream_inner` |
| `aon_error` | In `except ProviderContextOverflowError` and `except Exception` handlers in `_run_impl` | Same handler locations in `_run_stream_inner` |

**Note:** These are structural locations, not line numbers. Line numbers change as the codebase evolves.


---

## Claude Code Hook Event Coverage

| Claude Code Event | Mapped To |
|---|---|
| SessionStart | Existing `before_agent` |
| SessionEnd | Existing `after_agent` |
| UserPromptSubmit | New `on_user_prompt` |
| UserPromptExpansion | N/A (no slash-command expansion) |
| PreToolUse | New `before_tool` + existing `wrap_tool_call` |
| PostToolUse | New `after_tool` |
| PostToolUseFailure | New `on_error` (phase="tool") |
| PostToolBatch | Existing `after_model` |
| PermissionRequest / PermissionDenied | New `on_interrupt` |
| Stop | Existing `after_agent` |
| StopFailure | New `on_error` (phase="llm") |
| SubagentStart/Stop | Existing `ProgressMiddleware` / `InstructionMiddleware` |
| Notification, FileChanged, ConfigChange, CwdChanged | N/A (OS-level, not agent-level) |
| Setup, WorktreeCreate/Remove | N/A (product-specific) |

**Coverage:** 13 of 27 events map to existing or new middleware hooks. PreCompact/PostCompact are
excluded — `SummarizationMiddleware._on_summarize` callback covers that use case. The remaining 12
are either OS-level (Notification, FileChanged), product-specific (Worktree), or don't apply (no slash commands).

---

## Performance Model

### Current overhead (per iteration)

For each AgentLoop iteration with N middlewares:
- `_run_hooks("abefore_model")`: N `getattr` + N async calls
- `wrap_tool_call` (per tool): N sync calls

With the current 2 middlewares (Memory + Summarization): ~4 function calls per iteration.
Memory's `before_agent` runs once. Summarization's `abefore_model` runs per LLM call.

Current cost: negligible (<1ms per iteration).

### Proposed overhead

Adding up to 5 new hook points with M user middlewares:
- `abefore_tool` + `aafter_tool`: 2 × M async calls per tool execution
- `aon_user_prompt`: M async calls once per run
- `aon_interrupt`: M async calls per interrupt (rare)
- `aon_error`: M async calls per error (rare)

Worst case: 10 user middlewares, 20 tool calls per run → 400 extra async function calls.
At ~50μs per no-op async call: ~20ms total across a full run.

Realistic case: 1-3 user middlewares, most with no-op defaults (return None): <2ms total.

### Latency comparison with Claude Code hooks

| Operation | In-process middleware | External shell hook |
|---|---|---|
| Dispatch | ~50μs (Python function call) | ~5-50ms (fork+exec+stdin/stdout) |
| Per 20-tool run | ~2ms | ~100ms-1s |
| Startup cost | Module import (~10ms) | Process launch (~5ms each) |

### Matcher overhead

`_matches()` is a string/regex check on `tool_name`. Regex compilation cached per middleware
(on first use). String match: ~1μs. Regex match: ~5-10μs (compiled once).

---

## Pros and Cons

### Pros

1. **Zero process overhead** — no fork/exec, no subprocesses, no JSON serialization round-trips
2. **Direct state access** — middleware has full `AgentState`, can add/remove/modify messages, access tool registry
3. **Type safety** — Python type hints, mypy, IDE autocomplete
4. **Testability** — standard `pytest` with async fixtures, no mocking of subprocess I/O
5. **Consistent error handling** — same exception model as existing code, caught by `_run_hooks`
6. **Gradual adoption** — ship 7 new hook stubs with default no-ops, zero impact until users override them
7. **Minimal code** — ~30 lines added to `Middleware` ABC, ~50 lines of injection calls in `loop.py`, ~80 lines for `UserMiddlewareLoader`
8. **Matcher filtering** — prevents unnecessary calls, matches Claude Code's filtering model
9. **User extensibility** — users place `.py` files in a directory, no JSON config, no shell scripting
10. **Backward compatible** — all new hooks have default no-op implementations, existing middlewares unchanged

### Cons

1. **Python-only** — users must write Python, cannot use bash/Node.js/Go
2. **Same-process risk** — a buggy user middleware can crash the agent loop (mitigated by `_run_hooks` try/except)
3. **No external process isolation** — cannot sandbox user code from the main process
4. **Discovery complexity** — file-based discovery requires careful import handling, potential for import conflicts
5. **No HTTP/MCP hook types** — no network isolation, no MCP tool chaining in hooks
6. **No `if` condition syntax** — Claude Code's `if: "Bash(rm *)"` is more expressive than regex matchers
7. **Not declarative** — users write code, not JSON config; harder for non-developers
8. **Matcher regex overhead** — every hook dispatch checks matcher, even when no matcher is set (mitigated: `None` check is a single `is None` comparison)

### Neutral

1. **Two extension mechanisms** (middleware + guardrails + handoffs + tracing) — but they serve different purposes
2. **Hook naming divergence** — our names (`before_tool`) don't match Claude Code's (`PreToolUse`), which could confuse users familiar with Claude Code

---

## Open Questions

1. Should `matcher` support Claude Code's `if` syntax (`Bash(rm *)`) as well as tool-name patterns?
2. Should user middlewares be hot-reloadable (watch directory for changes)?
3. Should there be a `priority` ordering mechanism (user middlewares before/after built-in)?
4. Should `wrap_tool_call` be consolidated into `abefore_tool` (deprecation path)?
5. Should we support `@hook` decorator for function-based hooks (not just class-based middleware)?

---

## Deep Re-Evaluation: Code Trace Findings

A line-by-line trace of `loop.py` revealed several issues that affect the design.

### Finding 1: `aafter_model` is never called in `run_stream()`

`run()` calls `_run_hooks("aafter_model", state)` at line 634, after `state.add_message(response)`.
`_run_stream_inner()` **never** calls `aafter_model`. After the streaming LLM call completes (line
864 via `state.add_message(assistant_msg)`), execution jumps directly to the tool dedup/classification
block (line 866). The `after_model` hook point is simply absent in the streaming path.

**Impact:** Adding any hook that fires after the LLM returns would require adding the call in
`_run_stream_inner()` first — a bug fix in its own right.

### Finding 2: `wrap_tool_call` has zero error handling

In all 4 tool execution methods (lines 276, 322, 385, 433), `wrap_tool_call` is called via:

```python
for mw in self.middlewares:
    tc.arguments = mw.wrap_tool_call(tc.name, tc.arguments)
```

No try/except. A buggy user middleware that raises in `wrap_tool_call` **crashes the entire loop**.
Contrast with `_run_hooks` (line 490) which catches all exceptions and logs. Changing
`wrap_tool_call` to go through `_run_hooks`-style dispatch would fix this pre-existing bug.

### Finding 3: Four duplicate tool-execution code paths

```
_execute_single_tool            (line 258) — non-streaming, sequential
_execute_tool_batch              (line 304) — non-streaming, parallel
_execute_single_tool_streaming   (line 366) — streaming, sequential
_execute_tool_batch_streaming    (line 418) — streaming, parallel
```

Adding `before_tool`/`after_tool` calls means touching all 4 methods. That's 8 injection points
for just two hook types. This is fragile and a maintenance risk. Ideally, the tool execution
lifecycle (guardrails → hooks → execute → hooks → guardrails) should be a single reusable function.

### Finding 4: Overlapping interception mechanisms

For a single tool call, the current pipeline has **five** interception points:

```
input guardrail → wrap_tool_call → execute → output guardrail → add to state
```

Adding `before_tool` + `after_tool` would make it **seven**:

```
input guardrail → before_tool → wrap_tool_call → execute → after_tool → output guardrail → add to state
```

This is too many. The proposed `before_tool` and `wrap_tool_call` serve the same purpose (pre-execution
interception). The proposal should **consolidate** `wrap_tool_call` into `before_tool` (with a
deprecation path) to keep the pipeline at 5.

### Finding 5: `after_tool` cannot modify results through `_run_hooks`

The current `_run_hooks` applies returned dicts to `state.update()`. For `after_tool`, the hook
needs to modify the *result* (a `ToolResult`) before it becomes a `Message.tool_result()` in state.
Returning state updates won't work — the result needs direct mutation.

**Solution:** `after_tool` needs a different dispatch convention. It receives the `ToolResult`,
can return a modified `ToolResult`, and `None` means "no change":

```python
async def _run_tool_hook_after(hook_name, state, tc, result):
    for mw in self.middlewares:
        method = getattr(mw, hook_name, None)
        if method is None: continue
        if mw.matcher and not _matches(mw.matcher, tc.name): continue
        try:
            new_result = await method(state, tc.name, tc.id, result)
            if new_result is not None:
                result = new_result
        except Exception:
            logger.warning(...)
    return result
```

This diverges from `_run_hooks`'s state-update return convention. The hook ABC needs to document
this clearly: `before_*` hooks return state updates, `wrap_tool_call` returns modified args, 
`after_tool` returns a modified result.

### Finding 6: Parallel execution complicates per-tool hooks

In `_execute_tool_batch`, tools run concurrently via `asyncio.gather`. Each tool's `_run_one`
closure currently calls `wrap_tool_call` independently. For `before_tool`/`after_tool` to work
correctly in parallel mode, each closure must independently call the hooks — which means the
hook dispatch must be re-entrant (it is, since `_run_hooks` just iterates a list).

No code issue here, but it means batch and sequential paths can't share a unified tool-execution
method without adding concurrency concerns.

### Finding 7: interrupt hooks fire inside the main loop, not in tool methods

In `run()` (line 646-665) and `_run_stream_inner()` (line 894-922), interrupt handling happens
*during* the classification phase in the main loop body — not inside the tool execution methods.
This means `on_interrupt` hooks would need to be called from two places (run and stream), not
from the four tool methods. This is actually cleaner — only 2 injection points for interrupts.

---

## Revised Performance Analysis

### Benchmarks from code inspection

| Metric | Current (2 middlewares) | With 5 hook points + 3 user mw |
|---|---|---|
| `wrap_tool_call` calls per tool | 2 sync calls | 0 (consolidated into `abefore_tool`) |
| Per-tool overhead | ~5μs | ~150μs (2 async calls with matcher check × 3 middlewares) |
| Full run (20 tools, 5 iterations) | <1ms | ~3ms |
| Streaming latency impact | 0 | ~50μs per tool (hidden behind LLM latency) |

**Key insight:** The dominant cost is the LLM API call (~500ms-5s), not middleware dispatch.
Adding 150μs per tool execution is a 0.003% overhead relative to a 5-second LLM call. The
performance argument against adding hooks is essentially null.

### Startup impact

Loading 3 user middleware `.py` files via `importlib`: ~10-20ms (one-time, at AgentLoop creation).
Negligible compared to provider creation (~100ms) and MCP tool discovery (~500ms).

---

## Revised Pros and Cons

### Updated Pros

1. **Zero process overhead** — retains in-process dispatch, no fork/exec
2. **Direct state access** — middleware has full `AgentState`, can inject/remove messages
3. **Type safety** — Python hints, mypy, IDE support
4. **Testability** — `pytest` with async fixtures, no subprocess mocking
5. **Existing patterns** — extends the 70-line ABC users already understand
6. **Matcher filtering** — prevents unnecessary calls, same model as Claude Code
7. **User extensibility** — `.py` files in a directory, `importlib` discovery
8. **Performance is not a concern** — 150μs per tool vs 5-second LLM calls
9. **Backward compatible** — default no-ops, existing middlewares unchanged

### Updated Cons (with mitigations)

| Risk | Severity | Mitigation |
|---|---|---|
| `wrap_tool_call` has no error handling | **HIGH** (pre-existing bug) | Move to `_run_hooks` dispatch with try/except |
| `aafter_model` missing in stream path | **MEDIUM** (pre-existing bug) | Add call in `_run_stream_inner` |
| 4 duplicate tool-execution paths | **MEDIUM** (maintenance) | Consolidate to unified method in follow-up |
| Overlapping `before_tool` + `wrap_tool_call` | **MEDIUM** (confusion) | Consolidate `wrap_tool_call` into `before_tool` |
| Discovery complexity | **LOW** (one-time) | `importlib.import_module`, cache results |
| Python-only | **MEDIUM** (fundamental) | Accept as trade-off; docs can recommend `subprocess.run()` for external calls |
| Same-process risk | **LOW** | All hooks caught by `_run_hooks` try/except |
| Not declarative | **LOW** | Python is more expressive than JSON config |

### Implementation Cost

| Component | Lines | Complexity | Risk |
|---|---|---|---|
| ABC hook stubs (5 new methods) | ~30 | Trivial | None |
| `_run_hooks` matcher support | ~15 | Low | None |
| `before_tool` injection (4 tool methods) | ~20 | Medium | Merge conflicts |
| `after_tool` injection (4 tool methods) | ~30 | Medium | Needs new dispatch pattern |
| `on_user_prompt` injection | ~4 | Trivial | None |
| `on_interrupt` injection | ~8 | Low | None |
| `on_error` injection | ~6 | Low | None |
| Bug fix: `aafter_model` in stream | ~2 | Trivial | None |
| Bug fix: `wrap_tool_call` error handling | Move to `_run_hooks` | Low | None |
| User middleware discovery | ~80 | Medium | Import edge cases |
| Tests | ~200 | — | — |
| **Total** | **~380** | — | — |

---

## Final Recommendation

**Implement extended middleware with user discovery. Do not implement external process hooks.**

The deep code trace confirms this is the right approach:

1. The performance argument against hooks is a red herring — 150μs per tool is invisible against
   5-second LLM calls.
2. The real architecture concerns are the pre-existing bugs (`aafter_model` missing in stream,
   `wrap_tool_call` with no error handling) and the 4 duplicate tool-execution code paths.
   Adding hooks forces us to fix these — which is a net positive.
3. The `before_tool` should consolidate `wrap_tool_call` (deprecate the old method). This keeps
   the pipeline at 5 interception points instead of ballooning to 7.
4. The `after_tool` return convention must differ from `_run_hooks` (returns modified `ToolResult`,
   not state updates). This is a minor API inconsistency but the right semantics.
5. User discovery via `importlib` + directory scanning is straightforward — 80 lines of code.
6. For users who absolutely need shell scripting, they can call `subprocess.run()` inside a
   Python middleware. This gives them the flexibility without us building a shell hook subsystem.

### Recommended Implementation Order

1. Fix pre-existing bugs (error handling + missing stream hook) — prerequisite
2. Add `on_user_prompt`, `before_tool`, `after_tool` hooks with matcher support — core value
3. Consolidate `wrap_tool_call` into `before_tool` — simplification
4. Add `on_interrupt`, `on_error` — completes coverage
5. Implement user middleware discovery — unlocks extensibility
6. Write user-facing docs with examples — adoption

> **Note:** `abefore_summarize` / `aafter_summarize` were proposed but removed after peer review (2026-05-21).
> `SummarizationMiddleware._on_summarize` callback is sufficient — no ABC hooks needed.

---

## Peer Review Verdict (2026-05-21)

**Status: Design sound, ready for implementation. Pre-existing bug findings are the most valuable output.**

| # | Issue | Severity | Status |
|---|-------|----------|--------|
| 1 | `aafter_model` missing in streaming path — line 723 | Pre-existing bug | Confirmed — fix is prerequisite |
| 2 | `wrap_tool_call` has no error handling in all 4 tool methods | Pre-existing bug | Confirmed — move to `_run_hooks` dispatch |
| 3 | `_run_hooks` signature change impacts 8 call sites | Migration cost | Low — default `tool_name=None` is backward compat |
| 4 | `after_tool` needs separate dispatch from `_run_hooks` | API design | Accepted — documented in Finding 5 |
| 5 | `wrap_tool_call` → `before_tool` deprecation path underspecified | Design gap | Needs decision on alias vs migration |
| 6 | No security sandbox for user middleware discovery | Risk | Documented but not mitigated — decide per deployment model |
| 7 | `_matches()` function implementation undefined | Design gap | Needs implementation — recommend `fnmatch`-style glob first |

**Simplification:** `abefore_summarize` / `aafter_summarize` removed from the proposal (5 hooks instead of 7).
SummarizationMiddleware already has `_on_summarize` callback for post-summarization behavior. No existing
middleware needs to hook into summarization. If needed, users can subclass `SummarizationMiddleware`.

---

## Decision Log

- **2026-05-03:** Draft created. Exploring extending Middleware ABC + user discovery vs Claude Code external hooks.
- **2026-05-03:** Deep re-evaluation completed. Code trace found 2 pre-existing bugs, 4 duplicate tool-execution paths, overlapping `wrap_tool_call`/`before_tool` concerns. Recommendation confirmed: extend Middleware ABC, no external process hooks. Performance concern dismissed (150μs vs 5s LLM latency).
- **2026-05-21:** Peer review completed. `abefore_summarize` / `aafter_summarize` removed (5 hooks remain). 2 pre-existing bugs confirmed. 3 design gaps documented. Security risk noted but not mitigated.
