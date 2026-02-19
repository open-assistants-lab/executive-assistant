"""Test script to verify agent works with Ollama cloud."""

import asyncio
import os
import sys
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from langchain_core.messages import HumanMessage
from src.llm import create_model_from_config
from src.agents.factory import get_agent_factory


async def test_agent():
    """Test the agent with Ollama."""
    print("Testing Executive Assistant...")

    try:
        # Create model
        model = create_model_from_config()
        print(f"✓ Model: {model}")

        # Get agent factory
        factory = get_agent_factory()

        # Create agent
        agent = factory.create(
            model=model,
            tools=[],
            system_prompt="You are a helpful executive assistant.",
        )
        print("✓ Agent created")

        # Test message
        result = await agent.ainvoke(
            {"messages": [HumanMessage(content="Say 'Hello, I work!' in exactly 3 words.")]}
        )

        print(f"✓ Response: {result['messages'][-1].content}")
        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback

        traceback.print_exc()
        return False


async def main():
    ok = await test_agent()
    print("\n" + "=" * 50)
    print("PASS" if ok else "FAIL")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
