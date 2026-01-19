# Realistic Response Time Test Plan

**Date:** 2026-01-19
**Status:** Design Phase
**Priority:** High
**Related:** `llm-benchmark-plan-20250118.md`

---

## Problem Statement

**Discrepancy Found:**
- **Direct LLM benchmark:** GPT-5 Mini takes 2-4 seconds
- **Actual Cassey usage:** GPT-5 Mini takes ~20 seconds for "hello"
- **Overhead:** ~15-18 seconds unaccounted for (5-10x slower!)

**Why This Matters:**
The existing LLM benchmark only tests the raw API call. It doesn't measure:
- Middleware overhead (SummarizationMiddleware, ModelCallLimitMiddleware, StatusUpdateMiddleware)
- Memory retrieval from vector store
- Checkpoint DB operations (PostgreSQL read/write)
- Agent routing and tool selection
- Channel processing (Telegram webhook, message parsing)
- Tool registration overhead (65 tools loaded)

---

## Goal

Measure **realistic end-to-end response time** for Cassey and identify exactly where the 15s+ overhead comes from.

---

## Test Architecture

### Timing Breakdown Points

```
User Message (Telegram)
    ↓
┌─────────────────────────────────────────────────────────────┐
│ CHANNEL LAYER                                               │
│ ├─ Webhook receipt       [T1: webhook_received]            │
│ ├─ Message parsing       [T2: message_parsed]              │
│ └─ User lookup           [T3: user_resolved]               │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│ MEMORY LAYER                                                │
│ ├─ Vector store query      [T4: vs_query_start]            │
│ └─ Memory injection        [T5: memory_injected]           │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│ AGENT LAYER                                                 │
│ ├─ State building          [T6: state_built]               │
│ ├─ Checkpoint read         [T7: checkpoint_loaded]         │
│ ├─ Middleware before       [T8: middleware_before]         │
│ │  ├─ SummarizationMiddleware                              │
│ │  ├─ ModelCallLimitMiddleware                            │
│ │  └─ StatusUpdateMiddleware                              │
│ ├─ LLM invocation          [T9: llm_start]                 │
│ │  └─ (includes tool selection, prompt building)           │
│ ├─ LLM first token         [T10: llm_first_token]          │
│ ├─ LLM completion         [T11: llm_done]                  │
│ ├─ Middleware after        [T12: middleware_after]         │
│ ├─ Checkpoint write        [T13: checkpoint_saved]         │
│ └─ Tool execution (if any) [T14: tools_done]               │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│ RESPONSE LAYER                                              │
│ ├─ Message extraction     [T15: response_ready]            │
│ ├─ Telegram send          [T16: telegram_sent]             │
│ └─ Status update          [T17: complete]                  │
└─────────────────────────────────────────────────────────────┘
```

### Expected Timing Breakdown

| Component | Expected Time | Actual (to measure) |
|-----------|---------------|---------------------|
| Channel processing | 50-200ms | ? |
| Memory retrieval | 100-500ms | ? |
| Checkpoint read | 50-200ms | ? |
| Middleware (before) | 50-200ms | ? |
| **LLM call** | 2-4s (benchmark) | ? |
| Tool execution | 0-5s (depends) | ? |
| Middleware (after) | 50-200ms | ? |
| Checkpoint write | 50-200ms | ? |
| Response send | 100-300ms | ? |
| **TOTAL EXPECTED** | ~3-6s | **~20s observed** |

**Missing time:** ~14-17 seconds unaccounted for!

---

## Hypotheses for the 15s+ Overhead

### Hypothesis 1: Memory Retrieval is Slow
- Vector store query might be inefficient
- Could be calling multiple times
- Network latency to embedding service

**Test:** Measure T4-T5 specifically

### Hypothesis 2: Checkpoint Operations are Slow
- PostgreSQL checkpoint read/write might be slow
- Large conversation history being loaded
- Serialization/deserialization overhead

**Test:** Measure T7 and T13 specifically

### Hypothesis 3: Middleware is Adding Significant Overhead
- SummarizationMiddleware: Analyzes message count/tokens
- ModelCallLimitMiddleware: Checks DB for call count
- StatusUpdateMiddleware: Updates status messages

**Test:** Measure T8 and T12 specifically

### Hypothesis 4: Tool Registration is Expensive
- 65 tools being formatted for each LLM call
- Tool descriptions might be very long
- LangChain tool processing overhead

**Test:** Compare with agent that has 0 tools

### Hypothesis 5: LLM Factory / Model Creation
- Model might be recreated on each call
- Provider connection overhead
- Retry logic adding delays

**Test:** Measure T9-T11 specifically

### Hypothesis 6: Streaming vs Non-Streaming
- LangGraph's `astream()` might be slower than `ainvoke()`
- Event parsing overhead
- Message extraction from events

**Test:** Compare `astream()` vs `ainvoke()`

### Hypothesis 7: System Prompt is Huge
- Current system prompt: ~1,125 tokens
- This adds ~3-5s to each LLM call
- But doesn't explain the remaining ~10s

**Test:** Measure with minimal system prompt

---

## Implementation Plan

### Phase 1: Create Timing Instrumentation (1 day)

#### File: `scripts/measure_response_time.py`

```python
"""
Realistic Cassey response time measurement.

Measures the full stack from message receipt to response send,
breaking down timing by component.
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
import json

from langchain_core.messages import HumanMessage

from cassey.config.llm_factory import LLMFactory
from cassey.config.settings import settings
from cassey.agent.prompts import get_system_prompt
from cassey.storage.db_storage import PostgresStorage


@dataclass
class TimingBreakdown:
    """Detailed timing breakdown for a single request."""
    # Request info
    scenario: str
    provider: str
    model: str
    timestamp: str

    # Timing points (all relative to start_time)
    start_time: float  # When request starts
    webhook_received: float = 0
    message_parsed: float = 0
    user_resolved: float = 0
    vs_query_start: float = 0
    memory_injected: float = 0
    state_built: float = 0
    checkpoint_loaded: float = 0
    middleware_before: float = 0
    llm_start: float = 0
    llm_first_token: float = 0
    llm_done: float = 0
    middleware_after: float = 0
    checkpoint_saved: float = 0
    tools_done: float = 0
    response_ready: float = 0
    telegram_sent: float = 0
    complete: float = 0

    # Metrics
    llm_tokens_in: int = 0
    llm_tokens_out: int = 0
    tool_calls: int = 0
    events_processed: int = 0
    middleware_events: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "scenario": self.scenario,
            "provider": self.provider,
            "model": self.model,
            "timestamp": self.timestamp,
            "timings_ms": {
                "channel_processing": (self.message_parsed - self.start_time) * 1000,
                "memory_retrieval": (self.memory_injected - self.vs_query_start) * 1000,
                "checkpoint_read": (self.checkpoint_loaded - self.state_built) * 1000,
                "middleware_before": (self.middleware_before - self.checkpoint_loaded) * 1000,
                "llm_total": (self.llm_done - self.llm_start) * 1000,
                "llm_ttfb": (self.llm_first_token - self.llm_start) * 1000 if self.llm_first_token > 0 else None,
                "tool_execution": (self.tools_done - self.llm_done) * 1000 if self.tools_done > 0 else 0,
                "middleware_after": (self.middleware_after - self.tools_done) * 1000 if self.tools_done > 0 else 0,
                "checkpoint_write": (self.checkpoint_saved - self.middleware_after) * 1000,
                "response_send": (self.telegram_sent - self.response_ready) * 1000,
                "total": (self.complete - self.start_time) * 1000,
            },
            "metrics": {
                "llm_tokens_in": self.llm_tokens_in,
                "llm_tokens_out": self.llm_tokens_out,
                "tool_calls": self.tool_calls,
                "events_processed": self.events_processed,
                "middleware_events": self.middleware_events,
            },
        }


class CasseyResponseTimeTester:
    """Test Cassey response time with full stack instrumentation."""

    def __init__(self, provider: str = "openai", model: str = None):
        self.provider = provider
        self.model = model or settings.OPENAI_DEFAULT_MODEL
        self.storage = PostgresStorage()
        self.results: list[TimingBreakdown] = []

    async def test_simple_hello(
        self,
        iterations: int = 3,
    ) -> list[TimingBreakdown]:
        """Test the simplest case: 'hello' message."""
        print("\n" + "=" * 60)
        print(f"🧪 Testing: Simple 'hello' message")
        print(f"Provider: {self.provider}, Model: {self.model}")
        print(f"Iterations: {iterations}")
        print("=" * 60)

        scenarios = []
        for i in range(iterations):
            result = await self._run_single_test(
                scenario="simple_hello",
                user_message="hello",
                conversation_id=f"test_conversation_{i}",
            )
            scenarios.append(result)
            self._print_result(result)

        return scenarios

    async def test_with_memory(
        self,
        iterations: int = 3,
    ) -> list[TimingBreakdown]:
        """Test with memory retrieval enabled."""
        print("\n" + "=" * 60)
        print(f"🧪 Testing: With memory retrieval")
        print(f"Provider: {self.provider}, Model: {self.model}")
        print(f"Iterations: {iterations}")
        print("=" * 60)

        scenarios = []
        for i in range(iterations):
            result = await self._run_single_test(
                scenario="with_memory",
                user_message="what did we discuss earlier?",
                conversation_id=f"test_memory_{i}",
                enable_memory=True,
            )
            scenarios.append(result)
            self._print_result(result)

        return scenarios

    async def test_with_tools(
        self,
        iterations: int = 3,
    ) -> list[TimingBreakdown]:
        """Test with tools that will be called."""
        print("\n" + "=" * 60)
        print(f"🧪 Testing: With tool calls")
        print(f"Provider: {self.provider}, Model: {self.model}")
        print(f"Iterations: {iterations}")
        print("=" * 60)

        scenarios = []
        for i in range(iterations):
            result = await self._run_single_test(
                scenario="with_tools",
                user_message="what time is it?",
                conversation_id=f"test_tools_{i}",
            )
            scenarios.append(result)
            self._print_result(result)

        return scenarios

    async def _run_single_test(
        self,
        scenario: str,
        user_message: str,
        conversation_id: str,
        enable_memory: bool = False,
    ) -> TimingBreakdown:
        """Run a single test with full timing instrumentation."""
        timing = TimingBreakdown(
            scenario=scenario,
            provider=self.provider,
            model=self.model,
            timestamp=datetime.now().isoformat(),
            start_time=time.time(),
        )

        # Simulate channel processing
        timing.webhook_received = time.time()
        await asyncio.sleep(0.001)  # Simulate minimal processing
        timing.message_parsed = time.time()

        # Simulate user lookup
        timing.user_resolved = time.time()

        # Memory retrieval (if enabled)
        timing.vs_query_start = time.time()
        if enable_memory:
            # Simulate vector store query
            await asyncio.sleep(0.1)  # Placeholder
        timing.memory_injected = time.time()

        # State building
        timing.state_built = time.time()

        # Get/create agent and checkpoint
        from cassey.agent.langchain_agent import create_langchain_agent
        from langgraph.checkpoint.postgres import PostgresSaver

        # Create checkpointer
        checkpointer = PostgresSaver.from_conn_string(settings.postgres_dsn)

        # Create LLM
        llm = LLMFactory.create(provider=self.provider, model=self.model)

        # Create agent
        system_prompt = get_system_prompt("telegram")
        agent = create_langchain_agent(
            model=llm,
            checkpointer=checkpointer,
            system_prompt=system_prompt,
        )

        # Config for checkpointing
        config = {
            "configurable": {
                "thread_id": conversation_id,
            }
        }

        # Checkpoint load
        timing.checkpoint_loaded = time.time()

        # Build state
        state = {"messages": [HumanMessage(content=user_message)]}

        # Track LLM timing via context
        llm_start_time = time.time()
        llm_first = None

        # Stream agent response
        timing.middleware_before = time.time()
        event_count = 0
        middleware_events = []

        async for event in agent.astream(state, config):
            event_count += 1
            event_type = list(event.keys())[0] if isinstance(event, dict) else "unknown"
            middleware_events.append(event_type)

            # Detect LLM start
            if timing.llm_start == 0 and "agent" in str(event_type).lower():
                timing.llm_start = time.time()

            # Try to detect first token (this is approximate)
            if timing.llm_start > 0 and timing.llm_first_token == 0:
                # Check if event contains message content
                if isinstance(event, dict):
                    for value in event.values():
                        if hasattr(value, "content") and value.content:
                            timing.llm_first_token = time.time()
                            break

        timing.llm_done = time.time() if timing.llm_start > 0 else timing.middleware_before
        if timing.llm_first_token == 0:
            timing.llm_first_token = timing.llm_done

        timing.middleware_after = time.time()
        timing.events_processed = event_count
        timing.middleware_events = middleware_events

        # Checkpoint save (simulated)
        timing.checkpoint_saved = time.time()

        # Response ready
        timing.response_ready = time.time()

        # Simulate Telegram send
        await asyncio.sleep(0.05)  # Network delay
        timing.telegram_sent = time.time()

        timing.complete = time.time()

        return timing

    def _print_result(self, result: TimingBreakdown) -> None:
        """Print timing result."""
        timings = result.to_dict()["timings_ms"]
        print(f"\n📊 Result:")
        print(f"  Total time:        {timings['total']:.0f}ms")
        print(f"  Channel processing: {timings['channel_processing']:.0f}ms")
        print(f"  Memory retrieval:   {timings['memory_retrieval']:.0f}ms")
        print(f"  Checkpoint read:    {timings['checkpoint_read']:.0f}ms")
        print(f"  Middleware (before): {timings['middleware_before']:.0f}ms")
        print(f"  LLM total:          {timings['llm_total']:.0f}ms")
        print(f"  LLM TTFB:           {timings['llm_ttfb']:.0f}ms" if timings['llm_ttfb'] else "  LLM TTFB:           N/A")
        print(f"  Tool execution:    {timings['tool_execution']:.0f}ms")
        print(f"  Checkpoint write:   {timings['checkpoint_write']:.0f}ms")
        print(f"  Response send:      {timings['response_send']:.0f}ms")
        print(f"  Events processed:   {result.events_processed}")
        print(f"  Middleware events:  {result.middleware_events[:5]}..." if len(result.middleware_events) > 5 else f"  Middleware events:  {result.middleware_events}")

    def save_results(self, path: str | None = None) -> None:
        """Save results to JSON."""
        if path is None:
            path = f"scripts/benchmark_results/response_time_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        Path(path).parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w") as f:
            json.dump([r.to_dict() for r in self.results], f, indent=2)

        print(f"\n💾 Results saved to: {path}")

    def generate_report(self) -> str:
        """Generate markdown report."""
        lines = [
            "# Cassey Response Time Test Report\n",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
            f"**Provider:** {self.provider}\n",
            f"**Model:** {self.model}\n",
            "---\n",
            "## Summary\n",
            "| Scenario | Avg Total (ms) | LLM (ms) | Overhead (ms) | Overhead % |",
            "|---|---|---|---|---|",
        ]

        # Group by scenario
        by_scenario: dict[str, list[TimingBreakdown]] = {}
        for r in self.results:
            by_scenario.setdefault(r.scenario, []).append(r)

        for scenario, results in by_scenario.items():
            avg_total = sum((r.complete - r.start_time) * 1000 for r in results) / len(results)
            avg_llm = sum((r.llm_done - r.llm_start) * 1000 for r in results if r.llm_start > 0) / len(results)
            overhead = avg_total - avg_llm
            overhead_pct = (overhead / avg_llm * 100) if avg_llm > 0 else 0

            lines.append(f"| {scenario} | {avg_total:.0f} | {avg_llm:.0f} | {overhead:.0f} | {overhead_pct:.0f}% |")

        lines.append("\n---\n")
        lines.append("## Detailed Breakdown\n")
        lines.append("All timings in milliseconds\n")
        lines.append("### Timing Breakdown by Component\n\n")
        lines.append("| Scenario | Channel | Memory | CP Read | MW Before | LLM | Tools | CP Write | Send | Total |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|")

        for r in self.results:
            t = r.to_dict()["timings_ms"]
            lines.append(
                f"| {r.scenario} | "
                f"{t['channel_processing']:.0f} | "
                f"{t['memory_retrieval']:.0f} | "
                f"{t['checkpoint_read']:.0f} | "
                f"{t['middleware_before']:.0f} | "
                f"{t['llm_total']:.0f} | "
                f"{t['tool_execution']:.0f} | "
                f"{t['checkpoint_write']:.0f} | "
                f"{t['response_send']:.0f} | "
                f"{t['total']:.0f} |"
            )

        return "\n".join(lines)


async def main():
    """Run response time tests."""
    import argparse

    parser = argparse.ArgumentParser(description="Test Cassey response time")
    parser.add_argument("--provider", default="openai", help="LLM provider")
    parser.add_argument("--model", help="Model name (default: provider default)")
    parser.add_argument("--iterations", type=int, default=3, help="Iterations per test")
    parser.add_argument("--scenarios", nargs="+", default=["hello", "memory", "tools"],
                        help="Scenarios to test")

    args = parser.parse_args()

    tester = CasseyResponseTimeTester(provider=args.provider, model=args.model)

    if "hello" in args.scenarios:
        results = await tester.test_simple_hello(iterations=args.iterations)
        tester.results.extend(results)

    if "memory" in args.scenarios:
        results = await tester.test_with_memory(iterations=args.iterations)
        tester.results.extend(results)

    if "tools" in args.scenarios:
        results = await tester.test_with_tools(iterations=args.iterations)
        tester.results.extend(results)

    # Save and report
    tester.save_results()
    report = tester.generate_report()

    report_path = f"scripts/benchmark_results/response_time_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        f.write(report)

    print(f"\n📊 Report saved to: {report_path}")
    print("\n" + report)


if __name__ == "__main__":
    asyncio.run(main())
```

### Phase 2: Add Enhanced Middleware Timing (1 day)

#### File: `src/cassey/agent/timing_middleware.py`

```python
"""
Enhanced timing middleware for precise performance measurement.

Hooks into LangGraph's middleware system to capture exact timing
for each middleware component.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from langchain.agents import AgentMiddleware

if TYPE_CHECKING:
    from collections.abc import Callable

# Global timing storage (thread-local would be better)
_active_timing: dict[str, dict] = {}


class TimingMiddleware(AgentMiddleware):
    """
    Middleware that tracks precise timing for all middleware components.

    Captures:
    - SummarizationMiddleware timing
    - ModelCallLimitMiddleware timing
    - StatusUpdateMiddleware timing
    - LLM call timing
    """

    async def abefore_agent(self, state: dict, runtime: Any) -> dict | Any | None:
        """Capture agent start time."""
        _active_timing["agent_start"] = time.time()
        return None

    async def abefore_model(self, state: dict, runtime: Any) -> dict | Any | None:
        """Capture model call start time."""
        _active_timing["model_start"] = time.time()
        return None

    async def aafter_model(self, state: dict, runtime: Any) -> dict | Any | None:
        """Capture model call end time."""
        _active_timing["model_end"] = time.time()
        return None

    async def aafter_agent(self, state: dict, runtime: Any) -> dict | Any | None:
        """Capture agent end time."""
        _active_timing["agent_end"] = time.time()
        return None


def get_timing() -> dict:
    """Get timing data for current request."""
    return {
        "agent_duration": _active_timing.get("agent_end", 0) - _active_timing.get("agent_start", 0),
        "model_duration": _active_timing.get("model_end", 0) - _active_timing.get("model_start", 0),
        "overhead_duration": (
            _active_timing.get("agent_start", 0) - _active_timing.get("model_start", 0) +
            _active_timing.get("agent_end", 0) - _active_timing.get("model_end", 0)
        ),
    }


def clear_timing() -> None:
    """Clear timing data."""
    _active_timing.clear()
```

### Phase 3: Run Comparative Tests (1 day)

```bash
# Test current provider (OpenAI GPT-5 Mini)
uv run python scripts/measure_response_time.py \
    --provider openai \
    --model gpt-5-mini-2025-08-07 \
    --iterations 5

# Test GPT-4o Mini (likely much faster)
uv run python scripts/measure_response_time.py \
    --provider openai \
    --model gpt-4o-mini \
    --iterations 5

# Test Claude Haiku (likely fastest)
uv run python scripts/measure_response_time.py \
    --provider anthropic \
    --model claude-haiku-4-20250514 \
    --iterations 5

# Compare with Ollama (local, no network)
uv run python scripts/measure_response_time.py \
    --provider ollama \
    --model qwen2.5:7b \
    --iterations 5
```

### Phase 4: Analyze and Report (1 day)

Generate comparison report:
- Overhead breakdown by component
- Provider/model comparison
- Bottleneck identification
- Recommendations

---

## Expected Outcomes

### Best Case (Overhead is minimal)
- Total time: ~5-8s for "hello"
- LLM: ~3s
- Overhead: ~2-5s (acceptable)
- **Conclusion:** 20s observed was an anomaly or temporary issue

### Likely Case (Overhead is significant but fixable)
- Total time: ~12-15s for "hello"
- LLM: ~3s
- Overhead: ~9-12s
- **Conclusion:** Specific component(s) causing slowdown (memory, DB, middleware)

### Worst Case (Overhead is systemic)
- Total time: ~20s for "hello"
- LLM: ~3s
- Overhead: ~17s
- **Conclusion:** Architecture issues requiring significant refactoring

---

## Quick Diagnosis Commands

### 1. Check Database Latency
```bash
# Time a simple checkpoint read
docker exec postgres_db psql -U cassey -c "\timing" -c "SELECT * FROM checkpoints LIMIT 1;"
```

### 2. Check Vector Store Latency
```python
# scripts/test_vs_latency.py
import time
from cassey.storage.kb_tools import search_kb

start = time.time()
result = search_kb("test query", collection_id="test")
elapsed = time.time() - start
print(f"VS query: {elapsed:.3f}s")
```

### 3. Check Middleware Timing
```python
# Enable debug logging
MW_STATUS_UPDATE_ENABLED=true
MW_MODEL_CALL_LIMIT=0  # Disable to remove one variable
```

### 4. Minimal Agent Test
```python
# Test with NO tools, NO middleware, NO checkpoint
# This should be close to raw LLM speed
```

---

## Success Criteria

1. **Identify** where the 15s+ overhead comes from
2. **Quantify** each component's contribution to total time
3. **Compare** providers/models in realistic setting
4. **Recommend** specific optimizations with expected impact

---

## Follow-up Actions Based on Findings

### If Memory Retrieval is Slow (>1s)
- Cache common queries
- Use faster embedding model
- Consider local embeddings (Ollama)
- Reduce VS collection size

### If Checkpoint is Slow (>500ms)
- Add connection pooling
- Optimize serialization
- Consider memory checkpointer for development
- Add caching for recent threads

### If Middleware is Slow (>1s)
- Parallelize independent middleware
- Cache middleware results
- Disable unnecessary middleware
- Refactor slow middleware

### If Tool Registration is Slow (>1s)
- Lazy-load tool definitions
- Cache formatted tool lists
- Reduce tool descriptions
- Group tools by usage frequency

### If LLM Call is Slow (>10s for simple message)
- Switch to faster model (GPT-4o Mini, Claude Haiku)
- Reduce system prompt size
- Enable response caching
- Consider alternative providers

---

## References

- Existing benchmark: `llm-benchmark-plan-20250118.md`
- Agent code: `src/cassey/agent/langchain_agent.py`
- Channel code: `src/cassey/channels/base.py`
- Middleware: `src/cassey/agent/status_middleware.py`, `src/cassey/agent/middleware_debug.py`
