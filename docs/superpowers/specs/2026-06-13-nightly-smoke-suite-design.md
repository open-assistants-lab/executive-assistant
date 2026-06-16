# Nightly Smoke Suite Design

## Overview

A dedicated smoke test suite that exercises the full HTTP stack (FastAPI + AgentLoop + tools + LLM) against a real model (`ollama-cloud:deepseek-v4-flash`). Runs 180 tests (125 persona + 55 streaming) covering persona-driven interactions and streaming contract verification against the actual SSE endpoint.

## Architecture

```
tests/smoke/
├── __init__.py
├── run_smoke.py           # Entry point: parse args, orchestrate
├── server_manager.py      # Launch HTTP server with OLLAMA_API_KEY
├── suite_personas.py      # 125 persona tests via POST /message
├── suite_streaming.py     # 55 streaming contract tests via POST /message/stream
├── models.py              # TestResult, SuiteResult dataclasses
└── reporter.py            # Markdown report + JSONL interaction log
```

## Components

### server_manager.py

- Starts `uvicorn` as subprocess on chosen port
- Injects `OLLAMA_API_KEY` from CLI arg or env var
- Polls `/health` until ready (timeout: 30s)
- Returns base URL
- Async context manager for clean teardown

### suite_personas.py — 125 tests

- Reuses `PERSONAS` list and `generate_test_queries()` from `tests/evaluation/personas.py`
- Five personas × 25 queries = 125 tests:
  | Persona | ID | Why |
  |---------|----|-----|
  | Deep Diver | p22 | Complex multi-step, tests accuracy under load |
  | Technical Terry | p9 | Precise tool calls, verifies parameter passing |
  | Direct Dave | p1 | Terse commands, tests minimal-input understanding |
  | Error-Prone Eddie | p23 | Edge cases and error recovery |
  | Casual Chris | p3 | Informal language, tests tool detection from natural speech |

- Each interaction:
  1. `POST /message` with `{"message": query, "user_id": "smoke_eval"}`
  2. Assert HTTP 200
  3. Assert `response` is non-empty string
  4. Assert `error` is null
  5. Log response time, tool calls, token count

### suite_streaming.py — 55 tests

- `POST /message/stream` with SSE parsing via `aiohttp` 
- Parses every SSE event line, validates against the SSE endpoint's output format
- The SSE endpoint emits these event types (NOT raw StreamChunks):
  - `type: messages` with `data.content` (text_delta, reasoning_delta)
  - `type: updates` with `data.content` ("Using tool: X", tool output, "[Thinking...]")
  - `type: error` with `data.content` (error message)
- Each test validates event sequence, content format, and timing
- Test breakdown:

| # | Category | Tests | What it verifies |
|---|----------|-------|------------------|
| 10 | Basic streaming | 10 | Events arrive, stream terminates within 60s, no gap >30s between events |
| 15 | Tool call stream | 15 | `updates` event with "Using tool: X" is followed by tool output or `messages` text; tool names match valid tool set; correct tool invocation from natural language |
| 10 | Reasoning stream | 10 | `updates` with "[Thinking...]" appears at stream start; `messages` with "[Reasoning] ..." follow; content non-empty |
| 5 | Text accumulation | 5 | All `messages` type text_delta events concatenate to form coherent final response |
| 5 | Error handling | 5 | Empty message → `error` event with non-empty message; invalid input → graceful degradation |
| 5 | Multi-turn SSE | 5 | Two sequential streaming calls with same `user_id`: second call's response references information from first call |
| 5 | Content integrity | 5 | Text content doesn't contain raw StreamChunk type names (`text_delta`, `tool_input_start` etc.); HTML-like content preserved; Unicode (emoji, CJK) preserved |

### models.py

```python
@dataclass
class TestResult:
    name: str
    passed: bool
    duration_ms: int
    error: str | None = None
    tool_calls: int = 0
    tokens: int = 0
    response_preview: str = ""

@dataclass
class SuiteResult:
    category: str
    total: int
    passed: int
    results: list[TestResult]
    duration_ms: int

@dataclass
class SmokeReport:
    timestamp: str
    suites: list[SuiteResult]
    total_tests: int
    total_passed: int
    total_duration_ms: int
    model: str
```

### reporter.py

- Generates a markdown report with sections:
  1. **Summary header** — date, model, total/pass/fail counts, duration
  2. **Persona results table** — per-persona: name, tests passed, failed, avg response time, tool calls
  3. **Streaming results table** — per-category: tests passed/failed, avg duration
  4. **Failure detail** — each failed test with name, error, response preview
  5. **Cost estimate** — approximate token + dollar cost
- Also writes a JSONL file with one line per interaction:
  ```jsonl
  {"timestamp": "...", "category": "persona", "name": "p22-query-7", "passed": true, "duration_ms": 3421, "tool_calls": 3, "tokens": 512, "response": "..."}
  {"timestamp": "...", "category": "streaming", "name": "basic-001", "passed": false, "duration_ms": 5210, "error": "No done event received within 30s"}
  ```

## Entry Point

```bash
# Default: port 8080, 5 personas x 25 queries = 125 persona tests + 55 streaming
python tests/smoke/run_smoke.py --api-key "$OLLAMA_API_KEY"

# Custom port, model, streaming categories, full persona suite
python tests/smoke/run_smoke.py \
  --api-key "$OLLAMA_API_KEY" \
  --port 9090 \
  --model "ollama-cloud:deepseek-v4-flash" \
  --personas 5 \
  --streaming all

# Run all 25 personas (full coverage — 625 persona tests + 55 streaming = 680 total)
python tests/smoke/run_smoke.py --api-key "$OLLAMA_API_KEY" --personas all
```

## CLI Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--api-key` | `$OLLAMA_API_KEY` | OllamaCloud API key |
| `--port` | `8080` | HTTP server port |
| `--model` | `ollama-cloud:deepseek-v4-flash` | Model string for the agent |
| `--personas` | `5` | Number of personas to sample (5 = Deep Diver, Technical Terry, Direct Dave, Error-Prone Eddie, Casual Chris). Use `all` for full 25-persona coverage |
| `--streaming` | `all` | Comma-separated streaming categories: `basic`, `tool`, `reasoning`, `accumulation`, `error`, `multiturn`, `integrity`, or `all` |
| `--output` | `data/smoke/` | Output directory for report and logs |

Streaming category short names:
- `basic` → Basic streaming (10 tests)
- `tool` → Tool call stream (15 tests)  
- `reasoning` → Reasoning stream (10 tests)
- `accumulation` → Text accumulation (5 tests)
- `error` → Error handling (5 tests)
- `multiturn` → Multi-turn SSE (5 tests)
- `integrity` → Content integrity (5 tests)
- `all` → All 55 tests

## Provider & Model

All tests use `ollama-cloud:deepseek-v4-flash` by default, overridable via `--model`.
- Default is in `config.yaml` (already set)
- `server_manager.py` sets `OLLAMA_API_KEY` env var when spawning `uvicorn`
- CoreMem is not LLM-dependent — it's SQLite + FTS5 + ChromaDB storage only. No CoreMem-specific model config needed.

## Cost Estimation

At `ollama-cloud:deepseek-v4-flash` pricing ($0.15/M input tokens):
- Persona tests: ~500-2000 input tokens × 125 = ~62K-250K input tokens = ~$0.01-0.04
- Streaming tests: ~300-1000 input tokens × 55 = ~16K-55K input tokens = ~$0.002-0.008
- Output tokens: ~100-500 per test × 180 = ~18K-90K = ~$0.003-0.014
- **Estimated total: ~$0.02-0.06 per full run**

## Implementation Plan

1. Create `tests/smoke/` directory with `__init__.py`
2. Implement `models.py` — TestResult, SuiteResult, SmokeReport dataclasses
3. Implement `server_manager.py` — async context manager for HTTP server subprocess
4. Implement `suite_personas.py` — persona-driven tests via POST /message
5. Implement `suite_streaming.py` — streaming contract tests via POST /message/stream
6. Implement `reporter.py` — markdown report + JSONL log generation
7. Implement `run_smoke.py` — CLI entry point tying everything together
8. Create `scripts/nightly-smoke.sh` — wrapper script that reads `OLLAMA_API_KEY` from `.env`, runs smoke suite, saves report with timestamp, exits non-zero on failures
9. Verify: run full suite, confirm all 180 tests pass

## Future Enhancements

- GitHub Actions workflow for nightly cron run
- Slack/email notification on failures
- Historical trend tracking in data/evaluations/
