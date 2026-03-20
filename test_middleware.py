#!/usr/bin/env python3
"""Test all middlewares via 50 interactions."""

import requests
import json
import asyncio

BASE_URL = "http://localhost:8000"

messages = [
    # 1-5: Basic interactions to trigger InstinctsMiddleware
    "hello",
    "what time is it",
    "add a todo: test task 1",
    "list my todos",
    "how are you",
    # 6-10: More interactions for context
    "search the web for AI news",
    "add a contact: John, john@email.com",
    "list my contacts",
    "what is 2+2",
    "good morning",
    # 11-15: File operations to test more tools
    "list files in /tmp",
    "create a file test.txt with hello world",
    "read the file test.txt",
    "add another todo: test task 2",
    "delete the file test.txt",
    # 16-20: More complex operations
    "search for python tutorials",
    "add contact: Jane, jane@company.com",
    "add todo: meeting at 3pm",
    "what can you do",
    "tell me about yourself",
    # 21-25: Continue building context
    "add todo: buy groceries",
    "list all todos",
    "search web for weather",
    "add contact: Bob, bob@work.com",
    "hello again",
    # 26-30: More for summarization trigger
    "tell me a story about a dragon",
    "search for latest tech news",
    "add todo: finish project",
    "list todos",
    "what is the time in London",
    # 31-35: Keep building
    "search for Python best practices",
    "add contact: Alice, alice@home.com",
    "add todo: call mom",
    "hello",
    "how does this work",
    # 36-40: More interactions
    "search for AI trends 2024",
    "add todo: learn flutter",
    "list todos",
    "what is 5+5",
    "good evening",
    # 41-45: Continue
    "search for database tutorials",
    "add contact: Carol, carol@social.com",
    "add todo: read a book",
    "hi there",
    "help me",
    # 46-50: Final push for summarization
    "search for machine learning news",
    "add todo: write code",
    "list my todos",
    "search for web dev tips",
    "goodbye",
]


async def send_message(msg: str, user_id: str, verbose: bool = True) -> dict:
    """Send a message and return the response."""
    url = f"{BASE_URL}/message/stream"
    data = {"message": msg, "user_id": user_id, "verbose": verbose}

    response = requests.post(url, json=data, stream=True)

    middleware_count = 0
    tool_count = 0
    ai_count = 0
    middleware_content = []

    for line in response.iter_lines():
        if line:
            line = line.decode("utf-8")
            if line.startswith("data: "):
                try:
                    chunk = json.loads(line[6:])
                    chunk_type = chunk.get("type")
                    content = chunk.get("content", "")

                    if chunk_type == "middleware":
                        middleware_count += 1
                        middleware_content.append(content[:50])
                    elif chunk_type == "tool":
                        tool_count += 1
                    elif chunk_type == "ai":
                        ai_count += 1
                except:
                    pass

    return {
        "message": msg,
        "middleware_count": middleware_count,
        "middleware_content": middleware_content,
        "tool_count": tool_count,
        "ai_count": ai_count,
    }


async def main():
    user_id = "middleware_test"

    print(f"Running 50 interactions to test all middlewares...")
    print("=" * 60)

    middleware_types = set()

    for i, msg in enumerate(messages, 1):
        print(f"\n[{i}/50] Sending: {msg[:40]}...")

        result = await send_message(msg, user_id)

        print(f"  Middleware events: {result['middleware_count']}")
        print(f"  Tool events: {result['tool_count']}")
        print(f"  AI chunks: {result['ai_count']}")

        # Track middleware types
        for mc in result["middleware_content"]:
            if "Starting:" in mc:
                middleware_types.add(mc.replace("Starting: ", ""))

        if result["middleware_count"] > 15:  # Lots of middleware = summarization triggered
            print(f"  ⚠️  HIGH MIDDLEWARE COUNT - summarization may have triggered!")

    print("\n" + "=" * 60)
    print("SUMMARY:")
    print(f"Total middleware types encountered: {len(middleware_types)}")
    print(f"Middleware types: {middleware_types}")

    # Final message to check if summarization is active
    print("\n" + "=" * 60)
    print("Final test - checking summarization...")
    result = await send_message("hello", user_id)
    print(f"Middleware events: {result['middleware_count']}")
    print(f"Middleware content: {result['middleware_content'][:10]}")


if __name__ == "__main__":
    asyncio.run(main())
