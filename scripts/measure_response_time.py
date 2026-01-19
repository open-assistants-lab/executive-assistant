#!/usr/bin/env python3
"""
Realistic Cassey response time measurement.

Measures the full stack timing, breaking down where time is spent:
- Channel processing
- Memory retrieval
- Checkpoint operations
- Middleware
- LLM call
- Tool execution

Usage:
    python scripts/measure_response_time.py --provider openai --iterations 3
"""

from __future__ import annotations

import argparse
import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from langchain_core.messages import HumanMessage

from cassey.config.llm_factory import LLMFactory
from cassey.config.settings import settings
from cassey.agent.langchain_agent import create_langchain_agent
from cassey.agent.prompts import get_system_prompt
from cassey.tools.registry import get_all_tools
from cassey.storage.checkpoint import get_async_checkpointer
from cassey.storage.file_sandbox import set_thread_id


@dataclass
class TimingBreakdown:
    """Detailed timing breakdown for a single request."""

    scenario: str
    provider: str
    model: str
    timestamp: str
    start_time: float

    # Timing points (all relative to start_time)
    state_built: float = 0
    memory_start: float = 0
    memory_done: float = 0
    checkpoint_loaded: float = 0
    agent_stream_start: float = 0
    llm_start: float = 0
    llm_done: float = 0
    agent_stream_end: float = 0
    message_extraction: float = 0  # Extract messages from events
    markdown_conversion: float = 0  # Clean markdown for Telegram
    telegram_estimate: float = 0  # Estimated Telegram API overhead

    # Metrics
    events_processed: int = 0
    messages_extracted: int = 0
    middleware_events: list[str] = field(default_factory=list)
    memories_retrieved: int = 0
    error: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        # Total time: from start to after Telegram (simulated)
        telegram_end = self.telegram_estimate if self.telegram_estimate > 0 else self.markdown_conversion
        total = (telegram_end - self.start_time) * 1000 if telegram_end > 0 else 0

        # Agent-only time (without Telegram/post-processing)
        agent_total = (self.agent_stream_end - self.start_time) * 1000 if self.agent_stream_end > 0 else 0
        llm = (self.llm_done - self.llm_start) * 1000 if self.llm_start > 0 and self.llm_done > 0 else 0
        memory = (self.memory_done - self.memory_start) * 1000 if self.memory_start > 0 and self.memory_done > 0 else 0

        # Post-agent processing
        # NOTE: Message extraction now happens DURING stream (included in agent_total)
        # Markdown conversion and Telegram API happen after stream
        post_agent = (telegram_end - self.agent_stream_end) * 1000 if self.agent_stream_end > 0 and telegram_end > 0 else 0
        markdown_conv = (self.markdown_conversion - self.agent_stream_end) * 1000 if self.agent_stream_end > 0 and self.markdown_conversion > 0 else 0
        telegram_api = (self.telegram_estimate - self.markdown_conversion) * 1000 if self.markdown_conversion > 0 and self.telegram_estimate > 0 else 0

        overhead = agent_total - llm if agent_total > 0 and llm > 0 else 0

        return {
            "scenario": self.scenario,
            "provider": self.provider,
            "model": self.model,
            "timestamp": self.timestamp,
            "timings_ms": {
                "state_build": (self.state_built - self.start_time) * 1000,
                "memory_retrieval": memory,
                "checkpoint_load": (self.checkpoint_loaded - (self.memory_done if self.memory_done > 0 else self.state_built)) * 1000,
                "agent_stream_start": (self.agent_stream_start - self.checkpoint_loaded) * 1000,
                "llm_total": llm,
                "agent_stream_end": (self.agent_stream_end - self.llm_done) * 1000,
                "message_extraction": 0,  # Now happens during stream (included in agent_total)
                "markdown_conversion": markdown_conv,
                "telegram_api_estimate": telegram_api,
                "post_agent_total": post_agent,
                "total_including_telegram": total,
                "agent_only_total": agent_total,
                "overhead": overhead,
                "overhead_percent": (overhead / agent_total * 100) if agent_total > 0 else 0,
            },
            "metrics": {
                "events_processed": self.events_processed,
                "messages_extracted": self.messages_extracted,
                "middleware_events": self.middleware_events,
                "memories_retrieved": self.memories_retrieved,
            },
            "error": self.error,
        }


class CasseyResponseTimeTester:
    """Test Cassey response time with full stack instrumentation."""

    def __init__(self, provider: str = "openai", model: str | None = None):
        self.provider = provider
        self.model = model or self._get_default_model()
        self.results: list[TimingBreakdown] = []
        self._checkpointer = None

    async def _get_checkpointer(self):
        """Get or create async checkpointer."""
        if self._checkpointer is None:
            self._checkpointer = await get_async_checkpointer(
                storage_type="postgres",
                connection_string=settings.POSTGRES_URL,
            )
        return self._checkpointer

    def _get_default_model(self) -> str:
        """Get default model for provider."""
        if self.provider == "openai":
            return settings.OPENAI_DEFAULT_MODEL or "gpt-4o-mini"
        elif self.provider == "anthropic":
            return settings.ANTHROPIC_DEFAULT_MODEL or "claude-haiku-4-20250514"
        elif self.provider == "ollama":
            return settings.OLLAMA_DEFAULT_MODEL or "qwen2.5:7b"
        else:
            return "default"

    async def test_simple_hello(self, iterations: int = 3) -> list[TimingBreakdown]:
        """Test the simplest case: 'hello' message."""
        print("\n" + "=" * 70)
        print(f"🧪 Testing: Simple 'hello' message")
        print(f"   Provider: {self.provider}, Model: {self.model}")
        print(f"   Iterations: {iterations}")
        print("=" * 70)

        scenarios = []
        for i in range(iterations):
            print(f"\n--- Iteration {i + 1}/{iterations} ---")
            result = await self._run_single_test(
                scenario="simple_hello",
                user_message="hello",
                conversation_id=f"test_hello_{int(time.time())}_{i}",
            )
            scenarios.append(result)
            self._print_result(result)

        return scenarios

    async def test_with_memory(self, iterations: int = 3) -> list[TimingBreakdown]:
        """Test with memory retrieval enabled."""
        print("\n" + "=" * 70)
        print(f"🧪 Testing: With memory retrieval")
        print(f"   Provider: {self.provider}, Model: {self.model}")
        print(f"   Iterations: {iterations}")
        print("=" * 70)

        scenarios = []
        for i in range(iterations):
            print(f"\n--- Iteration {i + 1}/{iterations} ---")
            result = await self._run_single_test(
                scenario="with_memory",
                user_message="what did we discuss earlier?",
                conversation_id=f"test_memory_{int(time.time())}_{i}",
                enable_memory=True,
            )
            scenarios.append(result)
            self._print_result(result)

        return scenarios

    async def test_with_tools(self, iterations: int = 3) -> list[TimingBreakdown]:
        """Test with tools that will be called."""
        print("\n" + "=" * 70)
        print(f"🧪 Testing: Message that triggers tool use")
        print(f"   Provider: {self.provider}, Model: {self.model}")
        print(f"   Iterations: {iterations}")
        print("=" * 70)

        scenarios = []
        for i in range(iterations):
            print(f"\n--- Iteration {i + 1}/{iterations} ---")
            result = await self._run_single_test(
                scenario="with_tools",
                user_message="what time is it?",  # Should trigger get_time tool
                conversation_id=f"test_tools_{int(time.time())}_{i}",
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

        try:
            # State building
            timing.state_built = time.time()

            # Memory retrieval (if enabled)
            enhanced_message = user_message
            if enable_memory:
                timing.memory_start = time.time()

                # Set thread_id context for memory storage
                set_thread_id(conversation_id)

                try:
                    from cassey.storage.mem_storage import get_mem_storage

                    storage = get_mem_storage()
                    memories = storage.search_memories(
                        query=user_message,
                        limit=5,
                        min_confidence=settings.MEM_CONFIDENCE_MIN,
                    )
                    timing.memories_retrieved = len(memories)

                    # Inject memories into message (similar to base channel)
                    if memories:
                        memory_context = "\n\n".join([
                            f"- {m.get('content', '')}" for m in memories
                        ])
                        enhanced_message = (
                            f"[Relevant context from previous conversations:\n{memory_context}\n\n"
                            f"User message: {user_message}]"
                        )
                except Exception as e:
                    print(f"   ⚠️  Memory retrieval failed: {e}")
                    timing.memories_retrieved = 0

                timing.memory_done = time.time()

            # Create LLM
            llm = LLMFactory.create(provider=self.provider, model=self.model)

            # Get tools for agent
            tools = await get_all_tools()

            # Get checkpointer
            checkpointer = await self._get_checkpointer()

            # Create agent (do this each time to measure full setup)
            system_prompt = get_system_prompt("telegram")
            agent = create_langchain_agent(
                model=llm,
                tools=tools,
                checkpointer=checkpointer,
                system_prompt=system_prompt,
            )

            # Config for checkpointing
            config = {
                "configurable": {
                    "thread_id": conversation_id,
                }
            }

            # Checkpoint load timing
            timing.checkpoint_loaded = time.time()

            # Build state (with potentially enhanced message from memory retrieval)
            state = {"messages": [HumanMessage(content=enhanced_message)]}

            # Stream agent response
            timing.agent_stream_start = time.time()
            event_count = 0
            middleware_events = []

            # Track LLM timing by detecting model calls in events
            llm_start_detected = False
            llm_end_detected = False

            # Extract messages during stream (matches production base.py:356-359)
            messages = []

            async for event in agent.astream(state, config):
                event_count += 1

                # Extract event type/key
                if isinstance(event, dict):
                    event_keys = list(event.keys())
                    middleware_events.extend(event_keys)
                else:
                    event_keys = [str(type(event).__name__)]
                    middleware_events.append(event_keys[0])

                # Extract messages from events (like production)
                for msg in self._extract_message_from_event(event):
                    messages.append(msg)

                # Detect LLM start (when we see agent/model related events)
                if not llm_start_detected:
                    for key in event_keys:
                        key_lower = str(key).lower()
                        if "model" in key_lower or "llm" in key_lower or "chat" in key_lower:
                            if not llm_start_detected:
                                timing.llm_start = time.time()
                                llm_start_detected = True
                                break

                # After LLM, we start seeing tool or finish events
                if llm_start_detected and not llm_end_detected:
                    for key in event_keys:
                        key_lower = str(key).lower()
                        if "tool" in key_lower or "finish" in key_lower or "end" in key_lower:
                            timing.llm_done = time.time()
                            llm_end_detected = True
                            break

                if event_count % 50 == 0:
                    print(f"   Processed {event_count} events...")

            # If we didn't detect LLM end explicitly, set it now
            if not llm_end_detected and llm_start_detected:
                timing.llm_done = time.time()
            elif not llm_start_detected:
                # Never detected LLM start, use stream times as fallback
                timing.llm_start = timing.agent_stream_start
                timing.llm_done = time.time()

            timing.agent_stream_end = time.time()
            timing.messages_extracted = len(messages)
            print(f"   • Messages extracted during stream: {len(messages)}")

            # === NEW: Simulate markdown conversion (matches telegram.py _clean_markdown) ===
            timing.markdown_conversion = time.time()

            # Simulate markdown cleaning for each message (if it has content)
            markdown_conversions = 0
            for msg in messages:
                if hasattr(msg, "content") and msg.content:
                    # Simulate _clean_markdown() processing
                    # This involves string operations for special character escaping
                    cleaned_content = self._simulate_markdown_clean(msg.content)
                    markdown_conversions += 1

            markdown_conversion_time = time.time() - timing.markdown_conversion
            print(f"   • Markdown conversion: {markdown_conversion_time*1000:.0f}ms ({markdown_conversions} messages)")

            # === NEW: Estimate Telegram API overhead ===
            # Based on real production measurements, Telegram API takes ~3-4s
            # This includes: typing indicator + send_message API + network latency
            # We'll use a realistic estimate based on your real measurements
            telegram_estimate_ms = 3500  # ~3.5s based on your real tests (13.68 - 10.13)
            timing.telegram_estimate = time.time() + (telegram_estimate_ms / 1000)
            print(f"   • Telegram API (estimate): {telegram_estimate_ms:.0f}ms")
            timing.events_processed = event_count
            timing.middleware_events = middleware_events[:20]  # Keep first 20

        except Exception as e:
            timing.error = str(e)
            timing.agent_stream_end = time.time()
            if timing.llm_start == 0:
                timing.llm_start = timing.start_time
                timing.llm_done = time.time()

        return timing

    def _extract_message_from_event(self, event):
        """Extract message from event (matches base.py logic)."""
        # Simulates base.py _extract_messages_from_event logic (base.py:263-278)
        if isinstance(event, dict):
            # Direct messages array
            if "messages" in event and isinstance(event["messages"], list):
                for msg in event["messages"]:
                    yield msg
            # LangChain agent middleware events: {'model': {'messages': [...]}}
            for key in ("model", "agent", "output", "final"):
                value = event.get(key)
                if isinstance(value, dict) and isinstance(value.get("messages"), list):
                    for msg in value["messages"]:
                        yield msg
        elif hasattr(event, "content"):
            yield event

    def _simulate_markdown_clean(self, text: str) -> str:
        """Simulate telegram.py _clean_markdown() processing."""
        # This simulates the special character escaping done in production
        # In production: text.replace('\\', '\\\\'), escaping * _ ~ ` > # + - = | { } . !
        # We'll do a simplified version for timing
        chars_to_escape = ['*', '_']
        for char in chars_to_escape:
            count = text.count(char)
            if count % 2 == 1:
                # Odd count - escape the last occurrence
                last_pos = text.rfind(char)
                if last_pos != -1:
                    text = text[:last_pos] + '\\' + char + text[last_pos + 1:]
        return text

    def _print_result(self, result: TimingBreakdown) -> None:
        """Print timing result."""
        if result.error:
            print(f"\n❌ ERROR: {result.error}")
            return

        timings = result.to_dict()["timings_ms"]
        print(f"\n📊 Timing Breakdown (Production-Aligned):")
        print(f"\n   **Including Telegram API (Production-like):**")
        print(f"   Total time:        {timings['total_including_telegram']:.0f}ms ({timings['total_including_telegram']/1000:.1f}s)")
        print(f"   ├─ Agent only:      {timings['agent_only_total']:.0f}ms ({timings['agent_only_total']/1000:.1f}s)")
        print(f"   └─ Post-agent:      {timings['post_agent_total']:.0f}ms ({timings['post_agent_total']/1000:.1f}s)")
        print(f"\n   **Agent Breakdown:**")
        print(f"   ├─ LLM call:        {timings['llm_total']:.0f}ms ({timings['llm_total']/1000:.1f}s)")
        print(f"   ├─ Message extraction: {timings['message_extraction']:.0f}ms (during stream)")
        print(f"   └─ Agent overhead:  {timings['overhead'] - timings['message_extraction']:.0f}ms ({(timings['overhead'] - timings['message_extraction'])/1000:.1f}s, {(timings['overhead'] - timings['message_extraction'])/timings['agent_only_total']*100 if timings['agent_only_total'] > 0 else 0:.0f}%)")
        print(f"\n   **Post-Agent Breakdown:**")
        print(f"   ├─ Markdown conversion: {timings['markdown_conversion']:.0f}ms")
        print(f"   └─ Telegram API (est): {timings['telegram_api_estimate']:.0f}ms")
        print(f"\n   **Detail:**")
        print(f"   • State build:      {timings['state_build']:.0f}ms")
        if timings['memory_retrieval'] > 0:
            print(f"   • Memory retrieval: {timings['memory_retrieval']:.0f}ms ({result.memories_retrieved} memories)")
        print(f"   • Checkpoint load:  {timings['checkpoint_load']:.0f}ms")
        print(f"   • Agent stream:     {timings['agent_stream_start']:.0f}ms")
        print(f"   • After LLM:        {timings['agent_stream_end']:.0f}ms")
        print(f"\n   **Metrics:**")
        print(f"   • Events processed:     {result.events_processed}")
        print(f"   • Messages extracted:   {result.messages_extracted}")
        print(f"   • Middleware events:    {result.middleware_events[:10]}")

    def save_results(self, path: str | None = None) -> None:
        """Save results to JSON."""
        if path is None:
            path = f"scripts/benchmark_results/response_time_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        Path(path).parent.mkdir(parents=True, exist_ok=True)

        import json
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
            f"**Tests Run:** {len(self.results)}\n",
            "---\n",
        ]

        if not self.results:
            lines.append("\n⚠️ No results to report.\n")
            return "\n".join(lines)

        # Summary table
        lines.append("## Summary\n")
        lines.append("| Scenario | Iterations | Avg Total (s) | LLM (s) | Overhead (s) | Overhead % |")
        lines.append("|---|---|---|---|---|---|")

        # Group by scenario
        by_scenario: dict[str, list[TimingBreakdown]] = {}
        for r in self.results:
            by_scenario.setdefault(r.scenario, []).append(r)

        for scenario, results in by_scenario.items():
            if any(r.error for r in results):
                error_count = sum(1 for r in results if r.error)
                lines.append(f"| {scenario} | {len(results)} | - | - | - | {error_count} errors |")
                continue

            avg_total = sum((r.agent_stream_end - r.start_time) for r in results) / len(results)
            avg_llm = sum((r.llm_done - r.llm_start) for r in results if r.llm_start > 0) / len(results)
            overhead = avg_total - avg_llm
            overhead_pct = (overhead / avg_total * 100) if avg_total > 0 else 0

            lines.append(
                f"| {scenario} | {len(results)} | {avg_total:.2f} | {avg_llm:.2f} | {overhead:.2f} | {overhead_pct:.0f}% |"
            )

        lines.append("\n---\n")

        # Detailed breakdown
        lines.append("## Detailed Breakdown\n")
        lines.append("All timings in milliseconds\n")
        lines.append("| Scenario | Total | LLM | Overhead | Events |")
        lines.append("|---|---|---|---|---|")

        for r in self.results:
            if r.error:
                lines.append(f"| {r.scenario} | ERROR | - | - | {r.error} |")
                continue

            t = r.to_dict()["timings_ms"]
            lines.append(
                f"| {r.scenario} | "
                f"{t['total_including_telegram']:.0f} | "
                f"{t['llm_total']:.0f} | "
                f"{t['overhead']:.0f} ({t['overhead_percent']:.0f}%) | "
                f"{r.events_processed} |"
            )

        lines.append("\n---\n")

        # Analysis
        lines.append("## Analysis\n")

        for scenario, results in by_scenario.items():
            if any(r.error for r in results):
                continue

            # Use telegram_estimate if available (production-aligned), otherwise agent_stream_end
            avg_total = sum((r.telegram_estimate - r.start_time if r.telegram_estimate > 0 else r.agent_stream_end - r.start_time) for r in results) / len(results)
            avg_llm = sum((r.llm_done - r.llm_start) for r in results) / len(results)
            overhead = avg_total - avg_llm
            overhead_pct = (overhead / avg_total * 100) if avg_total > 0 else 0

            lines.append(f"\n### {scenario}\n")

            if overhead_pct < 30:
                lines.append(f"✅ **Good**: Overhead is only {overhead_pct:.0f}% of total time\n")
            elif overhead_pct < 60:
                lines.append(f"⚠️ **Moderate**: Overhead is {overhead_pct:.0f}% of total time\n")
            else:
                lines.append(f"❌ **High**: Overhead is {overhead_pct:.0f}% of total time (unacceptable)\n")

            lines.append(f"- Average total time: {avg_total:.2f}s\n")
            lines.append(f"- Average LLM time: {avg_llm:.2f}s\n")
            lines.append(f"- Average overhead: {overhead:.2f}s\n")

        return "\n".join(lines)


async def main():
    """Run response time tests."""
    parser = argparse.ArgumentParser(
        description="Test Cassey response time with full stack measurement",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test simple 'hello' message
  python scripts/measure_response_time.py --provider openai --iterations 3

  # Test with tools
  python scripts/measure_response_time.py --provider openai --scenarios tools --iterations 3

  # Test multiple providers
  python scripts/measure_response_time.py --provider anthropic --model claude-haiku-4-20250514
        """,
    )
    parser.add_argument("--provider", default="openai", help="LLM provider (openai, anthropic, ollama)")
    parser.add_argument("--model", help="Model name (default: provider default)")
    parser.add_argument("--iterations", type=int, default=3, help="Iterations per test")
    parser.add_argument("--scenarios", nargs="+", default=["hello", "tools"],
                        help="Scenarios to test: hello, memory, tools")
    parser.add_argument("--output", help="Output JSON path")

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

    # Save results
    tester.save_results(path=args.output)

    # Generate and save report
    report = tester.generate_report()
    report_path = f"scripts/benchmark_results/response_time_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    Path(report_path).parent.mkdir(parents=True, exist_ok=True)

    with open(report_path, "w") as f:
        f.write(report)

    print(f"\n📊 Report saved to: {report_path}")
    print("\n" + "=" * 70)
    print(report)
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
