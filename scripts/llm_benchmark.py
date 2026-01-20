"""LLM Provider & Model Benchmark - Test performance with realistic workloads."""

import asyncio
import time
import json
import sys
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from langchain_core.messages import HumanMessage, SystemMessage
from executive_assistant.config.llm_factory import LLMFactory
from benchmark_scenarios import SCENARIOS, get_scenario, get_all_scenarios


@dataclass
class BenchmarkResult:
    """Single benchmark result."""
    provider: str
    model: str
    scenario: str
    input_tokens: int
    output_tokens: int
    output_length: int
    total_time: float
    first_token_time: float | None  # Time to first token (TTFT)
    tokens_per_second: float
    cost_estimate: float | None
    error: str | None = None


class LLMBenchmark:
    """Benchmark LLM providers and models with realistic workloads."""

    def __init__(self, output_dir: str = None):
        self.results: list[BenchmarkResult] = []
        self.output_dir = Path(output_dir or "scripts/benchmark_results")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def run_single_benchmark(
        self,
        provider: str,
        model: str,
        scenario: dict,
    ) -> BenchmarkResult:
        """Run a single benchmark test."""
        print(f"\n🧪 Testing: {provider}/{model} - {scenario['name']}")

        # Create model instance
        try:
            llm = LLMFactory.create(provider=provider, model=model)
            model_name = llm.model_name if hasattr(llm, 'model_name') else model
        except Exception as e:
            print(f"❌ Failed to create model: {e}")
            return BenchmarkResult(
                provider=provider,
                model=model,
                scenario=scenario['name'],
                input_tokens=0,
                output_tokens=0,
                output_length=0,
                total_time=0,
                first_token_time=None,
                tokens_per_second=0,
                cost_estimate=None,
                error=str(e),
            )

        # Prepare messages
        messages = [
            SystemMessage(content=scenario['system_prompt']),
            HumanMessage(content=scenario['user_message']),
        ]

        # Measure performance
        start_time = time.time()
        first_token_time = None

        try:
            # Stream response to measure TTFT
            response_chunks = []
            chunk_count = 0

            print(f"   Starting request at {datetime.now().strftime('%H:%M:%S')}...")

            async for chunk in llm.astream(messages):
                chunk_count += 1
                if first_token_time is None:
                    first_token_time = time.time() - start_time
                    print(f"   First token: {first_token_time:.2f}s")

                # Extract content from chunk
                if hasattr(chunk, 'content'):
                    response_chunks.append(chunk.content)
                elif hasattr(chunk, ' generations'):
                    for gen in chunk.generations:
                        if hasattr(gen, 'text'):
                            response_chunks.append(gen.text)
                        elif hasattr(gen, 'content'):
                            response_chunks.append(gen.content)

            total_time = time.time() - start_time

            # Combine output
            output_text = "".join(str(c) for c in response_chunks)
            output_length = len(output_text)

            # Estimate tokens
            input_tokens = scenario.get('estimated_input_tokens', 0)
            output_tokens = len(output_text) // 4  # Rough estimate: 4 chars per token

            tokens_per_second = output_tokens / total_time if total_time > 0 else 0

            # Estimate cost
            cost_estimate = self._estimate_cost(provider, model_name, input_tokens, output_tokens)

            print(f"   ✅ Total: {total_time:.2f}s | TTFT: {first_token_time:.2f}s | {tokens_per_second:.0f} tok/s | Out: {output_tokens} tokens")

            return BenchmarkResult(
                provider=provider,
                model=model,
                scenario=scenario['name'],
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                output_length=output_length,
                total_time=total_time,
                first_token_time=first_token_time,
                tokens_per_second=tokens_per_second,
                cost_estimate=cost_estimate,
                error=None,
            )

        except Exception as e:
            print(f"   ❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return BenchmarkResult(
                provider=provider,
                model=model,
                scenario=scenario['name'],
                input_tokens=0,
                output_tokens=0,
                output_length=0,
                total_time=0,
                first_token_time=None,
                tokens_per_second=0,
                cost_estimate=None,
                error=str(e),
            )

    def _estimate_cost(self, provider: str, model: str, input_tokens: int, output_tokens: int) -> float:
        """Estimate API call cost in USD."""
        # Pricing per 1M tokens (as of 2025-01)
        pricing = {
            # OpenAI
            "gpt-4o": {"input": 2.50, "output": 10.00},
            "gpt-4o-mini": {"input": 0.15, "output": 0.60},
            "gpt-4o-mini-real": {"input": 0.15, "output": 0.60},
            "gpt-5-mini": {"input": 0.20, "output": 0.80},  # Estimated
            "gpt-5-mini-2025-08-07": {"input": 0.20, "output": 0.80},  # Estimated
            "gpt-5-nano": {"input": 0.10, "output": 0.40},   # Estimated
            "gpt-5-nano-2025-08-07": {"input": 0.10, "output": 0.40},  # Estimated
            "o1-preview": {"input": 15.00, "output": 60.00},
            "o1-mini": {"input": 1.10, "output": 4.40},

            # Anthropic
            "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
            "claude-haiku-4-20250514": {"input": 0.25, "output": 1.25},

            # Zhipu
            "glm-4-plus": {"input": 0.70, "output": 0.70},
            "glm-4-flash": {"input": 0.10, "output": 0.10},

            # Ollama (free)
            "ollama": {"input": 0, "output": 0},
            "deepseek": {"input": 0, "output": 0},
        }

        # Find matching pricing
        rate = pricing.get(model, pricing.get("ollama", {"input": 0, "output": 0}))

        input_cost = (input_tokens / 1_000_000) * rate["input"]
        output_cost = (output_tokens / 1_000_000) * rate["output"]

        return input_cost + output_cost

    async def run_full_benchmark(
        self,
        providers: list[str] | None = None,
        models: list[str] | None = None,
        scenarios: list[str] | None = None,
        iterations: int = 1,
    ) -> None:
        """Run comprehensive benchmark."""
        providers = providers or ["openai"]
        models = models or ["default"]
        scenarios_to_test = scenarios or ["simple_qa"]

        print("=" * 70)
        print("🚀 LLM Benchmark - Executive Assistant Performance Testing")
        print("=" * 70)
        print(f"Providers: {', '.join(providers)}")
        print(f"Models: {', '.join(models)}")
        print(f"Scenarios: {', '.join(scenarios_to_test)}")
        print(f"Iterations: {iterations}")
        print(f"Output: {self.output_dir}")
        print("=" * 70)

        # Run benchmarks
        for provider in providers:
            for model in models:
                for scenario_name in scenarios_to_test:
                    scenario = get_scenario(scenario_name)
                    if not scenario:
                        print(f"⚠️  Unknown scenario: {scenario_name}")
                        continue

                    for i in range(iterations):
                        if iterations > 1:
                            print(f"\n   Iteration {i+1}/{iterations}")

                        result = await self.run_single_benchmark(provider, model, scenario)
                        self.results.append(result)

        # Generate report
        self._generate_report()

    def _generate_report(self) -> None:
        """Generate benchmark report."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save JSON results
        json_path = self.output_dir / f"{timestamp}_results.json"

        # Convert results to dict for JSON serialization
        results_dict = [asdict(r) for r in self.results]

        with open(json_path, "w") as f:
            json.dump(results_dict, f, indent=2)

        # Generate markdown report
        report_path = self.output_dir / f"{timestamp}_report.md"
        report = self._generate_markdown_report()

        with open(report_path, "w") as f:
            f.write(report)

        print(f"\n{'=' * 70}")
        print(f"📊 Results saved:")
        print(f"   JSON: {json_path}")
        print(f"   Report: {report_path}")
        print(f"{'=' * 70}")

    def _generate_markdown_report(self) -> str:
        """Generate markdown report from results."""
        lines = []
        lines.append("# LLM Benchmark Report\n")
        lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        lines.append(f"**Total Tests:** {len(self.results)}\n")
        lines.append("---\n")

        # Filter successful results
        successful = [r for r in self.results if not r.error]
        failed = [r for r in self.results if r.error]

        # Summary table
        lines.append("## Summary by Provider/Model\n")

        if successful:
            # Group by provider/model
            grouped = {}
            for r in successful:
                key = f"{r.provider}/{r.model}"
                if key not in grouped:
                    grouped[key] = []
                grouped[key].append(r)

            lines.append("| Provider/Model | Tests | Avg Time (s) | Avg TTFT (s) | Avg tok/s | Avg Cost |")
            lines.append("|---|---|---|---|---|---|")

            for key in sorted(grouped.keys()):
                results = grouped[key]
                avg_time = sum(r.total_time for r in results) / len(results)
                avg_ttft = sum(r.first_token_time or 0 for r in results) / len(results)
                avg_tps = sum(r.tokens_per_second for r in results) / len(results)
                avg_cost = sum(r.cost_estimate or 0 for r in results) / len(results)

                lines.append(
                    f"| {key} | {len(results)} | {avg_time:.2f} | {avg_ttft:.2f} | "
                    f"{avg_tps:.0f} | ${avg_cost:.4f} |"
                )

        lines.append("\n---\n")

        # Detailed results by scenario
        lines.append("## Detailed Results by Scenario\n")

        scenario_names = sorted(set(r.scenario for r in self.results))

        for scenario_name in scenario_names:
            lines.append(f"### {scenario_name}\n")

            scenario = get_scenario(scenario_name)
            if scenario:
                lines.append(f"**Complexity:** {scenario['complexity']}\n")
                lines.append(f"**Description:** {scenario['description']}\n")
                lines.append(f"**Expected Tools:** {', '.join(scenario.get('expected_tools', []))}\n")
                lines.append(f"**Estimated Input Tokens:** ~{scenario.get('estimated_input_tokens', 0)}\n")
                lines.append("\n")

            lines.append("| Provider/Model | Time (s) | TTFT (s) | In Tok | Out Tok | tok/s | Cost | Status |")
            lines.append("|---|---|---|---|---|---|---|---|")

            # Sort results by model within this scenario
            scenario_results = [r for r in self.results if r.scenario == scenario_name]
            scenario_results.sort(key=lambda x: (x.provider, x.model))

            for r in scenario_results:
                if r.error:
                    lines.append(
                        f"| {r.provider}/{r.model} | - | - | - | - | - | - | ❌ {r.error[:50]}... |"
                    )
                else:
                    lines.append(
                        f"| {r.provider}/{r.model} | {r.total_time:.2f} | {r.first_token_time:.2f} | "
                        f"{r.input_tokens} | {r.output_tokens} | {r.tokens_per_second:.0f} | "
                        f"${r.cost_estimate:.4f} | ✅ |"
                    )

            lines.append("\n")

        # Recommendations
        lines.append("## Recommendations\n")
        lines.append(self._generate_recommendations())

        # Failed tests
        if failed:
            lines.append("\n---\n")
            lines.append("## Failed Tests\n")
            lines.append("| Provider/Model | Scenario | Error |")
            lines.append("|---|---|---|")
            for r in failed:
                lines.append(f"| {r.provider}/{r.model} | {r.scenario} | {r.error[:100]}... |")

        return "\n".join(lines)

    def _generate_recommendations(self) -> str:
        """Generate recommendations based on results."""
        lines = []

        successful = [r for r in self.results if not r.error]

        if not successful:
            return "⚠️  No successful benchmarks to analyze.\n"

        # Find fastest overall
        fastest = min(successful, key=lambda r: r.total_time)
        lines.append(f"⚡ **Fastest Single Test:** {fastest.provider}/{fastest.model}\n")
        lines.append(f"   - Scenario: {fastest.scenario}\n")
        lines.append(f"   - Time: {fastest.total_time:.2f}s\n")
        lines.append(f"   - TTFT: {fastest.first_token_time:.2f}s\n")
        lines.append(f"   - Speed: {fastest.tokens_per_second:.0f} tokens/second\n\n")

        # Find best TTFT (time to first token)
        if successful:
            best_ttft = min(successful, key=lambda r: r.first_token_time or 999)
            lines.append(f"🚀 **Best Time to First Token:** {best_ttft.provider}/{best_ttft.model}\n")
            lines.append(f"   - TTFT: {best_ttft.first_token_time:.2f}s (critical for UX)\n\n")

        # Find best value (time vs cost)
        if successful and any(r.cost_estimate for r in successful):
            best_value = min(
                [r for r in successful if r.cost_estimate],
                key=lambda r: (r.total_time, r.cost_estimate)
            )
            lines.append(f"💰 **Best Value:** {best_value.provider}/{best_value.model}\n")
            lines.append(f"   - Time: {best_value.total_time:.2f}s\n")
            lines.append(f"   - Cost: ${best_value.cost_estimate:.4f} per call\n\n")

        # Analyze GPT-5 Mini specifically
        gpt5_results = [r for r in successful if "gpt-5" in r.model.lower()]
        if gpt5_results:
            avg_gpt5_time = sum(r.total_time for r in gpt5_results) / len(gpt5_results)
            avg_gpt5_ttft = sum(r.first_token_time or 0 for r in gpt5_results) / len(gpt5_results)

            lines.append(f"📊 **GPT-5 Mini Analysis:**\n")
            lines.append(f"- Average response time: {avg_gpt5_time:.2f}s\n")
            lines.append(f"- Average TTFT: {avg_gpt5_ttft:.2f}s\n")
            lines.append(f"- Tests completed: {len(gpt5_results)}\n\n")

            if avg_gpt5_time > 10:
                lines.append(f"⚠️  **WARNING:** GPT-5 Mini is slow ({avg_gpt5_time:.2f}s average)!\n")
                lines.append(f"   Consider switching to a faster model.\n\n")

            # Compare to alternatives
            other_results = [r for r in successful if "gpt-5" not in r.model.lower()]
            if other_results:
                avg_other_time = sum(r.total_time for r in other_results) / len(other_results)
                speedup = avg_gpt5_time / avg_other_time

                if speedup > 2:
                    lines.append(f"💡 **Alternatives are {speedup:.1f}x faster** on average!\n\n")

        # Complexity analysis
        simple_results = [r for r in successful if get_scenario(r.scenario) and get_scenario(r.scenario).get('complexity') == 'simple']
        complex_results = [r for r in successful if get_scenario(r.scenario) and get_scenario(r.scenario).get('complexity') == 'complex']

        if simple_results and complex_results:
            avg_simple = sum(r.total_time for r in simple_results) / len(simple_results)
            avg_complex = sum(r.total_time for r in complex_results) / len(complex_results)

            lines.append(f"📈 **Complexity Impact:**\n")
            lines.append(f"- Simple scenarios: {avg_simple:.2f}s average\n")
            lines.append(f"- Complex scenarios: {avg_complex:.2f}s average\n")
            lines.append(f"- Overhead: {avg_complex / avg_simple:.1f}x slower for complex tasks\n\n")

        return "\n".join(lines)


def main():
    """Run benchmark from command line."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Benchmark LLM providers and models",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Quick test: GPT-5 Mini only
  python scripts/llm_benchmark.py --providers openai --models gpt-5-mini-2025-08-07

  # Compare OpenAI models
  python scripts/llm_benchmark.py --providers openai --models gpt-4o gpt-4o-mini gpt-5-mini-2025-08-07

  # Full benchmark
  python scripts/llm_benchmark.py --providers openai anthropic --iterations 3
        """
    )

    parser.add_argument(
        "--providers",
        nargs="+",
        default=["openai"],
        help="Providers to test (openai, anthropic, zhipu)",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=["default"],
        help="Models to test (default, fast, or specific model names)",
    )
    parser.add_argument(
        "--scenarios",
        nargs="+",
        default=["simple_qa"],
        help="Scenarios to test",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=1,
        help="Iterations per test (default: 1)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="scripts/benchmark_results",
        help="Output directory for results",
    )

    args = parser.parse_args()

    # Run benchmark
    benchmark = LLMBenchmark(output_dir=args.output_dir)
    asyncio.run(benchmark.run_full_benchmark(
        providers=args.providers,
        models=args.models,
        scenarios=args.scenarios,
        iterations=args.iterations,
    ))


if __name__ == "__main__":
    main()
