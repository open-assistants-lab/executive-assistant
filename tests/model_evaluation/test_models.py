#!/usr/bin/env python3
"""
Model Evaluation Test Suite for Executive Assistant

Tests multiple models via Ollama Cloud on:
- Conversational Quality
- Instruction Following
- Information Extraction
- Response Relevance
- Tool Usage Accuracy
- Performance (latency, tokens)
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Any, Dict, List
from datetime import datetime

import httpx


# Models to test
MODELS = [
    "gpt-oss:20b-cloud",      # Baseline
    "kimi-k2.5:cloud",
    "minimax-m2.1:cloud",
    "deepseek-v3.2:cloud",
    "qwen3-next:80b-cloud",
]

# Test scenarios
SCENARIOS = {
    "scenario_1_simple_onboarding": {
        "name": "Simple Onboarding",
        "description": "Test basic onboarding flow with 'hi' message",
        "user_message": "hi",
        "user_id": "test_eval_user_1",
        "expected_behaviors": [
            "Welcomes user warmly",
            "Introduces agent (I'm Ken/I'm your assistant)",
            "Asks about role/goals",
            "Explains why asking (to help you better)",
        ],
        "metrics": ["conversational_quality", "instruction_following", "response_time", "token_usage"],
    },
    "scenario_2_role_onboarding": {
        "name": "Role-Based Onboarding",
        "description": "Test information extraction with specific role",
        "user_message": "I'm a data analyst. I need to track my daily work logs.",
        "user_id": "test_eval_user_2",
        "expected_behaviors": [
            "Extracts role: 'data analyst'",
            "Identifies goal: 'track daily work logs'",
            "Suggests relevant tools (database, reminders, etc.)",
            "Asks if user wants to proceed",
        ],
        "metrics": ["info_extraction", "response_relevance", "suggestion_quality"],
    },
    "scenario_3_tool_creation": {
        "name": "Tool Creation",
        "description": "Test if model can create tools correctly",
        "user_message": "Yes please create it",
        "user_id": "test_eval_user_2",  # Continue conversation
        "expected_behaviors": [
            "Attempts to create database/table",
            "Uses create_tdb_table tool",
            "Provides appropriate schema",
            "Handles errors gracefully",
        ],
        "metrics": ["tool_usage_accuracy", "reasoning_quality", "instruction_following"],
    },
}


class ModelEvaluator:
    """Evaluate models on test scenarios."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.results = []

    async def test_scenario(
        self,
        model: str,
        scenario_id: str,
        scenario: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Test a single model on a single scenario."""
        print(f"\n{'='*60}")
        print(f"Testing: {model} - {scenario['name']}")
        print(f"{'='*60}")

        start_time = time.time()

        try:
            # Send message to agent
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.base_url}/message",
                    json={
                        "content": scenario["user_message"],
                        "user_id": scenario["user_id"],
                        "stream": False,
                    },
                )

                if response.status_code != 200:
                    return {
                        "model": model,
                        "scenario": scenario_id,
                        "error": f"HTTP {response.status_code}: {response.text}",
                        "success": False,
                    }

                data = response.json()
                elapsed = time.time() - start_time

                if not data or not isinstance(data, list):
                    return {
                        "model": model,
                        "scenario": scenario_id,
                        "error": f"Invalid response: {data}",
                        "success": False,
                    }

                # Extract assistant response
                assistant_message = data[0] if data else {}
                content = assistant_message.get("content", "")

                # Calculate tokens (rough estimate)
                input_tokens = len(scenario["user_message"].split())
                output_tokens = len(content.split())
                total_tokens = input_tokens + output_tokens

                result = {
                    "model": model,
                    "scenario": scenario_id,
                    "success": True,
                    "response": content,
                    "response_time": round(elapsed, 2),
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": total_tokens,
                    "timestamp": datetime.now().isoformat(),
                }

                # Print response for manual evaluation
                print(f"\nResponse ({elapsed:.2f}s, {total_tokens} tokens):")
                print("-" * 60)
                print(content)
                print("-" * 60)

                return result

        except Exception as e:
            return {
                "model": model,
                "scenario": scenario_id,
                "error": str(e),
                "success": False,
                "response_time": round(time.time() - start_time, 2),
            }

    async def test_model(self, model: str, scenarios: List[str] = None) -> List[Dict[str, Any]]:
        """Test a model on multiple scenarios."""
        if scenarios is None:
            scenarios = ["scenario_1_simple_onboarding"]

        results = []
        for scenario_id in scenarios:
            scenario = SCENARIOS[scenario_id]
            result = await self.test_scenario(model, scenario_id, scenario)
            results.append(result)

        return results

    def save_results(self, results: List[Dict[str, Any]], output_path: str = "model_evaluation_results.json"):
        """Save results to JSON file."""
        output_file = Path(output_path)
        output_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"\nResults saved to {output_file}")


async def main():
    """Run model evaluation tests."""
    import sys

    # Get model from command line argument
    if len(sys.argv) > 1:
        models_to_test = [sys.argv[1]]
    else:
        models_to_test = MODELS

    evaluator = ModelEvaluator()

    # Test Scenario 1 across specified models
    print("\n" + "="*60)
    print(f"PHASE 1: Testing Scenario 1 (Simple Onboarding)")
    print(f"Models: {', '.join(models_to_test)}")
    print("="*60)

    all_results = []
    for model in models_to_test:
        results = await evaluator.test_model(model, ["scenario_1_simple_onboarding"])
        all_results.extend(results)

    # Save results
    evaluator.save_results(all_results)

    # Print summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    for result in all_results:
        model = result["model"]
        scenario = result["scenario"]
        success = result["success"]
        response_time = result.get("response_time", "N/A")
        tokens = result.get("total_tokens", "N/A")

        status = "✅ PASS" if success else "❌ FAIL"
        print(f"\n{model} | {scenario}")
        print(f"  Status: {status}")
        print(f"  Time: {response_time}s | Tokens: {tokens}")

        if "error" in result:
            print(f"  Error: {result['error']}")


if __name__ == "__main__":
    asyncio.run(main())
