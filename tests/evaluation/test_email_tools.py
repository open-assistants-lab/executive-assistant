"""Focused test for email tools."""

import os
import time
from dataclasses import dataclass

HTTP_BASE_URL = os.environ.get("EVAL_HTTP_URL", "http://localhost:8080")


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
