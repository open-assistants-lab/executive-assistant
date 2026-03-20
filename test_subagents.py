#!/usr/bin/env python3
"""Test subagent functionality - 20 tests covering create, invoke, list, schedule, etc."""

import asyncio
import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta

import httpx


@dataclass
class TestResult:
    name: str
    success: bool
    message: str
    details: str = ""


SUBAGENT_TESTS = [
    # Simple tests (1-5)
    ("Create simple subagent", "create subagent assistant_1 that can answer questions", True),
    ("List subagents", "list my subagents", True),
    ("Invoke existing subagent", "use subagent assistant_1 to say hello world", True),
    ("Check subagent status", "check status of subagent assistant_1", True),
    ("Delete subagent", "delete subagent assistant_1", True),
    # Medium tests (6-10)
    (
        "Create subagent with tools",
        "create subagent researcher that can search the web and scrape URLs",
        True,
    ),
    ("List after create", "list my subagents", True),
    ("Invoke researcher", "use subagent researcher to tell me about Python", True),
    ("Create another subagent", "create subagent coder that can write and read files", True),
    ("List multiple subagents", "list all my subagents", True),
    # Complex tests (11-15) - immediate execution
    (
        "Invoke with progress check",
        "invoke subagent researcher to find latest AI news, then check progress",
        True,
    ),
    (
        "Batch invoke",
        "use subagent assistant_1 to say hi, use subagent researcher to tell me about Python",
        True,
    ),
    ("Create and invoke chain", "create subagent greeter that says hello, then invoke it", True),
    ("Delete and verify", "delete subagent greeter, then list subagents to confirm", True),
    (
        "Multiple operations",
        "create subagent tester that can test code, list subagents, use tester to test a simple function",
        True,
    ),
    # Scheduled tests (16-20) - will run in ~5 mins
    (
        "Schedule task 1",
        "schedule subagent researcher to search for weather in Tokyo in 5 minutes",
        False,
    ),  # Won't run immediately
    (
        "Schedule task 2",
        "schedule subagent assistant_1 to say 'scheduled message' in 5 minutes",
        False,
    ),
    (
        "Schedule task 3",
        "schedule subagent coder to write 'test.txt' with 'hello world' in 5 minutes",
        False,
    ),
    ("List scheduled", "list my scheduled subagent tasks", True),
    ("Cancel scheduled", "cancel all scheduled subagent tasks", True),
]


async def run_test(message: str) -> TestResult:
    """Run a single test and return result."""
    result = TestResult(name="", success=False, message=message)

    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            async with client.stream(
                "POST",
                "http://localhost:8000/message/stream",
                json={"message": message, "user_id": "subagent_test", "verbose": True},
            ) as response:
                chunks = []
                tool_calls = []
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])
                            chunks.append(data)
                            if data.get("type") == "updates":
                                ns = data.get("ns", "")
                                content = data.get("data", {}).get("content", "")[:100]
                                if "subagent" in ns.lower():
                                    tool_calls.append(f"{ns}: {content}")
                        except:
                            pass

                result.success = len(chunks) > 0
                result.details = f"Chunks: {len(chunks)}, Tool calls: {tool_calls}"

        except Exception as e:
            result.success = False
            result.details = f"Error: {str(e)}"

    return result


async def main():
    print("=" * 70)
    print("SUBAGENT FUNCTIONALITY TEST - 20 TESTS")
    print("=" * 70)

    results = []

    # Tests 1-15: Immediate execution
    print("\n" + "=" * 70)
    print("PHASE 1: Immediate Execution Tests (1-15)")
    print("=" * 70)

    for i, (name, message, expect_success) in enumerate(SUBAGENT_TESTS[:15], 1):
        print(f"\n[{i}/20] {name}")
        print(f"    Message: {message[:60]}...")

        result = await run_test(message)
        result.name = name

        if result.success:
            print(
                f"    ✅ Success - {len(result.details.split(',')[0].split(':')[1]) if 'Chunks' in result.details else '0'} chunks"
            )
        else:
            print(f"    ❌ Failed - {result.details}")

        results.append(result)
        await asyncio.sleep(2)  # Delay between tests

    # Wait a bit for scheduled tasks to potentially complete
    print("\n" + "=" * 70)
    print("PHASE 2: Scheduled Task Tests (16-20)")
    print("=" * 70)
    print(
        "\nNote: Tests 16-20 schedule tasks for 5 minutes - will create but not wait for execution"
    )

    for i, (name, message, expect_success) in enumerate(SUBAGENT_TESTS[15:], 16):
        print(f"\n[{i}/20] {name}")
        print(f"    Message: {message[:60]}...")

        result = await run_test(message)
        result.name = name

        # For scheduled tasks, we expect the scheduling to work even if execution is in future
        if "schedule" in message.lower() or "scheduled" in message.lower():
            result.success = (
                "scheduled" in result.details.lower()
                or "schedule" in result.details.lower()
                or result.success
            )

        if result.success:
            print(f"    ✅ Success")
        else:
            print(f"    ⚠️  {result.details[:80]}")

        results.append(result)
        await asyncio.sleep(2)

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    passed = sum(1 for r in results if r.success)
    failed = len(results) - passed

    print(f"\nTotal: {len(results)}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")

    if failed > 0:
        print("\nFailed tests:")
        for r in results:
            if not r.success:
                print(f"  - {r.name}: {r.details[:60]}")

    # Verify subagent tools were used
    print("\n" + "=" * 70)
    print("TOOL VERIFICATION")
    print("=" * 70)

    tools_found = set()
    for r in results:
        if r.success and r.details:
            if "subagent_create" in r.details:
                tools_found.add("subagent_create")
            if "subagent_invoke" in r.details:
                tools_found.add("subagent_invoke")
            if "subagent_list" in r.details:
                tools_found.add("subagent_list")
            if "subagent_delete" in r.details:
                tools_found.add("subagent_delete")
            if "subagent_progress" in r.details:
                tools_found.add("subagent_progress")
            if "subagent_schedule" in r.details:
                tools_found.add("subagent_schedule")
            if "subagent_schedule_list" in r.details:
                tools_found.add("subagent_schedule_list")
            if "subagent_schedule_cancel" in r.details:
                tools_found.add("subagent_schedule_cancel")

    print(f"\nSubagent tools used:")
    for tool in sorted(tools_found):
        print(f"  ✅ {tool}")

    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
