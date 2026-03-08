"""Focused test for email tools and background sync."""

import asyncio
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HTTP_BASE_URL = os.environ.get("EVAL_HTTP_URL", "http://localhost:8000")


@dataclass
class TestResult:
    name: str
    query: str
    response: str
    success: bool
    error: str | None = None
    duration_ms: int = 0


async def call_agent(message: str, user_id: str = "test_email") -> dict:
    """Call agent via HTTP API."""
    import aiohttp

    async with aiohttp.ClientSession() as session:
        payload = {"message": message, "user_id": user_id}
        start_time = time.time()
        async with session.post(f"{HTTP_BASE_URL}/message", json=payload) as resp:
            duration_ms = int((time.time() - start_time) * 1000)
            if resp.status != 200:
                text = await resp.text()
                raise Exception(f"HTTP {resp.status}: {text}")
            data = await resp.json()
            return {
                "response": data.get("response", ""),
                "duration_ms": duration_ms,
            }


async def test_email_connect():
    """Test email connection."""
    results = []

    tests = [
        (
            "Connect Gmail",
            "Connect my Gmail account with email test@gmail.com password testpassword",
        ),
        ("List accounts", "List my connected email accounts"),
        ("Disconnect", "Disconnect my Gmail account"),
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


async def test_email_list():
    """Test listing emails."""
    results = []

    tests = [
        ("List inbox", "List my recent emails from inbox"),
        ("List with limit", "List 5 most recent emails"),
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


async def test_email_search():
    """Test searching emails."""
    results = []

    tests = [
        ("Search by sender", "Search emails from john"),
        ("Search by subject", "Search emails with meeting in subject"),
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


async def test_email_get():
    """Test reading specific email."""
    results = []

    tests = [
        ("Read latest", "Read my most recent email"),
        ("Get by ID", "Get email with ID 1"),
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


async def test_email_send():
    """Test sending email."""
    results = []

    tests = [
        ("Send simple", "Send email to test@example.com with subject Test message Hello world"),
        (
            "Send with body",
            "Send email to bob@gmail.com subject Project Update about the latest progress",
        ),
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


async def test_email_sync():
    """Test email sync."""
    results = []

    tests = [
        ("Sync inbox", "Sync my Gmail inbox"),
        ("Sync new", "Sync new emails only"),
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


async def test_email_extract():
    """Test extracting todos from emails."""
    results = []

    tests = [
        ("Extract todos", "Extract todos from recent emails"),
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


async def run_email_tests():
    """Run all email tests."""
    output_dir = Path("data/evaluations")
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("EMAIL TOOLS TESTING")
    print("=" * 60)

    all_results = {}

    print("\n[1/7] Testing email connection...")
    all_results["email_connect"] = await test_email_connect()
    for r in all_results["email_connect"]:
        print(f"  {'✅' if r.success else '❌'} {r.name}: {r.duration_ms}ms")

    print("\n[2/7] Testing email list...")
    all_results["email_list"] = await test_email_list()
    for r in all_results["email_list"]:
        print(f"  {'✅' if r.success else '❌'} {r.name}: {r.duration_ms}ms")

    print("\n[3/7] Testing email search...")
    all_results["email_search"] = await test_email_search()
    for r in all_results["email_search"]:
        print(f"  {'✅' if r.success else '❌'} {r.name}: {r.duration_ms}ms")

    print("\n[4/7] Testing email get/read...")
    all_results["email_get"] = await test_email_get()
    for r in all_results["email_get"]:
        print(f"  {'✅' if r.success else '❌'} {r.name}: {r.duration_ms}ms")

    print("\n[5/7] Testing email send...")
    all_results["email_send"] = await test_email_send()
    for r in all_results["email_send"]:
        print(f"  {'✅' if r.success else '❌'} {r.name}: {r.duration_ms}ms")

    print("\n[6/7] Testing email sync...")
    all_results["email_sync"] = await test_email_sync()
    for r in all_results["email_sync"]:
        print(f"  {'✅' if r.success else '❌'} {r.name}: {r.duration_ms}ms")

    print("\n[7/7] Testing email extract...")
    all_results["email_extract"] = await test_email_extract()
    for r in all_results["email_extract"]:
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
    output_file = output_dir / f"email_tools_test_{timestamp}.json"

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
    asyncio.run(run_email_tests())
