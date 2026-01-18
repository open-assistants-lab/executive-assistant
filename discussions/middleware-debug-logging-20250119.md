# Middleware Debug Logging Design

**Date:** 2026-01-19
**Status:** Implemented
**Files:** `src/cassey/agent/middleware_debug.py`, `src/cassey/agent/status_middleware.py`

## Overview

Added debug logging to verify middleware effectiveness without exposing full internal state. Logs only when middleware **actually does something**, not just when it checks conditions.

## Problem Being Solved

LangChain middleware runs silently - you can't tell if:
- Summarization actually happened (or just checked and skipped)
- Context editing trimmed tool uses
- Retries occurred due to failures
- Call limits were hit

## Design

### Single Responsibility: `MiddlewareDebug` Utility

Created a reusable utility class that:
- Captures state before/after middleware runs
- Detects specific middleware actions by comparing states
- Logs with clear, concise format
- Can be extended for new middleware types

### What Gets Logged

| Middleware | Log Format | Example |
|------------|------------|---------|
| Summarization | `[SUMMARIZATION] 45→3 msgs (42 removed)` | Shows message/token reduction |
| Context Editing | `[CONTEXT_EDIT] Tool uses: 20→5 (15 removed, 75% reduction)` | Shows tool_use trimming |
| LLM Retry | `[LLM_RETRY] Expected 1 call, got 2 (1 retry)` | Shows retry count |
| Tool Retry | `[TOOL_RETRY] Expected 1 tool call, got 3 (2 retries)` | Shows tool retry |

### Status Message Integration

When status updates are enabled, users also see:
```
📝 Summarized: 45→3 msgs, 15000→2500 tokens (83% smaller)
```

## Implementation

### Files Created

```
src/cassey/agent/middleware_debug.py  # Detection utilities
├── MiddlewareDebug                    # State comparison class
│   ├── capture_before_model()
│   ├── capture_after_model()
│   ├── detect_summarization()
│   └── detect_context_editing()
│
└── RetryTracker                       # Call counting for retries
    ├── start_run()
    ├── record_llm_call()
    ├── record_tool_call()
    ├── detect_llm_retries()
    └── detect_tool_retries()
```

### Files Modified

```
src/cassey/agent/status_middleware.py
├── Uses MiddlewareDebug for detection
├── Uses RetryTracker for retry counting
└── Logs results via print() and status messages
```

## Usage

### In Production

Logs go to console automatically:
```bash
[SUMMARIZATION] 45 → 3 messages (42 removed)
[SUMMARIZATION] ~15000 → ~2500 tokens (12500 saved, 83.3% reduction)
[CONTEXT_EDIT] Tool uses: 20 → 5 (15 removed, 75.0% reduction)
```

### For Testing

```python
from cassey.agent.middleware_debug import MiddlewareDebug, RetryTracker

# Test summarization detection
debug = MiddlewareDebug()
debug.capture_before_model({"messages": long_message_list})
# ... summarization happens ...
debug.capture_after_model({"messages": short_message_list})
result = debug.detect_summarization()
assert result["reduction_pct"] > 80

# Test retry detection
tracker = RetryTracker()
tracker.start_run(expected_llm_calls=1)
tracker.record_llm_call()
tracker.record_llm_call()  # Unexpected = retry
result = tracker.detect_llm_retries()
assert result["retries"] == 1
```

## Detection Logic

### Summarization

**Trigger:** Message count drops significantly (>10 messages before)

```python
if messages_before > 10 and messages_after < messages_before:
    return {
        "messages_removed": messages_before - messages_after,
        "tokens_saved": tokens_before - tokens_after,
        "reduction_pct": (tokens_saved / tokens_before * 100),
    }
```

### Context Editing

**Trigger:** tool_uses count drops

```python
if tool_uses_after < tool_uses_before:
    return {
        "uses_removed": tool_uses_before - tool_uses_after,
        "reduction_pct": (uses_removed / tool_uses_before * 100),
    }
```

### Retries

**Trigger:** More calls than expected (1 LLM call per turn)

```python
actual_llm_calls = count_llm_calls_in_run()
expected = 1  # One model call per agent turn
if actual > expected:
    return {"retries": actual - expected}
```

## Limitations

| Middleware | Detection Confidence | Notes |
|------------|---------------------|-------|
| Summarization | ✅ High | Message count is reliable indicator |
| Context Editing | ✅ High | tool_uses count is reliable |
| Tool Retry | ⚠️ Medium | Multi-tool agents legitimately make multiple calls |
| Model Retry | ⚠️ Medium | Streaming responses may count differently |

## Future Enhancements

1. **Per-tool retry tracking** - Track which specific tools are retrying
2. **Retry reasons** - Log why retry happened (timeout, rate limit, etc.)
3. **Threshold alerts** - Warn when reduction is too aggressive
4. **Metrics export** - Send to Prometheus/Datadog for dashboards

## Configuration

No new config required - debug logging is automatic. Status messages can be disabled via `MW_STATUS_UPDATE_ENABLED=false`.
