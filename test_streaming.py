#!/usr/bin/env python3
"""Test streaming output format against LangChain specification."""

import asyncio
import json
import sys

import httpx


async def test_streaming():
    """Test streaming output format."""

    base_url = "http://localhost:8000"
    user_id = "test_streaming"

    test_cases = [
        {
            "name": "Basic greeting",
            "message": "hello",
            "expected_types": ["custom", "messages"],
        },
        {
            "name": "Tool call (time)",
            "message": "what time is it in tokyo",
            "expected_types": ["custom", "messages", "updates"],
        },
        {
            "name": "Tool call (files)",
            "message": "list files in current directory",
            "expected_types": ["custom", "messages", "updates"],
        },
        {
            "name": "Multiple tools",
            "message": "what time is it in tokyo AND list files",
            "expected_types": ["custom", "messages", "updates"],
        },
    ]

    all_passed = True

    for test in test_cases:
        print(f"\n{'=' * 60}")
        print(f"TEST: {test['name']}")
        print(f"{'=' * 60}")
        print(f"Message: {test['message']}")

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                async with client.stream(
                    "POST",
                    f"{base_url}/message/stream",
                    json={
                        "message": test["message"],
                        "user_id": user_id,
                        "verbose": True,
                    },
                ) as response:
                    if response.status_code != 200:
                        print(f"❌ HTTP Error: {response.status_code}")
                        all_passed = False
                        continue

                    seen_types = set()
                    seen_ns = set()
                    chunk_count = 0

                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            chunk_count += 1
                            data = line[6:]  # Remove "data: "
                            try:
                                parsed = json.loads(data)
                                chunk_type = parsed.get("type")
                                ns = parsed.get("ns", "")
                                content = parsed.get("data", {}).get("content", "")

                                seen_types.add(chunk_type)
                                if ns:
                                    seen_ns.add(ns)

                                # Validate format
                                if chunk_type not in ["messages", "updates", "custom"]:
                                    print(f"❌ Unknown type: {chunk_type}")
                                    all_passed = False
                                elif not ns:
                                    print(f"❌ Missing ns: {parsed}")
                                    all_passed = False
                                elif "data" not in parsed:
                                    print(f"❌ Missing data: {parsed}")
                                    all_passed = False

                            except json.JSONDecodeError as e:
                                print(f"❌ JSON decode error: {e}")
                                all_passed = False

                    print(f"\n📊 Summary:")
                    print(f"   Total chunks: {chunk_count}")
                    print(f"   Types seen: {sorted(seen_types)}")
                    print(f"   Namespaces: {sorted(seen_ns)}")

                    # Check expected types
                    for expected in test["expected_types"]:
                        if expected not in seen_types:
                            print(f"❌ Missing expected type: {expected}")
                            all_passed = False
                        else:
                            print(f"✅ Type '{expected}' present")

            except Exception as e:
                print(f"❌ Request failed: {e}")
                all_passed = False

    print(f"\n{'=' * 60}")
    print(f"FINAL RESULT: {'✅ ALL PASSED' if all_passed else '❌ FAILED'}")
    print(f"{'=' * 60}")

    return all_passed


if __name__ == "__main__":
    result = asyncio.run(test_streaming())
    sys.exit(0 if result else 1)
