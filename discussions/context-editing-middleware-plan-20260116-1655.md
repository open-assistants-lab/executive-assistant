# Plan: Context Editing Middleware (2026-01-16 16:55)

## Goal
Add a conservative ContextEditingMiddleware layer that trims large tool outputs only when context pressure is high, without changing core agent behavior.

## Non-Goals
- Do not replace summarization middleware.
- Do not remove user-visible messages or system prompts.
- Do not mutate tool results outside of explicit context pressure triggers.

## Proposed Approach
1. Add settings toggles:
   - `MW_CONTEXT_EDITING_ENABLED` (default: false)
   - `MW_CONTEXT_EDITING_TRIGGER_TOKENS` (default: 100000)
   - `MW_CONTEXT_EDITING_KEEP_TOOL_USES` (default: 3)
2. Implement in LangChain runtime only:
   - Add `ContextEditingMiddleware` to middleware list when enabled.
   - Configure `ClearToolUsesEdit(trigger=..., keep=...)`.
3. Keep summarization as primary context control; context editing is a safety net.

## Integration Points
- `src/executive_assistant/agent/langchain_agent.py`: extend `_build_middleware`.
- `src/executive_assistant/config/settings.py`: add settings and defaults.
- `.env.example`: document new settings.

## Tests
- Unit test: middleware list includes ContextEditingMiddleware when enabled.
- Behavior test: verify tool outputs trimmed after trigger threshold (mocked).

## Rollout Plan
- Stage 1: Add toggles and keep disabled in production.
- Stage 2: Enable in dev for long-running conversations.
- Stage 3: Enable for selected channels/users if stable.

## Risks / Mitigations
- Risk: Removing tool outputs needed later.
  - Mitigation: high trigger threshold + small keep count + keep summarization on.
