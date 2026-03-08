"""Focused tests for subagents and skills functionality."""

import asyncio
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

HTTP_BASE_URL = os.environ.get("EVAL_HTTP_URL", "http://localhost:8000")


@dataclass
class TestResult:
    name: str
    query: str
    response: str
    success: bool
    error: str | None = None
    duration_ms: int = 0


async def call_agent(message: str, user_id: str = "test_subagent") -> dict:
    """Call agent via HTTP API."""
    import aiohttp

    async with aiohttp.ClientSession() as session:
        payload = {"message": message, "user_id": user_id}
        async with session.post(f"{HTTP_BASE_URL}/message", json=payload) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise Exception(f"HTTP {resp.status}: {text}")
            return await resp.json()


async def test_subagent_create():
    """Test subagent creation."""
    results = []

    tests = [
        (
            "Create research subagent",
            "Create a subagent named 'researcher' with deep-research skill",
        ),
        (
            "Create coding subagent",
            "Create a coding subagent named 'coder' that helps with programming",
        ),
        (
            "Create reminder subagent",
            "Create a reminder subagent named 'reminder-sender' that sends Telegram messages",
        ),
    ]

    for name, query in tests:
        start = time.time()
        try:
            resp = await call_agent(query)
            response = resp.get("response", "")
            success = (
                "subagent" in response.lower()
                or "created" in response.lower()
                or "success" in response.lower()
            )
            results.append(
                TestResult(
                    name=name,
                    query=query,
                    response=response,
                    success=success,
                    duration_ms=int((time.time() - start) * 1000),
                )
            )
        except Exception as e:
            results.append(
                TestResult(
                    name=name,
                    query=query,
                    response="",
                    success=False,
                    error=str(e),
                    duration_ms=int((time.time() - start) * 1000),
                )
            )

    return results


async def test_subagent_invoke():
    """Test subagent invocation."""
    results = []

    # First create the subagent
    await call_agent("Create a research subagent named 'quick-test' with deep-research skill")
    await asyncio.sleep(1)

    tests = [
        ("Invoke research subagent", "Use subagent 'quick-test' to search for AI news"),
        ("Invoke with specific task", "Ask quick-test to find information about Python asyncio"),
    ]

    for name, query in tests:
        start = time.time()
        try:
            resp = await call_agent(query)
            response = resp.get("response", "")
            success = len(response) > 50  # Has actual response
            results.append(
                TestResult(
                    name=name,
                    query=query,
                    response=response,
                    success=success,
                    duration_ms=int((time.time() - start) * 1000),
                )
            )
        except Exception as e:
            results.append(
                TestResult(
                    name=name,
                    query=query,
                    response="",
                    success=False,
                    error=str(e),
                    duration_ms=int((time.time() - start) * 1000),
                )
            )

    return results


async def test_subagent_schedule_once():
    """Test one-time subagent scheduling."""
    results = []

    tests = [
        (
            "Schedule reminder now",
            "Schedule a reminder subagent to send 'Test reminder' in 1 minute",
        ),
        (
            "Schedule meeting reminder",
            "Schedule a reminder to remind me about meeting at 8pm today",
        ),
        (
            "Schedule with specific time",
            "Schedule reminder-sender subagent to send 'Visit 501' tomorrow at 9am",
        ),
    ]

    for name, query in tests:
        start = time.time()
        try:
            resp = await call_agent(query)
            response = resp.get("response", "")
            success = (
                "schedule" in response.lower()
                or "reminder" in response.lower()
                or "job" in response.lower()
            )
            results.append(
                TestResult(
                    name=name,
                    query=query,
                    response=response,
                    success=success,
                    duration_ms=int((time.time() - start) * 1000),
                )
            )
        except Exception as e:
            results.append(
                TestResult(
                    name=name,
                    query=query,
                    response="",
                    success=False,
                    error=str(e),
                    duration_ms=int((time.time() - start) * 1000),
                )
            )

    return results


async def test_subagent_schedule_recurring():
    """Test recurring subagent scheduling."""
    results = []

    tests = [
        ("Schedule daily reminder", "Schedule a daily reminder at 9am every day"),
        ("Schedule weekly", "Schedule weekly team standup reminder every Monday at 10am"),
    ]

    for name, query in tests:
        start = time.time()
        try:
            resp = await call_agent(query)
            response = resp.get("response", "")
            success = (
                "schedule" in response.lower()
                or "daily" in response.lower()
                or "weekly" in response.lower()
            )
            results.append(
                TestResult(
                    name=name,
                    query=query,
                    response=response,
                    success=success,
                    duration_ms=int((time.time() - start) * 1000),
                )
            )
        except Exception as e:
            results.append(
                TestResult(
                    name=name,
                    query=query,
                    response="",
                    success=False,
                    error=str(e),
                    duration_ms=int((time.time() - start) * 1000),
                )
            )

    return results


async def test_subagent_list():
    """Test listing subagents."""
    results = []

    tests = [
        ("List all subagents", "List all my subagents"),
    ]

    for name, query in tests:
        start = time.time()
        try:
            resp = await call_agent(query)
            response = resp.get("response", "")
            success = "subagent" in response.lower() or len(response) > 0
            results.append(
                TestResult(
                    name=name,
                    query=query,
                    response=response,
                    success=success,
                    duration_ms=int((time.time() - start) * 1000),
                )
            )
        except Exception as e:
            results.append(
                TestResult(
                    name=name,
                    query=query,
                    response="",
                    success=False,
                    error=str(e),
                    duration_ms=int((time.time() - start) * 1000),
                )
            )

    return results


async def test_subagent_validate():
    """Test subagent validation."""
    results = []

    tests = [
        ("Validate subagent", "Validate the subagent named 'quick-test'"),
    ]

    for name, query in tests:
        start = time.time()
        try:
            resp = await call_agent(query)
            response = resp.get("response", "")
            success = "valid" in response.lower() or "subagent" in response.lower()
            results.append(
                TestResult(
                    name=name,
                    query=query,
                    response=response,
                    success=success,
                    duration_ms=int((time.time() - start) * 1000),
                )
            )
        except Exception as e:
            results.append(
                TestResult(
                    name=name,
                    query=query,
                    response="",
                    success=False,
                    error=str(e),
                    duration_ms=int((time.time() - start) * 1000),
                )
            )

    return results


async def test_subagent_progress():
    """Test subagent progress tracking."""
    results = []

    tests = [
        ("Get subagent progress", "Show progress of any active subagent tasks"),
    ]

    for name, query in tests:
        start = time.time()
        try:
            resp = await call_agent(query)
            response = resp.get("response", "")
            success = "progress" in response.lower() or "subagent" in response.lower()
            results.append(
                TestResult(
                    name=name,
                    query=query,
                    response=response,
                    success=success,
                    duration_ms=int((time.time() - start) * 1000),
                )
            )
        except Exception as e:
            results.append(
                TestResult(
                    name=name,
                    query=query,
                    response="",
                    success=False,
                    error=str(e),
                    duration_ms=int((time.time() - start) * 1000),
                )
            )

    return results


async def test_skills_list():
    """Test listing skills."""
    results = []

    tests = [
        ("List all skills", "List all available skills"),
        ("Show skills detail", "What skills do you have?"),
    ]

    for name, query in tests:
        start = time.time()
        try:
            resp = await call_agent(query)
            response = resp.get("response", "")
            success = "skill" in response.lower() or len(response) > 0
            results.append(
                TestResult(
                    name=name,
                    query=query,
                    response=response,
                    success=success,
                    duration_ms=int((time.time() - start) * 1000),
                )
            )
        except Exception as e:
            results.append(
                TestResult(
                    name=name,
                    query=query,
                    response="",
                    success=False,
                    error=str(e),
                    duration_ms=int((time.time() - start) * 1000),
                )
            )

    return results


async def test_skills_load():
    """Test loading a skill."""
    results = []

    tests = [
        ("Load planning skill", "Load the planning-with-files skill"),
        ("Load deep-research skill", "Load the deep-research skill"),
        ("Load skill creator", "Load the skill-creator skill"),
    ]

    for name, query in tests:
        start = time.time()
        try:
            resp = await call_agent(query)
            response = resp.get("response", "")
            success = "skill" in response.lower() or "load" in response.lower() or len(response) > 0
            results.append(
                TestResult(
                    name=name,
                    query=query,
                    response=response,
                    success=success,
                    duration_ms=int((time.time() - start) * 1000),
                )
            )
        except Exception as e:
            results.append(
                TestResult(
                    name=name,
                    query=query,
                    response="",
                    success=False,
                    error=str(e),
                    duration_ms=int((time.time() - start) * 1000),
                )
            )

    return results


async def test_skill_create():
    """Test skill creation."""
    results = []

    tests = [
        ("Create simple skill", "Create a new skill named 'test-hello' that says hello world"),
        (
            "Create skill with description",
            "Create a skill called 'email-helper' for helping with emails",
        ),
    ]

    for name, query in tests:
        start = time.time()
        try:
            resp = await call_agent(query)
            response = resp.get("response", "")
            success = (
                "skill" in response.lower()
                or "created" in response.lower()
                or "success" in response.lower()
            )
            results.append(
                TestResult(
                    name=name,
                    query=query,
                    response=response,
                    success=success,
                    duration_ms=int((time.time() - start) * 1000),
                )
            )
        except Exception as e:
            results.append(
                TestResult(
                    name=name,
                    query=query,
                    response="",
                    success=False,
                    error=str(e),
                    duration_ms=int((time.time() - start) * 1000),
                )
            )

    return results


async def test_subagent_with_skills():
    """Test subagent with specific skills."""
    results = []

    tests = [
        (
            "Create with deep-research",
            "Create a research subagent named 'market-research' with deep-research skill",
        ),
        ("Create with planning", "Create a planning subagent with planning-with-files skill"),
    ]

    for name, query in tests:
        start = time.time()
        try:
            resp = await call_agent(query)
            response = resp.get("response", "")
            success = "subagent" in response.lower() or "created" in response.lower()
            results.append(
                TestResult(
                    name=name,
                    query=query,
                    response=response,
                    success=success,
                    duration_ms=int((time.time() - start) * 1000),
                )
            )
        except Exception as e:
            results.append(
                TestResult(
                    name=name,
                    query=query,
                    response="",
                    success=False,
                    error=str(e),
                    duration_ms=int((time.time() - start) * 1000),
                )
            )

    return results


async def test_subagent_manager_skill():
    """Test using subagent-manager skill."""
    results = []

    tests = [
        ("Load subagent manager", "Load the subagent-manager skill"),
        ("How to create subagent", "How do I create a subagent?"),
        ("How to schedule", "Show me how to schedule a subagent"),
    ]

    for name, query in tests:
        start = time.time()
        try:
            resp = await call_agent(query)
            response = resp.get("response", "")
            success = len(response) > 0
            results.append(
                TestResult(
                    name=name,
                    query=query,
                    response=response,
                    success=success,
                    duration_ms=int((time.time() - start) * 1000),
                )
            )
        except Exception as e:
            results.append(
                TestResult(
                    name=name,
                    query=query,
                    response="",
                    success=False,
                    error=str(e),
                    duration_ms=int((time.time() - start) * 1000),
                )
            )

    return results


async def run_all_tests():
    """Run all focused tests."""
    output_dir = Path("data/evaluations")
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("SUBAGENT AND SKILLS FOCUSED TESTS")
    print("=" * 60)

    all_results = {}

    # Subagent tests
    print("\n[1/11] Testing subagent creation...")
    all_results["subagent_create"] = await test_subagent_create()
    for r in all_results["subagent_create"]:
        print(f"  {'✅' if r.success else '❌'} {r.name}: {r.duration_ms}ms")

    print("\n[2/11] Testing subagent invocation...")
    all_results["subagent_invoke"] = await test_subagent_invoke()
    for r in all_results["subagent_invoke"]:
        print(f"  {'✅' if r.success else '❌'} {r.name}: {r.duration_ms}ms")

    print("\n[3/11] Testing one-time scheduling...")
    all_results["schedule_once"] = await test_subagent_schedule_once()
    for r in all_results["schedule_once"]:
        print(f"  {'✅' if r.success else '❌'} {r.name}: {r.duration_ms}ms")

    print("\n[4/11] Testing recurring scheduling...")
    all_results["schedule_recurring"] = await test_subagent_schedule_recurring()
    for r in all_results["schedule_recurring"]:
        print(f"  {'✅' if r.success else '❌'} {r.name}: {r.duration_ms}ms")

    print("\n[5/11] Testing subagent listing...")
    all_results["subagent_list"] = await test_subagent_list()
    for r in all_results["subagent_list"]:
        print(f"  {'✅' if r.success else '❌'} {r.name}: {r.duration_ms}ms")

    print("\n[6/11] Testing subagent validation...")
    all_results["subagent_validate"] = await test_subagent_validate()
    for r in all_results["subagent_validate"]:
        print(f"  {'✅' if r.success else '❌'} {r.name}: {r.duration_ms}ms")

    print("\n[7/11] Testing subagent progress...")
    all_results["subagent_progress"] = await test_subagent_progress()
    for r in all_results["subagent_progress"]:
        print(f"  {'✅' if r.success else '❌'} {r.name}: {r.duration_ms}ms")

    # Skills tests
    print("\n[8/11] Testing skills list...")
    all_results["skills_list"] = await test_skills_list()
    for r in all_results["skills_list"]:
        print(f"  {'✅' if r.success else '❌'} {r.name}: {r.duration_ms}ms")

    print("\n[9/11] Testing skills load...")
    all_results["skills_load"] = await test_skills_load()
    for r in all_results["skills_load"]:
        print(f"  {'✅' if r.success else '❌'} {r.name}: {r.duration_ms}ms")

    print("\n[10/11] Testing skill creation...")
    all_results["skill_create"] = await test_skill_create()
    for r in all_results["skill_create"]:
        print(f"  {'✅' if r.success else '❌'} {r.name}: {r.duration_ms}ms")

    # Combined
    print("\n[11/11] Testing subagent with skills...")
    all_results["subagent_with_skills"] = await test_subagent_with_skills()
    for r in all_results["subagent_with_skills"]:
        print(f"  {'✅' if r.success else '❌'} {r.name}: {r.duration_ms}ms")

    print("\n[Bonus] Testing subagent-manager skill...")
    all_results["subagent_manager_skill"] = await test_subagent_manager_skill()
    for r in all_results["subagent_manager_skill"]:
        print(f"  {'✅' if r.success else '❌'} {r.name}: {r.duration_ms}ms")

    # Summary
    total = 0
    passed = 0
    for category, results in all_results.items():
        for r in results:
            total += 1
            if r.success:
                passed += 1

    print("\n" + "=" * 60)
    print(f"SUMMARY: {passed}/{total} tests passed ({100 * passed / total:.1f}%)")
    print("=" * 60)

    # Save results
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"subagent_skills_test_{timestamp}.json"

    # Convert to JSON-serializable format
    json_results = {}
    for category, results in all_results.items():
        json_results[category] = [
            {
                "name": r.name,
                "query": r.query,
                "response": r.response[:500] if r.response else "",
                "success": r.success,
                "error": r.error,
                "duration_ms": r.duration_ms,
            }
            for r in results
        ]

    with open(output_file, "w") as f:
        json.dump(json_results, f, indent=2)

    print(f"\nResults saved to {output_file}")

    # Show failures
    print("\nFailed tests:")
    for category, results in all_results.items():
        for r in results:
            if not r.success:
                print(f"  [{category}] {r.name}: {r.error or 'no response'}")

    return all_results


if __name__ == "__main__":
    asyncio.run(run_all_tests())
