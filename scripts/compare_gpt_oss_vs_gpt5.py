#!/usr/bin/env python3
"""
Compare GPT-OSS (Ollama Cloud) vs GPT-5.1 Mini (OpenAI API)
Fair comparison with timing metrics
"""

import time
import os
import asyncio
from statistics import mean, median, stdev
from datetime import datetime
from openai import AsyncOpenAI
import subprocess
import json
from dotenv import load_dotenv
from anthropic import AsyncAnthropic

# Load environment variables from .env file
load_dotenv()


def print_result(result: dict):
    """Print individual result"""
    if result.get("success"):
        print(f"\n✓ Success")
        print(f"  Time: {result['total_time']:.3f}s")
        response = result.get('response', '')
        print(f"  Response: {response[:100]}{'...' if len(response) > 100 else ''}")
    else:
        print(f"\n✗ Failed")
        print(f"  Error: {result.get('error', 'Unknown error')}")


class LLMBenchmark:
    def __init__(self):
        self.openai_client = None
        self.anthropic_client = None

        if os.environ.get("OPENAI_API_KEY"):
            self.openai_client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])

        if os.environ.get("ANTHROPIC_API_KEY"):
            self.anthropic_client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    def test_ollama_model(self, model: str, prompt: str) -> dict:
        """Test Ollama Cloud model"""
        print(f"\n{'='*60}")
        print(f"Testing: {model} via Ollama Cloud")
        print(f"{'='*60}")

        start = time.time()
        try:
            result = subprocess.run(
                ["ollama", "run", model, prompt],
                capture_output=True,
                text=True,
                timeout=60
            )
            end = time.time()

            # Extract actual response (remove control codes)
            response = result.stdout

            return {
                "model": model,
                "prompt": prompt,
                "response": response.strip(),
                "total_time": end - start,
                "success": result.returncode == 0,
                "timestamp": datetime.now().isoformat()
            }
        except subprocess.TimeoutExpired:
            return {
                "model": model,
                "prompt": prompt,
                "error": "Timeout",
                "total_time": 60,
                "success": False
            }

    async def test_openai_model(self, model: str, prompt: str, max_tokens: int = 100) -> dict:
        """Test OpenAI API model"""
        print(f"\n{'='*60}")
        print(f"Testing: {model} via OpenAI API")
        print(f"{'='*60}")

        start = time.time()
        try:
            response = await self.openai_client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_completion_tokens=max_tokens,
                temperature=1  # GPT-5 Mini only supports temperature=1
            )
            end = time.time()

            content = response.choices[0].message.content

            # Extract timing info if available
            usage = response.usage.model_dump() if response.usage else {}

            return {
                "model": model,
                "prompt": prompt,
                "response": content.strip(),
                "total_time": end - start,
                "usage": usage,
                "success": True,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            end = time.time()
            return {
                "model": model,
                "prompt": prompt,
                "error": str(e),
                "total_time": end - start,
                "success": False
            }

    async def test_anthropic_model(self, model: str, prompt: str, max_tokens: int = 100) -> dict:
        """Test Anthropic API model"""
        print(f"\n{'='*60}")
        print(f"Testing: {model} via Anthropic API")
        print(f"{'='*60}")

        start = time.time()
        try:
            response = await self.anthropic_client.messages.create(
                model=model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}]
            )
            end = time.time()

            content = response.content[0].text

            # Extract usage info
            usage = response.usage.model_dump() if hasattr(response, 'usage') else {}

            return {
                "model": model,
                "prompt": prompt,
                "response": content.strip(),
                "total_time": end - start,
                "usage": usage,
                "success": True,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            end = time.time()
            return {
                "model": model,
                "prompt": prompt,
                "error": str(e),
                "total_time": end - start,
                "success": False
            }

    async def run_comparison_suite(self):
        """Run comprehensive comparison"""

        test_scenarios = [
            {
                "name": "Simple Q&A",
                "prompt": "What is the capital of France? Answer in one word."
            },
            {
                "name": "Math",
                "prompt": "What is 247 multiplied by 132? Just give me the number."
            },
            {
                "name": "Coding - Simple",
                "prompt": "Write a Python function to add two numbers."
            },
            {
                "name": "Explanation",
                "prompt": "Explain what a REST API is in 2-3 sentences."
            },
            {
                "name": "Creative",
                "prompt": "Tell me a short joke about programming."
            }
        ]

        results = {
            "ollama": {
                "gpt-oss:20b-cloud": []
            },
            "anthropic": {
                "claude-haiku-4-5": []
            }
        }

        print("\n" + "="*80)
        print("LLM COMPARISON: GPT-OSS (Ollama Cloud) vs Claude Haiku 4.5 (Anthropic API)")
        print("="*80)
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # Test each scenario
        for scenario in test_scenarios:
            print(f"\n\n{'#'*80}")
            print(f"# SCENARIO: {scenario['name']}")
            print(f"# Prompt: {scenario['prompt']}")
            print(f"{'#'*80}")

            # Test GPT-OSS 20B
            result_20b = self.test_ollama_model("gpt-oss:20b-cloud", scenario['prompt'])
            results["ollama"]["gpt-oss:20b-cloud"].append(result_20b)
            print_result(result_20b)

            time.sleep(1)  # Brief pause

            # Test Claude Haiku 4.5 (if API key available)
            if self.anthropic_client:
                result_haiku = await self.test_anthropic_model("claude-haiku-4-5", scenario['prompt'], max_tokens=500)
                results["anthropic"]["claude-haiku-4-5"].append(result_haiku)
                print_result(result_haiku)

            time.sleep(2)  # Pause between scenarios

        # Calculate statistics
        print(f"\n\n{'='*80}")
        print("SUMMARY STATISTICS")
        print(f"{'='*80}\n")

        for provider, models in results.items():
            for model, model_results in models.items():
                if not model_results:
                    continue

                successful = [r for r in model_results if r["success"]]
                failed = [r for r in model_results if not r["success"]]

                if successful:
                    times = [r["total_time"] for r in successful]
                    print(f"\n{model} ({provider}):")
                    print(f"  Success rate: {len(successful)}/{len(model_results)} ({len(successful)/len(model_results)*100:.1f}%)")
                    print(f"  Average time: {mean(times):.3f}s")
                    print(f"  Median time:  {median(times):.3f}s")
                    print(f"  Min time:     {min(times):.3f}s")
                    print(f"  Max time:     {max(times):.3f}s")
                    if len(times) > 1:
                        print(f"  Std deviation: {stdev(times):.3f}s")

                    if failed:
                        print(f"  Failed: {len(failed)}")

        # Save results
        output_file = f"llm_comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)

        print(f"\n\nResults saved to: {output_file}")

        return results


async def main():
    benchmark = LLMBenchmark()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("⚠️  ANTHROPIC_API_KEY not set - will only test Ollama Cloud models")
        print("   Set it with: export ANTHROPIC_API_KEY='your-key-here'")

    await benchmark.run_comparison_suite()


if __name__ == "__main__":
    asyncio.run(main())
