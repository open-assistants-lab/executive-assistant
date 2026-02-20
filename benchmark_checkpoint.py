"""Benchmark script to measure agent response time with checkpoint support."""

import asyncio
import time
import os
import sys
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.llm import create_model_from_config
from src.agents.factory import get_agent_factory
from src.storage.conversation import get_conversation_store
from src.storage.checkpoint import init_checkpoint_manager
from langchain_core.messages import HumanMessage, AIMessage


async def benchmark_conversation(message_count: int = 10, user_id: str = "benchmark"):
    """Benchmark agent with conversation history (simulates real usage)."""
    print(f"\n{'=' * 60}")
    print(f"Conversation Benchmark: {message_count} messages")
    print(f"{'=' * 60}\n")

    # Initialize storage
    conversation = get_conversation_store(user_id)

    # Initialize checkpoint manager
    checkpoint_manager = await init_checkpoint_manager(user_id)

    model = create_model_from_config()
    factory = get_agent_factory(checkpointer=checkpoint_manager.checkpointer)
    agent = factory.create(
        model=model,
        tools=[],
        system_prompt="You are a helpful assistant. Be concise.",
    )

    messages = []
    response_times = []

    test_messages = [
        "Hi, my name is John.",
        "What's my name?",
        "I'm interested in AI.",
        "What am I interested in?",
        "What's 2 + 2?",
        "What was the result of 2 + 2?",
        "Tell me a joke.",
        "Did you tell me a joke?",
        "What's the weather like?",
        "Thanks for the info!",
    ]

    for i in range(min(message_count, len(test_messages))):
        msg = test_messages[i]
        print(f"Message {i + 1}: {msg}")

        # Store user message
        conversation.add_message("user", msg)
        messages.append(HumanMessage(content=msg))

        start = time.time()
        config = {"configurable": {"thread_id": user_id}}
        result = await agent.ainvoke({"messages": messages}, config=config)
        elapsed = time.time() - start
        response_times.append(elapsed)

        response = result["messages"][-1].content
        messages.append(AIMessage(content=response))

        # Store assistant message
        conversation.add_message("assistant", response)

        print(f"  Response time: {elapsed:.2f}s")
        print(f"  Response: {response[:60]}...")
        print()

    avg = sum(response_times) / len(response_times)
    total = sum(response_times)

    print(f"{'=' * 60}")
    print(f"Results:")
    print(f"  Total messages: {len(response_times)}")
    print(f"  Average response time: {avg:.2f}s")
    print(f"  Total time: {total:.2f}s")
    print(f"  Min: {min(response_times):.2f}s, Max: {max(response_times):.2f}s")
    print(f"{'=' * 60}\n")

    return {
        "avg": avg,
        "total": total,
        "min": min(response_times),
        "max": max(response_times),
        "times": response_times,
    }


async def main():
    print("=" * 60)
    print("Agent Response Time Benchmark (With Checkpoint)")
    print("=" * 60 + "\n")

    # Conversation benchmark (10 messages)
    result = await benchmark_conversation(10)

    print("=" * 60)
    print("Benchmark complete!")
    print("=" * 60)

    return result


if __name__ == "__main__":
    asyncio.run(main())
