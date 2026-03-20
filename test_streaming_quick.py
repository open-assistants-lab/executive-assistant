#!/usr/bin/env python3
"""Quick streaming test with key personas and features."""

import asyncio
import json

import httpx


# Fewer tests - 5 per persona = 25 total
PERSONA_TESTS = [
    # p1_direct
    ("p1", "hello"),
    ("p1", "what time is it in tokyo"),
    ("p1", "list files in current directory"),
    ("p1", "list my contacts"),
    ("p1", "create a subagent named test_agent"),
    # p2_polite
    ("p2", "good morning!"),
    ("p2", "what time is it in london"),
    ("p2", "list my files please"),
    ("p2", "show my todos"),
    ("p2", "find contact john"),
    # p3_casual
    ("p3", "hey what's up"),
    ("p3", "time in berlin"),
    ("p3", "show files"),
    ("p3", "what tasks do i have?"),
    ("p3", "search for python files"),
    # p4_questioning
    ("p4", "hi how can you help me?"),
    ("p4", "what time is it? which cities can you check?"),
    ("p4", "what files can you show me?"),
    ("p4", "how do i see my contacts?"),
    ("p4", "can you list my emails?"),
    # p5_storytelling
    ("p5", "hi! how are you today"),
    ("p5", "i need to check time in tokyo for my meeting"),
    ("p5", "can you show my files?"),
    ("p5", "i have tasks to complete, show my todos"),
    ("p5", "find contact named john"),
]


async def run_test(message: str, user_id: str):
    """Run a single streaming test."""
    types_seen = set()
    namespaces_seen = set()
    chunk_count = 0

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            async with client.stream(
                "POST",
                "http://localhost:8000/message/stream",
                json={"message": message, "user_id": user_id, "verbose": True},
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        chunk_count += 1
                        try:
                            data = json.loads(line[6:])
                            ct = data.get("type")
                            ns = data.get("ns", "")
                            if ct:
                                types_seen.add(ct)
                            if ns:
                                namespaces_seen.add(ns)
                        except:
                            pass
        except Exception as e:
            return {"error": str(e), "chunk_count": chunk_count}

    return {
        "types": types_seen,
        "namespaces": namespaces_seen,
        "chunk_count": chunk_count,
    }


async def main():
    print("=" * 60)
    print("QUICK STREAMING TEST - 25 interactions")
    print("=" * 60)

    all_types = set()
    all_ns = set()

    for i, (persona, message) in enumerate(PERSONA_TESTS, 1):
        print(f"\n[{i}/25] {persona}: {message[:40]}...")

        result = await run_test(message, f"test_{persona}")

        if "error" in result:
            print(f"   ❌ Error: {result['error']}")
        else:
            print(f"   ✅ {result['chunk_count']} chunks")
            print(f"   Types: {sorted(result['types'])}")
            all_types.update(result["types"])
            all_ns.update(result["namespaces"])

        await asyncio.sleep(0.3)

    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")

    print(f"\nAll Types Seen: {sorted(all_types)}")
    print(f"\nAll Namespaces:")

    middlewares = [n for n in all_ns if "Middleware" in n]
    tools = [
        n
        for n in all_ns
        if n in ["list_files", "files_glob_search", "time_get", "list_contacts", "todos_list"]
    ]
    agents = [n for n in all_ns if "agent" in n.lower()]

    print(f"  Middlewares ({len(middlewares)}): {sorted(middlewares)}")
    print(f"  Tools ({len(tools)}): {sorted(tools)}")
    print(f"  Agents ({len(agents)}): {sorted(agents)}")

    print(f"\n--- Verification ---")
    print(f"✅ messages type: {'messages' in all_types}")
    print(f"✅ updates type: {'updates' in all_types}")
    print(f"✅ custom type: {'custom' in all_types}")
    print(f"✅ Middlewares: {len(middlewares) > 0}")
    print(f"✅ Tools: {len(tools) > 0}")

    # Check expected middlewares
    expected = [
        "SkillMiddleware",
        "InstinctsMiddleware",
        "SummarizationMiddleware",
        "HumanInTheLoopMiddleware",
    ]
    print(f"\n--- Expected Middlewares ---")
    for e in expected:
        found = any(e in m for m in middlewares)
        print(f"  {'✅' if found else '❌'} {e}")


if __name__ == "__main__":
    asyncio.run(main())
