"""Benchmark script to measure agent response time."""

import asyncio
import time
import os
import sys
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.llm import create_model_from_config
from src.agents.factory import get_agent_factory
from langchain_core.messages import HumanMessage


async def benchmark(message: str, iterations: int = 3):
    """Benchmark agent response time."""
    print(f"Benchmarking: '{message}'")
    print(f"Iterations: {iterations}\n")

    model = create_model_from_config()
    factory = get_agent_factory()
    agent = factory.create(
        model=model,
        tools=[],
        system_prompt="You are a helpful assistant. Be concise.",
    )

    times = []
    for i in range(iterations):
        start = time.time()
        result = await agent.ainvoke({"messages": [HumanMessage(content=message)]})
        elapsed = time.time() - start
        times.append(elapsed)
        response = result["messages"][-1].content
        print(f"  Run {i + 1}: {elapsed:.2f}s")
        print(f"  Response: {response[:80]}...")
        print()

    avg = sum(times) / len(times)
    print(f"Average: {avg:.2f}s")
    return avg


async def main():
    print("=" * 60)
    print("Agent Response Time Benchmark (v0.0.1 Baseline)")
    print("=" * 60 + "\n")

    # Simple query
    await benchmark("What is 2 + 2?", 3)

    # Moderate query
    await benchmark("Explain what AI is in one sentence.", 3)

    print("=" * 60)
    print("Baseline established!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
