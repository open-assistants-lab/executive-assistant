# Middleware Configuration Guide

## Overview

Middlewares are configurable components that intercept and enhance agent behavior. This guide covers all available middlewares, their configuration options, and how to test their effectiveness.

**Key Principles:**
- Configuration is YAML-only (no env vars for middleware settings)
- Single config file: `/data/config.yaml` (admin-managed, no user overrides)
- All middlewares tested via HTTP API (real integration tests)
- Progressive disclosure pattern minimizes token usage

## Configuration

### Location

**Path:** `/data/config.yaml`

**Managed by:** Admin / deployment person

**Format:** YAML

**No env var overrides** - Configuration is YAML-only. Environment variables are reserved for API keys, URLs, and deployment settings only.

### Configuration Loading Flow

1. Agent startup reads `/data/config.yaml`
2. YAML validated against Pydantic schema
3. Middleware factory instantiates enabled middlewares
4. Middlewares applied in configured order

## Available Middlewares

### Custom Middlewares

#### MemoryContextMiddleware

**Section:** `memory_context`

**Default:** Enabled

**Purpose:** Inject relevant user memories into prompts using progressive disclosure to minimize token usage.

**Configuration:**
```yaml
middleware:
  memory_context:
    enabled: true
    max_memories: 5                      # Maximum memories to inject (1-50)
    min_confidence: 0.7                  # Minimum confidence threshold (0.0-1.0)
    include_types: null                  # Filter to specific types (null = all)
```

**Memory Types:** profile, contact, preference, schedule, task, decision, insight, context, goal, chat, feedback, personal

**Effectiveness Targets:**
- Token savings: 10x from progressive disclosure
- Memory hit rate: 90%+
- Performance: <100ms overhead

**Testing:**
```bash
# Unit tests
uv run pytest tests/unit/middleware/test_memory_context.py -v

# HTTP integration tests
uv run pytest tests/integration/middleware_http/test_memory_context_http.py -v

# Effectiveness tests
uv run pytest tests/middleware_effectiveness/test_token_usage.py -v
```

#### MemoryLearningMiddleware

**Section:** `memory_learning`

**Default:** Enabled

**Purpose:** Automatically extract and save memories from conversations.

**Configuration:**
```yaml
middleware:
  memory_learning:
    enabled: true
    auto_learn: true                     # Extract automatically
    min_confidence: 0.6                  # Minimum confidence for saving (0.0-1.0)
    extraction_model: null               # LLM for extraction (provider/model format)
                                        # Null = rule-based extraction (no LLM)
    max_memories_per_conversation: 10    # Max memories per conversation
```

**Extraction Modes:**
- **Rule-based:** Fast, no LLM required, lower accuracy (~30-40% recall)
- **LLM-based:** Slower, higher accuracy (~70-80% recall), requires extraction_model

**Effectiveness Targets:**
- Extraction recall: 90%+ (LLM-based), 30%+ (rule-based)
- Extraction precision: 95%+
- Performance: <1s (rule-based), <10s (LLM-based)

#### LoggingMiddleware

**Section:** `logging`

**Default:** Enabled

**Purpose:** Log agent activity for debugging and analytics.

**Configuration:**
```yaml
middleware:
  logging:
    enabled: true
    log_dir: "/data/logs"                # Log directory path
    log_model_calls: true                # Log model calls
    log_tool_calls: true                 # Log tool calls
    log_memory_access: true              # Log memory access
    log_errors: true                     # Log errors
    log_format: "jsonl"                  # jsonl or json
```

**Log Format (JSONL):**
```jsonl
{"timestamp": "2025-01-15T10:30:00Z", "user_id": "user-123", "event": "model_call_complete", "data": {"duration_ms": 1234, "success": true}}
```

**Performance:** <50ms overhead per log entry

#### CheckinMiddleware

**Section:** `checkin`

**Default:** Disabled

**Purpose:** Periodic check-ins with the user (disabled by default).

**Configuration:**
```yaml
middleware:
  checkin:
    enabled: false
    interval_minutes: 30                 # Check-in interval (5-1440 minutes)
    active_hours_start: 8                # Start of active hours (0-23)
    active_hours_end: 22                 # End of active hours (1-24)
    idle_threshold_hours: 8              # Idle hours before check-in (1-168)
    checklist:                           # Check-in checklist items
      - "Check for pending tasks"
      - "Review recent conversations for follow-ups"
      - "Summarize any completed work"
```

#### RateLimitMiddleware

**Section:** `rate_limit`

**Default:** Enabled

**Purpose:** Rate limit agent requests per user to prevent abuse.

**Configuration:**
```yaml
middleware:
  rate_limit:
    enabled: true
    max_model_calls_per_minute: 60       # Max model calls per minute (1-1000)
    max_tool_calls_per_minute: 120       # Max tool calls per minute (1-2000)
    window_seconds: 60                   # Time window in seconds (10-3600)
```

**Performance:** <10ms overhead per check

### Built-in DeepAgents Middlewares

#### SummarizationMiddleware

**Section:** `summarization`

**Default:** Enabled

**Purpose:** Compress long conversations to save tokens.

**Configuration:**
```yaml
middleware:
  summarization:
    enabled: true
    max_tokens: 4000                     # Max tokens after summarization (1000-32000)
    threshold_tokens: 8000               # Trigger when exceeded (2000-100000)
    summary_model: null                  # Custom summarization model
                                        # Null = uses SUMMARIZATION_MODEL from env
```

**Effectiveness Targets (CRITICAL):**
- Token compression: >50%
- Information retention: 90%+
- Quality score: 4/5 (80%+)
- Performance: <60s for summarization

**Testing:**
```bash
# HTTP integration tests (CRITICAL)
uv run pytest tests/integration/middleware_http/test_summarization_http.py -v

# Effectiveness tests
uv run pytest tests/middleware_effectiveness/test_summarization_quality.py -v
```

#### TodoListMiddleware

**Section:** `todo_list`

**Purpose:** Manage todo lists for task tracking.

#### FilesystemMiddleware

**Section:** `filesystem`

**Purpose:** Manage file operations in virtual filesystem.

#### SubagentMiddleware

**Section:** `subagent`

**Purpose:** Manage subagent delegation.

#### HumanInTheLoopMiddleware

**Section:** `human_in_the_loop`

**Default:** Disabled

**Purpose:** Require user confirmations for certain actions.

#### ToolRetryMiddleware

**Section:** `tool_retry`

**Purpose:** Retry failed tool calls automatically.

## Example Configuration

### Minimal Example

```yaml
# /data/config.yaml
middleware:
  memory_context:
    enabled: true
    max_memories: 10  # Increased from default 5

  summarization:
    enabled: true
    threshold_tokens: 10000  # Summarize later than default
```

### Production Example

```yaml
# /data/config.yaml
middleware:
  # Custom middlewares
  memory_context:
    enabled: true
    max_memories: 5
    min_confidence: 0.7
    include_types: [profile, preference, task]  # Focus on key types

  memory_learning:
    enabled: true
    auto_learn: true
    min_confidence: 0.6
    extraction_model: "openai/gpt-4o-mini"  # Use LLM for better extraction
    max_memories_per_conversation: 10

  logging:
    enabled: true
    log_dir: "/data/logs"
    log_model_calls: true
    log_tool_calls: true
    log_errors: true
    log_format: "jsonl"

  checkin:
    enabled: false  # Disabled in production

  rate_limit:
    enabled: true
    max_model_calls_per_minute: 60
    max_tool_calls_per_minute: 120

  # Built-in middlewares
  summarization:
    enabled: true
    max_tokens: 4000
    threshold_tokens: 8000

  tool_retry:
    enabled: true
    max_retries: 3
    retry_on_errors:
      - "timeout"
      - "rate_limit"
      - "server_error"
```

## Testing

### HTTP Integration Tests (REQUIRED)

All middlewares are tested via HTTP API integration tests. This ensures middlewares work correctly in real usage scenarios.

**Run all HTTP integration tests:**
```bash
uv run pytest tests/integration/middleware_http/ -v
```

**Test specific middleware:**
```bash
# Memory context
uv run pytest tests/integration/middleware_http/test_memory_context_http.py -v

# Summarization (CRITICAL)
uv run pytest tests/integration/middleware_http/test_summarization_http.py -v
```

### Effectiveness Tests

Measure actual performance metrics and effectiveness.

**Run all effectiveness tests:**
```bash
uv run pytest tests/middleware_effectiveness/ -v
```

**Key effectiveness benchmarks:**
```bash
# Token usage (target: 10x savings from progressive disclosure)
uv run pytest tests/middleware_effectiveness/test_token_usage.py -v

# Memory hit rate (target: 90%+)
uv run pytest tests/middleware_effectiveness/test_memory_hit_rate.py -v

# Summarization quality (target: 4/5, >50% compression, 90%+ retention)
uv run pytest tests/middleware_effectiveness/test_summarization_quality.py -v

# Extraction quality and performance
uv run pytest tests/middleware_effectiveness/test_extraction_quality.py -v
```

### Unit Tests

Test individual middleware components in isolation.

```bash
uv run pytest tests/unit/middleware/ -v
```

## Benchmarking

### Run Benchmarks

**Benchmark all middlewares:**
```bash
uv run python scripts/benchmark_middlewares.py --all
```

**Benchmark specific middleware:**
```bash
uv run python scripts/benchmark_middlewares.py --middleware summarization
```

**Save results to file:**
```bash
uv run python scripts/benchmark_middlewares.py --all --output results.json
```

### Benchmark Output

Example output:
```
============================================================
Middleware Benchmarks
============================================================

Benchmarking MemoryContextMiddleware...
  - Testing token overhead...
  - Testing search performance...
  - Testing progressive disclosure savings...

[... other middlewares ...]

============================================================
Summary
============================================================

Total Tests: 15
Passed: 14 ✓
Failed: 1 ✗
Pass Rate: 93.3%

============================================================
By Middleware
============================================================

✓ memory_context: 3/3 tests passed
✓ memory_learning: 3/3 tests passed
✗ summarization: 2/3 tests passed
✓ rate_limit: 2/2 tests passed
✓ logging: 2/2 tests passed

============================================================
Critical Metrics
============================================================

Progressive Disclosure: 10.0x savings (target: 10x)
Summarization Compression: 60.0% (target: >50%)
Information Retention: 92.0% (target: 90%+)
Quality Score: 4.2/5 (target: 4.0+)
```

## Schema Reference

For a complete schema reference with all options and defaults, see:

```bash
cat config.schema.yaml
```

This file contains:
- All middleware configuration options
- Valid ranges and constraints
- Default values
- Descriptions and examples

## Troubleshooting

### Middleware Not Working

1. **Check if enabled:**
   ```yaml
   middleware:
     your_middleware:
       enabled: true  # Must be true
   ```

2. **Check config.yaml syntax:**
   ```bash
   # Validate YAML syntax
   python -c "import yaml; yaml.safe_load(open('/data/config.yaml'))"
   ```

3. **Check logs:**
   ```bash
   # View middleware logs
   cat /data/logs/agent-$(date +%Y-%m-%d).jsonl | jq
   ```

### High Token Usage

1. **Reduce memory_context.max_memories**
2. **Adjust summarization threshold lower**
3. **Check for middleware leaks in logs**

### Low Memory Hit Rate

1. **Lower memory_context.min_confidence** (e.g., 0.5)
2. **Enable LLM-based extraction** (set extraction_model)
3. **Check if memories are being saved** (via logs)

### Slow Performance

1. **Disable unnecessary middlewares**
2. **Check benchmark results** for bottlenecks
3. **Adjust rate limit window** if seeing many blocks

## Best Practices

1. **Start with defaults**, then adjust based on metrics
2. **Monitor logs** to understand middleware behavior
3. **Run benchmarks** before and after changes
4. **Use progressive disclosure** (memory_context, summarization)
5. **Test via HTTP** to verify real-world behavior

## Related Documentation

- `config.schema.yaml` - Complete configuration schema
- `AGENTS.md` - AI coding agent guidelines
- `tests/integration/middleware_http/` - HTTP integration test examples
- `tests/middleware_effectiveness/` - Effectiveness test examples
- `scripts/benchmark_middlewares.py` - Benchmarking tool
