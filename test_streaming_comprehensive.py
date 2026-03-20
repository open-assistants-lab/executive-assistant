#!/usr/bin/env python3
"""Comprehensive streaming test with multiple personas, tools, middlewares, and subagents."""

import asyncio
import json
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass
class TestResult:
    """Result of a single test case."""

    persona: str
    message: str
    success: bool
    types_seen: set = field(default_factory=set)
    namespaces_seen: set = field(default_factory=set)
    chunk_count: int = 0
    error: str = ""


async def run_streaming_test(message: str, user_id: str, verbose: bool = True) -> TestResult:
    """Run a single streaming test."""
    result = TestResult(persona=user_id, message=message, success=False)

    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            async with client.stream(
                "POST",
                "http://localhost:8000/message/stream",
                json={"message": message, "user_id": user_id, "verbose": verbose},
            ) as response:
                if response.status_code != 200:
                    result.error = f"HTTP {response.status_code}"
                    return result

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        result.chunk_count += 1
                        try:
                            data = json.loads(line[6:])
                            chunk_type = data.get("type")
                            ns = data.get("ns", "")

                            if chunk_type:
                                result.types_seen.add(chunk_type)
                            if ns:
                                result.namespaces_seen.add(ns)
                        except json.JSONDecodeError:
                            pass

                result.success = result.chunk_count > 0

        except Exception as e:
            result.error = str(e)

    return result


# Test cases designed to trigger different features
PERSONA_TESTS = {
    "p1_direct": [
        # Basic greeting - triggers middleware
        "hello",
        "hi there",
        # Time tool
        "what time is it in tokyo",
        "time in london",
        "what's the time in sydney",
        # Files tool
        "list files in current directory",
        "list files in src",
        "search for python files",
        # Contacts tool
        "list my contacts",
        "find contact john",
        # Todos tool
        "list my todos",
        "show my tasks",
        # Multiple tools
        "list files AND show todos",
        "get time in tokyo AND list contacts",
        # Subagent trigger
        "create a subagent to help with testing",
    ],
    "p2_polite": [
        # Greeting
        "hello, how are you?",
        "good morning!",
        # Time tool
        "could you please tell me the time in paris?",
        "what time is it in new york please?",
        # Files tool
        "would you be so kind as to list my files?",
        "please show me what files are available",
        # Contacts
        "could you help me find a contact named john?",
        "i would like to see my contacts please",
        # Todos
        "please show my todo list",
        "could you list my pending tasks?",
        # Multiple tools
        "list my files and also show the time in tokyo",
        # Subagent
        "i need help managing my tasks, can you create a subagent?",
    ],
    "p3_casual": [
        # Greeting
        "hey",
        "what's up",
        # Time tool
        "hey what time is it in tokyo?",
        "time in berlin plz",
        # Files tool
        "list files plz",
        "show me the files",
        # Contacts
        "find john",
        "show contacts",
        # Todos
        "show todos",
        "what tasks do i have?",
        # Multiple tools
        "list files AND get time",
        # Subagent
        "make a subagent for me",
    ],
    "p4_questioning": [
        # Greeting
        "hi, how can you help me today?",
        # Time tool
        "can you tell me what time it is? which cities can you check?",
        # Files tool
        "what files can you show me? how do i list them?",
        # Contacts
        "how do i find contacts? can you show me who i have?",
        # Todos
        "what are my tasks? how do i see them?",
        # More questioning
        "can you help me with files AND time at the same time?",
        # Subagent
        "what's a subagent? can you create one for me?",
        # Tools with questions
        "could you list my emails? which email provider do you support?",
        "find my contacts - do you need a name to search?",
    ],
    "p5_storytelling": [
        # Greeting
        "hi! i've been using your assistant for a while now",
        # Time tool
        "i remember i used to live in tokyo, what's the time there now?",
        "i have a meeting in london tomorrow, what's the time there?",
        # Files tool
        "i've been working on some documents, can you list them?",
        "i created some files in the src folder, can you show them?",
        # Contacts
        "i met this person named john last week, can you find them?",
        "i have some contacts saved, can you show them to me?",
        # Todos
        "i have some tasks to complete, can you list them?",
        "i've been meaning to organize my work, show my todos?",
        # Multiple
        "i need to check my files and also know the time in tokyo for my meeting",
        # Subagent
        "i need help managing all these tasks, can you create a subagent to assist me?",
    ],
}


def analyze_result(result: TestResult) -> dict[str, Any]:
    """Analyze a test result and return findings."""
    findings = {
        "has_messages": "messages" in result.types_seen,
        "has_updates": "updates" in result.types_seen,
        "has_custom": "custom" in result.types_seen,
        "middlewares": [],
        "tools": [],
        "agents": [],
    }

    # Categorize namespaces
    for ns in result.namespaces_seen:
        if "Middleware" in ns:
            findings["middlewares"].append(ns)
        elif ns in ["list_files", "files_glob_search", "time_get", "list_contacts", "todos_list"]:
            findings["tools"].append(ns)
        elif "agent" in ns.lower():
            findings["agents"].append(ns)

    return findings


async def main():
    """Run comprehensive streaming tests."""
    print("=" * 70)
    print("COMPREHENSIVE STREAMING TEST")
    print("=" * 70)

    total_tests = 0
    passed_tests = 0
    all_results = []

    # Track all middleware/tool/agent namespaces
    all_middlewares = set()
    all_tools = set()
    all_agents = set()

    for persona, messages in PERSONA_TESTS.items():
        print(f"\n{'=' * 70}")
        print(f"PERSONA: {persona}")
        print(f"{'=' * 70}")

        for i, message in enumerate(messages, 1):
            print(f"\n[{i}/{len(messages)}] {message[:50]}...")

            result = await run_streaming_test(message, f"test_{persona}")
            total_tests += 1

            if result.success:
                passed_tests += 1
                findings = analyze_result(result)

                all_middlewares.update(findings["middlewares"])
                all_tools.update(findings["tools"])
                all_agents.update(findings["agents"])

                print(f"   ✅ Chunks: {result.chunk_count}")
                print(f"   Types: {sorted(result.types_seen)}")
                print(f"   Middlewares: {len(findings['middlewares'])}")
                print(f"   Tools: {len(findings['tools'])}")
                print(f"   Agents: {len(findings['agents'])}")
            else:
                print(f"   ❌ Error: {result.error}")

            all_results.append((persona, message, result))

            # Small delay between requests
            await asyncio.sleep(0.5)

    # Summary
    print(f"\n{'=' * 70}")
    print("SUMMARY")
    print(f"{'=' * 70}")
    print(f"\nTotal tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {total_tests - passed_tests}")
    print(f"Success rate: {passed_tests / total_tests * 100:.1f}%")

    print(f"\n--- All Middlewares Found ---")
    for m in sorted(all_middlewares):
        print(f"  - {m}")

    print(f"\n--- All Tools Found ---")
    for t in sorted(all_tools):
        print(f"  - {t}")

    print(f"\n--- All Agents Found ---")
    for a in sorted(all_agents):
        print(f"  - {a}")

    # Verify key features
    print(f"\n--- Feature Verification ---")
    features = {
        "messages type": len([r for r in all_results if "messages" in r[2].types_seen]),
        "updates type": len([r for r in all_results if "updates" in r[2].types_seen]),
        "custom type": len([r for r in all_results if "custom" in r[2].types_seen]),
        "middleware events": len(all_middlewares),
        "tool calls": len(all_tools),
        "subagents": len(all_agents),
    }

    for feature, count in features.items():
        status = "✅" if count > 0 else "❌"
        print(f"  {status} {feature}: {count}")

    # Check for specific middlewares we expect
    expected_middlewares = [
        "SkillMiddleware",
        "InstinctsMiddleware",
        "SummarizationMiddleware",
        "HumanInTheLoopMiddleware",
    ]

    print(f"\n--- Expected Middlewares ---")
    for m in expected_middlewares:
        found = any(m in mid for mid in all_middlewares)
        status = "✅" if found else "❌"
        print(f"  {status} {m}: {'found' if found else 'NOT found'}")

    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
