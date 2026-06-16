from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from tests.evaluation.personas import PERSONAS, generate_test_queries
from tests.smoke.models import SuiteResult, TestResult

logger = logging.getLogger(__name__)

_PERSONA_SAMPLE_IDS = ["p22", "p9", "p1", "p23", "p3"]


def _resolve_personas(requested: str | int) -> list[dict]:
    if isinstance(requested, str) and requested.lower() == "all":
        return list(PERSONAS)
    count = int(requested)
    selected = [p for p in PERSONAS if p["id"] in _PERSONA_SAMPLE_IDS]
    if not selected:
        selected = PERSONAS[:count]
    return selected[:count]


_GAP_QUERIES = [
    # Browser tools (15 queries)
    "open a browser and navigate to example.com",
    "click the first link on the page",
    "fill in a search box with hello world",
    "take a screenshot of the current page",
    "scroll down the page",
    "get the page title",
    "get the text content of the page",
    "open a new tab and go to google.com",
    "switch to the first tab",
    "close the current tab",
    "go back in browser history",
    "go forward in browser history",
    "press the enter key",
    "list all browser sessions",
    "check browser status",
    # Small tools (8 queries)
    "search for tools related to files",
    "reload all tools",
    "count my messages",
    "show my message timeline",
    "show my memory profile",
    "reflect on what I learned today",
    "set a user prompt to always be concise",
    "get my current user prompt",
]


async def run_persona_suite(
    base_url: str,
    persona_count: str | int = 5,
    queries_per_persona: int = 25,
) -> SuiteResult:
    import aiohttp

    personas = _resolve_personas(persona_count)
    all_results: list[TestResult] = []
    suite_start = time.monotonic()

    async with aiohttp.ClientSession() as session:
        for persona in personas:
            pid = persona["id"]
            name = persona["name"]
            queries = generate_test_queries(persona, queries_per_persona)

            logger.info("Persona %s (%s): %d queries + %d gap queries",
                        pid, name, len(queries), len(_GAP_QUERIES))

            for idx, query in enumerate(queries):
                start = time.monotonic()
                test_name = f"{pid}-{idx:03d}"
                result = await _run_single_message(
                    session, base_url, test_name, query
                )
                result.duration_ms = int((time.monotonic() - start) * 1000)
                all_results.append(result)
                await asyncio.sleep(0.1)

            for idx, query in enumerate(_GAP_QUERIES):
                start = time.monotonic()
                test_name = f"{pid}-gap-{idx:03d}"
                result = await _run_single_message(
                    session, base_url, test_name, query
                )
                result.duration_ms = int((time.monotonic() - start) * 1000)
                all_results.append(result)
                await asyncio.sleep(0.1)

    duration = int((time.monotonic() - suite_start) * 1000)
    passed = sum(1 for r in all_results if r.passed)
    return SuiteResult(
        category="persona",
        total=len(all_results),
        passed=passed,
        results=all_results,
        duration_ms=duration,
    )


async def _run_single_message(
    session: Any,
    base_url: str,
    test_name: str,
    query: str,
) -> TestResult:
    try:
        async with session.post(
            f"{base_url}/message",
            json={"message": query, "user_id": "smoke_eval"},
            timeout=60,
        ) as resp:
            body = await resp.json()
            response = body.get("response", "")
            error = body.get("error")

            if resp.status != 200:
                return TestResult(
                    name=test_name,
                    passed=False,
                    duration_ms=0,
                    error=f"HTTP {resp.status}: {response[:200]}",
                )
            if error:
                return TestResult(
                    name=test_name,
                    passed=False,
                    duration_ms=0,
                    error=error[:500],
                )

            tool_calls = body.get("tool_calls") or body.get("verbose_data", {}).get("tool_events", [])
            tool_call_count = len(tool_calls) if isinstance(tool_calls, list) else 0

            return TestResult(
                name=test_name,
                passed=bool(response.strip()),
                duration_ms=0,
                tool_calls=tool_call_count,
                response_preview=response[:200],
            )

    except Exception as e:
        return TestResult(
            name=test_name,
            passed=False,
            duration_ms=0,
            error=str(e)[:500],
        )
