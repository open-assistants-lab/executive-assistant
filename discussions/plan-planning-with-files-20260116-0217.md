# Plan: Thread-Scoped Planning Files (2026-01-16 02:17)

## Decision
Adopt the 3‑file planning pattern (task_plan/findings/progress) with **strict separation** from user files by storing under `data/users/{thread_id}/plan/`. Use it only for multi‑step tasks and keep it opt‑in to avoid noise.

## Goals
- Preserve long‑running task context across sessions without stuffing the prompt.
- Keep LLM‑generated planning artifacts separate from user files.
- Provide a lean, low‑friction workflow aligned with the Manus pattern.

## Storage Layout
```
data/users/{thread_id}/plan/
  task_plan.md
  findings.md
  progress.md
  archive/
```

## Templates
Use existing templates from:
- `discussions/planning-with-files/templates/task_plan.md`
- `discussions/planning-with-files/templates/findings.md`
- `discussions/planning-with-files/templates/progress.md`

## Plan Tools (verb‑first)
- `init_plan(task_title, force_new=False)`
  - Creates `plan/` and files from templates if missing
  - If current plan is completed, archive and start a new one
- `read_plan(which="task_plan")`
- `write_plan(which, content)`
- `update_plan(which, section, content)` (simple heading replacement)
- `clear_plan(confirm=False)` (remove current plan files, keep archive)
- `list_plans()` (current + archived)

## Agent Behavior (prompt-level only)
Add to `src/executive_assistant/agent/prompts.py`:
- Create plan first for complex tasks (3+ steps, research, multi‑turn work)
- Write findings to `findings.md` (2‑action rule)
- Log errors and test results to `progress.md`
- Re‑read `task_plan.md` before major decisions and before final response
- Skip the plan for simple Q&A or single‑file edits

## Plan Lifecycle
- **Completed plan** detection:
  - `Status: complete`, or all phases marked complete
- **When completed**:
  - Move to `plan/archive/plan-YYYYMMDD-HHMM.md` (or copy + clear)
  - Start a fresh plan on next `init_plan`

## Access Separation
- Plan files are **not** visible via user file tools (`list_files`, `glob_files`, etc.)
- Only plan tools access `data/users/{thread_id}/plan/`
- Optional `export_plan` tool if user wants a plan copied into their files

## Implementation Steps
1. Add `get_thread_plan_path()` in `src/executive_assistant/config/settings.py`.
2. Create `src/executive_assistant/storage/plan_storage.py` for plan sandbox utilities.
3. Add plan tools in `src/executive_assistant/tools/plan_tools.py` and register in `src/executive_assistant/tools/registry.py`.
4. Update system prompt with the planning rules in `src/executive_assistant/agent/prompts.py`.
5. Add docs to `README.md` describing `/plan` usage and separation behavior.

## Risks / Mitigations
- **Overhead for small tasks** → keep usage opt‑in + only for complex tasks.
- **Plan noise in prompt** → read plan only at decision points.
- **User confusion about hidden files** → document clearly; provide `export_plan` if needed.

## Acceptance Criteria
- Plan files are created under `data/users/{thread_id}/plan/`.
- User files remain unchanged and separate.
- Agent can read/update plan files without exposing them via standard file tools.
- Completed plan files can be archived and replaced cleanly.

---

## Implementation Status (2026-01-16)

### Implemented
- **Custom middleware**: `src/executive_assistant/agent/planning_middleware.py`
  - Uses `abefore_agent` to auto-init plans on complex tasks.
  - Uses `awrap_tool_call` to log findings/errors after tool calls.
  - Skips plan tools (`init_plan`, `read_plan`, etc.) to avoid recursion.
- **Wiring**: `src/executive_assistant/agent/langchain_agent.py`
  - Middleware is injected before summarization when `MW_PLAN_FILES_ENABLED=true`.
- **Settings**: `src/executive_assistant/config/settings.py` + `.env.example`
  - `MW_PLAN_FILES_ENABLED`, `MW_PLAN_AUTO_INIT`, thresholds + max chars.
- **Tool name alignment**:
  - Research tool list updated to actual tool names: `search_web`, `search_kb`, `describe_kb`, `kb_list`, `grep_files`, `glob_files`, `read_file`, `list_files`.

### Behavior Summary
- Auto-inits plan when the user message looks complex (length/keyword heuristics) or starts with `/plan`.
- Logs **every 2 research tools** to `findings.md` (configurable).
- Logs tool errors to `progress.md` error table.
- Works in **LangChain runtime** (async). Sync hooks (`before_agent`/`wrap_tool_call`) are not implemented.

### Known Gaps
- No sync hook fallbacks; only `abefore_agent`/`awrap_tool_call` are implemented.
- Not wired for custom graph runtime.
- Findings/logging is heuristic-based; may require tuning per channel.
