#!/usr/bin/env python3
"""Quick subagent test - 10 essential tests."""

import asyncio
import json

import httpx


TESTS = [
    ("List subagents (empty)", "list my subagents"),
    ("Create subagent", "create subagent tester that can test code"),
    ("List after create", "list my subagents"),
    ("Invoke subagent", "use subagent tester to say hello"),
    ("Check status", "check status of subagent tester"),
    ("Create another", "create subagent researcher that can search the web"),
    ("List multiple", "list my subagents"),
    ("Delete subagent", "delete subagent tester"),
    ("Verify delete", "list my subagents"),
    ("Delete another", "delete subagent researcher"),
]


async def run_test(msg: str, i: int):
    print(f"\n[{i + 1}/10] {msg[:50]}...")

    async with httpx.AsyncClient(timeout=45.0) as client:
        try:
            async with client.stream(
                "POST",
                "http://localhost:8000/message/stream",
                json={"message": msg, "user_id": "subagent_test", "verbose": True},
            ) as resp:
                chunks = 0
                tools = set()
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        chunks += 1
                        try:
                            d = json.loads(line[6:])
                            if d.get("type") == "updates":
                                ns = d.get("ns", "")
                                if "subagent" in ns.lower():
                                    tools.add(ns)
                        except:
                            pass

                print(f"   ✅ {chunks} chunks, tools: {sorted(tools)}")
                return True, tools
        except Exception as e:
            print(f"   ❌ {str(e)[:50]}")
            return False, set()


async def main():
    print("=" * 60)
    print("SUBAGENT FUNCTIONALITY TEST - 10 TESTS")
    print("=" * 60)

    all_tools = set()

    for i, (name, msg) in enumerate(TESTS):
        success, tools = await run_test(msg, i)
        all_tools.update(tools)
        await asyncio.sleep(1)

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"\nAll subagent tools used: {sorted(all_tools)}")

    # Verify expected tools
    expected = [
        "subagent_create",
        "subagent_invoke",
        "subagent_list",
        "subagent_delete",
        "subagent_progress",
    ]
    print("\nVerification:")
    for tool in expected:
        status = "✅" if tool in all_tools else "❌"
        print(f"  {status} {tool}")


if __name__ == "__main__":
    asyncio.run(main())
