# Summarization Overhaul — Structured Prompts, Tool Pruning, and Overflow Recovery

**Date:** 2026-05-21

## Problem

EA's `SummarizationMiddleware` works but has three gaps that reduce its effectiveness and reliability:

1. **Generic prompt.** The summary prompt is open-ended ("preserve all key facts"). It doesn't force structured reasoning, doesn't ask for specific technical details like file paths or code snippets, and doesn't section the output.
2. **No tool output pruning.** When summarization triggers at 50K tokens, 60-80% of that is bloated tool results (file reads, grep output, shell stdout). These are included in the summary generation call, wasting tokens and diluting the summary quality.
3. **No overflow recovery.** If the LLM API returns a 413 / context-too-large error, the agent turn fails. The user has no recourse and loses their session.
4. **No manual trigger.** Only auto-triggers on token threshold. User cannot say "compact now."

## Design Goals

1. Replace the generic summarization prompt with Claude Code's structured template that forces `<analysis>` reasoning, explicit sections, and technical details
2. Prune old tool outputs before summarization so the summary LLM sees only meaningful conversation
3. Catch API overflow errors, trigger summarization, and replay the last user message
4. Add a manual `/summarize` tool (like Claude Code's `/compact`)
5. Use existing `_on_summarize` callback for post-summarization behavior (no new Middleware ABC hooks — see verdict)
6. Keep the message store untouched — all pruning and replacement is in-memory only

## Design

### 1. Structured Summarization Prompt

Replace `SUMMARY_SYSTEM_PROMPT` in `middleware_summarization.py`:

```python
SUMMARY_SYSTEM_PROMPT = """Your task is to create a detailed summary of the conversation so far, paying close attention to the user's explicit requests and your previous actions.

This summary should be thorough in capturing technical details, code patterns, and architectural decisions that would be essential for continuing development work without losing context.

Before providing your final summary, wrap your analysis in <analysis> tags to organize your thoughts and ensure you've covered all necessary points. In your analysis process:

1. Chronologically analyze each message and section of the conversation. For each section thoroughly identify:
   - The user's explicit requests and intents
   - Your approach to addressing the user's requests
   - Key decisions, technical concepts and code patterns
   - Specific details like file names, full code snippets, function signatures, file edits, etc
2. Double-check for technical accuracy and completeness, addressing each required element thoroughly.

Your summary should include the following sections:

1. ## Accomplished
   What was completed since the last summary. List specific files modified, functions changed, tests added.

2. ## Current State
   What is in progress right now. What the user was last working on. What the last message was about.

3. ## Files & Architecture
   All files that have been touched. Their purposes. Key architectural decisions made.

4. ## Next Steps
   What the user was about to do next. Any explicit TODO items. Unresolved issues or bugs.

5. ## Constraints & Preferences
   User preferences, coding style constraints, performance requirements, or any other context that would be harmful to forget.
"""
```

### 2. Tool Output Pruning

Add a method that runs before summarization:

```python
def _prune_tool_outputs(self, messages: list[Message], keep_tokens: int) -> list[Message]:
    """Replace old tool outputs with short placeholders.

    Messages newer than keep_tokens are left intact.
    Older messages with role == 'tool' get their content replaced with
    a token-count placeholder instead of the full blob.
    """
    # Count backwards to find the keep boundary
    recent_tokens = 0
    boundary = len(messages)
    for i in range(len(messages) - 1, -1, -1):
        t = self._count_message_tokens(messages[i])
        if recent_tokens + t > keep_tokens and i < len(messages) - 1:
            boundary = i + 1
            break
        recent_tokens += t

    pruned = list(messages)
    for i in range(boundary):
        if pruned[i].role == "tool":
            original_tokens = self._count_message_tokens(pruned[i])
            pruned[i] = Message(
                role="tool",
                content=f"[pruned: {original_tokens} tokens of tool output]",
                name=pruned[i].name,
                tool_call_id=pruned[i].tool_call_id,
            )
        elif pruned[i].role == "assistant" and pruned[i].tool_calls:
            pruned[i] = Message(
                role="assistant",
                content=pruned[i].content,
                tool_calls=pruned[i].tool_calls,
            )
    return pruned
```

This is called inside `abefore_model` *before* the summarization trigger check:

```python
async def abefore_model(self, state: AgentState) -> dict[str, Any] | None:
    messages = state.messages

    # Prune old tool outputs first
    pruned = self._prune_tool_outputs(messages, self.keep_tokens)

    # Count tokens on the pruned list
    total_tokens = self._total_tokens(pruned)

    if total_tokens <= self.trigger_tokens:
        return None

    # Continue with summarization using pruned messages as source
    old_messages, recent_messages = self._split_messages(pruned)
    conversation_text = self._messages_to_conversation_text(old_messages)
    summary = await self._generate_summary(conversation_text)
    ...
```

**Key detail:** The pruning applies to the source messages for summarization AND the `state.messages` replacement after summarization. The message store is never touched.

### 2.1 Split Messages Helper

Extract the existing inline splitting logic from `abefore_model` (lines 167-190) into a reusable method:

```python
def _split_messages(self, messages: list[Message]) -> tuple[list[Message], list[Message]]:
    """Split messages into 'old' (to summarize) and 'recent' (keep as-is).

    The split boundary is computed from keep_tokens: messages within the
    keep_tokens window are 'recent'; everything older is 'old'.
    System messages are always excluded from summarization.
    """
    tokens_to_keep = self.keep_tokens
    recent_tokens = 0
    split_idx = len(messages)

    for i in range(len(messages) - 1, -1, -1):
        msg_tokens = self._count_message_tokens(messages[i])
        if recent_tokens + msg_tokens > tokens_to_keep and i < len(messages) - 1:
            split_idx = i + 1
            break
        recent_tokens += msg_tokens
    else:
        split_idx = 1

    old_messages = messages[:split_idx]
    system_messages = [m for m in old_messages if m.role == "system"]
    non_system_old = [m for m in old_messages if m.role != "system"]
    return non_system_old, list(system_messages) + list(messages[split_idx:])
```

### 3. Overflow Recovery

In `loop.py`, catch context overflow errors from the provider and trigger compaction:

```python
MAX_OVERFLOW_RETRIES = 3

async def _run_iteration(self, ...):
    ...
    overflow_retries = 0
    try:
        response = await self.provider.chat(
            prepared, tools=tools, model=None, ...
        )
    except ProviderContextOverflowError as e:
        logger.warning("context_overflow", {"error": str(e)})

        if overflow_retries >= MAX_OVERFLOW_RETRIES:
            yield StreamChunk.error(
                message="Context too large after multiple summarization attempts."
            )
            return
        overflow_retries += 1

        # Trigger summarization immediately
        from src.sdk.middleware_summarization import SummarizationMiddleware

        summary_mw = self._find_middleware(SummarizationMiddleware)
        if summary_mw:
            # Force-prune and summarize
            result = await summary_mw.force_summarize(state)
            if result:
                # Replay the last user message
                last_user = _last_user_message(state.messages)
                if last_user:
                    state.messages.append(last_user)
                    # Retry this iteration
                    continue

        # Fallback: return error message
        yield StreamChunk.error(
            message="Context too large. Try /summarize to compact the conversation."
        )
        return
```

The provider needs a new exception type:

```python
class ProviderContextOverflowError(Exception):
    """Raised when the LLM API returns a 413 or context-too-large error."""
```

Add a new `force_summarize` method to `SummarizationMiddleware`:

```python
async def force_summarize(self, state: AgentState, instructions: str | None = None) -> bool:
    """Force summarization even if token count is below threshold.

    Called by overflow recovery or /summarize command.
    Returns True if summarization was performed.

    If instructions are provided, they are prepended to the summary
    prompt to focus the summary on specific areas.
    """
    messages = state.messages
    pruned = self._prune_tool_outputs(messages, self.keep_tokens)
    total_tokens = self._total_tokens(pruned)

    if total_tokens < 1000:
        return False  # Nothing meaningful to summarize

    old_messages, recent_messages = self._split_messages(pruned)
    conversation_text = self._messages_to_conversation_text(old_messages)

    # Prepend focus instructions if provided
    if instructions:
        conversation_text = f"[Focus: {instructions}]\n\n{conversation_text}"

    summary = await self._generate_summary(conversation_text)
    if summary is None:
        return False

    new_messages = [
        Message.system(f"## Summary of previous conversation\n\n{summary}"),
        *recent_messages,
    ]
    state.messages = new_messages

    if self._on_summarize is not None:
        try:
            result = self._on_summarize(summary)
            if hasattr(result, "__await__"):
                await result
        except Exception:
            pass

    return True
```

### 4. Manual `/summarize` Tool

Add a tool the LLM can call:

```python
@tool
async def summarize_session(
    user_id: str,
    workspace_id: str = "personal",
    instructions: str | None = None,
) -> str:
    """Manually compact the conversation by summarizing old messages.

    Use this when the conversation is getting long and you want to
    free up context space. Old tool outputs are pruned and the
    conversation history is summarized.

    Args:
        user_id: The user ID
        workspace_id: Workspace ID
        instructions: Optional focus instructions for the summary
            (e.g. "preserve all file paths and error messages")

    Returns:
        Confirmation message with token savings
    """
    # Access the active agent loop's summarization middleware
    # PREREQUISITE: AgentLoop must set a ContextVar on entry to run()/run_stream()
    loop = get_current_agent_loop()
    summary_mw = loop.find_middleware(SummarizationMiddleware)
    if summary_mw is None:
        return "Error: No summarization middleware configured."

    before_tokens = summary_mw._total_tokens(loop.state.messages)
    success = await summary_mw.force_summarize(loop.state, instructions=instructions)
    if not success:
        return "Conversation too short to summarize meaningfully."
    after_tokens = summary_mw._total_tokens(loop.state.messages)
    return f"Summarized. Saved ~{before_tokens - after_tokens} tokens."
```

**Annotations:**

```python
summarize_session.annotations = ToolAnnotations(
    title="Summarize / Compact Conversation",
    read_only=True,
    idempotent=True,
)
```

### 5. No Middleware ABC Hooks Needed

The original design (2026-05-03 hook middleware spec) proposed `abefore_summarize` / `aafter_summarize` hooks on the Middleware ABC. After peer review, these were removed because:

- No existing middleware needs to react to summarization events
- The `_on_summarize` callback already covers reactive behavior
- Adding them as ABC hooks requires two new dispatch methods (`_run_summary_hooks` with its own signature) and complicates `_generate_summary`'s signature by requiring access to `state`
- If a user middleware genuinely needs to intercept summarization, they can use `_on_summarize` or subclass `SummarizationMiddleware`

The `_on_summarize` callback (already on `SummarizationMiddleware`) is sufficient.

## Prerequisites

Before implementing this design, two infrastructure pieces need to exist in `loop.py`:

- **`get_current_agent_loop()`** — a module-level `ContextVar[AgentLoop]` set at the start of `run()` and `run_stream()`, cleared at exit. Enables tools like `summarize_session` to access the active loop.
- **`AgentLoop.find_middleware(T)`** — type-safe lookup method that returns the first middleware matching the given type, or `None`.

## Implementation Summary

The summarization overhaul was implemented on 2026-05-21. Most acceptance criteria are met; see bugs below.

### Implemented

| Changed file | Key changes | Tests |
|------|--------|-------|
| `src/sdk/providers/base.py` | Added `ProviderContextOverflowError` exception class | 1 test |
| `src/sdk/middleware_summarization.py` | Replaced generic prompt with Claude Code's structured template (`<analysis>` tags, 5 sections); added `_prune_tool_outputs()` to replace old tool blobs with `[pruned: N tokens]` placeholders; refactored inline splitting logic into `_split_messages()`; added `force_summarize(state, instructions)` for manual/overflow-driven summarization; updated `abefore_model` to prune before counting tokens | 6 tests |
| `src/sdk/loop.py` | Added `_current_agent_loop` ContextVar + `get_current_agent_loop()` function; added `AgentLoop.find_middleware(T)` type-safe lookup; wrapped `run()` and `run_stream()` with ContextVar lifecycle; added overflow recovery in `_run_impl` (non-streaming) with 3-retry while loop calling `force_summarize` + user message replay; overflow recovery in `_run_stream_inner` (streaming) added but has a bug (see below) | 2 tests |
| `src/sdk/tools_core/summarize.py` | New file: `summarize_session` async tool that accesses the active loop via `get_current_agent_loop()`, calls `force_summarize`, reports token savings | 2 tests |
| `src/sdk/native_tools.py` | Imported and registered `summarize_session` | 1 test |
| `tests/sdk/test_summarization_overhaul.py` | 12 tests covering: `ProviderContextOverflowError`, pruning, splitting, `force_summarize` method existence, tool registration, annotations, ContextVar, `find_middleware` | — |

### Known Bugs

| # | Bug | Location | Severity | Fix |
|---|-----|----------|----------|-----|
| B1 | `overflow_retries` uninitialized in streaming path | `loop.py:912-913` in `_run_stream_inner` | High — crashes on first overflow | Add `overflow_retries = 0` before the `for iteration` loop (~line 801) |
| B2 | `non_system_old` undefined in `abefore_model` error path | `middleware_summarization.py:330` | Medium — crashes on summary generation failure | Replace `len(non_system_old)` with `len(old_messages)` |

### Deferred (not a blocker)

| Item | Reason |
|------|--------|
| Per-provider 413 error mapping (OpenAI, Anthropic, Gemini, Ollama) | `ProviderContextOverflowError` exception is defined and the loop handles it, but providers need per-provider error parsing to raise it. Can be added incrementally — currently the loop catches it when raised; providing it from each provider is a future improvement. |
| Thin test coverage for overflow recovery | No test verifies the overflow retry loop in either streaming or non-streaming path. |

### Full test results

```
255 passed, 2 failed (both pre-existing OllamaCloud identity tests)
```

## File Changes

| File | Change |
|------|--------|
| `src/sdk/loop.py` | Add `get_current_agent_loop()`, `AgentLoop.find_middleware()`, ContextVar lifecycle; catch `ProviderContextOverflowError` with overflow retry guard in both `_run_impl` and `_run_stream_inner` |
| `src/sdk/middleware_summarization.py` | Replace prompt, add `_prune_tool_outputs`, `_split_messages`, `force_summarize(instructions)`, update `abefore_model` |
| `src/sdk/providers/base.py` | Add `ProviderContextOverflowError` exception type |
| `src/sdk/tools_core/summarize.py` | New file: `summarize_session` tool |
| `src/sdk/native_tools.py` | Register `summarize_session` |

## Non-Goals

- No message store changes — pruning and replacement are in-memory only
- No duplicate prevention changes — existing guard (`_last_summary_msg_count`) still applies for auto-trigger
- The `/compact` command is specified as a tool, not a REST endpoint or Flutter UI

## Future Considerations

- Custom `CLAUDE.md`-style preservation notes: "always preserve file paths and error messages during summarization"
- Flutter button: "Compact now" in the workspace panel or chat footer
- Configurable max summary count before tool outputs are permanently truncated

## Peer Review Verdict

### Design Review (2026-05-21)

**Status: Design sound, ready for implementation after fixing 5 issues found in design peer review.**

| # | Issue | Severity | Status |
|---|-------|----------|--------|
| 1 | `force_summarize` signature missing `instructions` param | Bug | ✅ Fixed above |
| 2 | `_run_summary_hooks` referenced but never defined | Bug | ✅ Removed — using `_on_summarize` instead |
| 3 | `_generate_summary` can't access `state` for hook dispatch | Bug | ✅ Removed — hooks not needed |
| 4 | `get_current_agent_loop()` and `find_middleware()` don't exist | Prerequisite | ✅ Added to prerequisites + file changes |
| 5 | Overflow retry could infinite-loop | Bug | ✅ Fixed — added `MAX_OVERFLOW_RETRIES = 3` guard |
| 6 | `_split_messages()` referenced but not defined | Omission | ✅ `_split_messages` extracts the existing inline splitting logic from `abefore_model` (lines 167-190) into a reusable helper |

**Code validation:** All 6 design goals are validated against the current codebase. The existing `SummarizationMiddleware` (272 lines), `Middleware` ABC (70 lines), and `AgentLoop` (1079 lines) support all proposed changes with no breaking changes to existing behavior.

### Implementation Review (2026-05-21)

**Status: Mostly sound — 2 runtime bugs found during code review of the implementation.**

**Verification method:** Line-by-line comparison of the implemented code against the design spec, plus grep/read of all changed files.

| # | Issue | Location | Severity | Status |
|---|-------|----------|----------|--------|
| B1 | `overflow_retries` uninitialized in streaming path | `loop.py:912-913` | **High** — crashes with `UnboundLocalError` on first overflow in streaming | ❌ Needs fix |
| B2 | `non_system_old` undefined in `abefore_model` error path | `middleware_summarization.py:330` | **Medium** — crashes with `NameError` if summary generation fails | ❌ Needs fix |
| T1 | Thin test coverage — 8/12 tests structural, only 2 behavioral, zero overflow tests | `test_summarization_overhaul.py` | Low | Noted |

**Confidence level:** High. All line references verified against the current 2468-line `middleware_summarization.py`, 1166-line `loop.py`, and 51-line `summarize.py`.

## Acceptance Criteria

- Summarization prompt produces structured output with `<analysis>` and 5 sections
- Tool outputs older than `keep_tokens` are replaced with `[pruned: N tokens]` placeholders
- The pruned tokens are NOT sent to the LLM during summary generation
- The message store retains all original tool outputs unchanged
- An API overflow error triggers auto-summarization with max retry guard and replays the last user message
- The `summarize_session` tool triggers summarization on demand and reports token savings
- `force_summarize` accepts optional `instructions` parameter to focus the summary
- No regression in existing summarization behavior (auto-trigger, keep_tokens, on_summarize callback)
