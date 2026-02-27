"""Test script for agent pool concurrency."""

import asyncio
import time

import httpx


async def send_message(client: httpx.AsyncClient, message: str, user_id: str) -> dict:
    """Send a message to the agent."""
    try:
        response = await client.post(
            "http://localhost:8000/message",
            json={"message": message, "user_id": user_id},
            timeout=120.0,
        )
        data = response.json()
        return {"status": response.status_code, "data": data, "user_id": user_id}
    except Exception as e:
        return {"status": "error", "error": str(e), "user_id": user_id}


async def test_concurrent_requests(num_requests: int, same_user: bool = False):
    """Test concurrent requests."""
    async with httpx.AsyncClient() as client:
        tasks = []
        for i in range(num_requests):
            user_id = "test_user" if same_user else f"user_{i}"
            message = f"Hello, this is request {i}! What time is it?"
            tasks.append(send_message(client, message, user_id))

        start = time.time()
        results = await asyncio.gather(*tasks)
        elapsed = time.time() - start

        success = sum(
            1 for r in results if r.get("status") == 200 and r.get("data", {}).get("response")
        )
        errors = [
            r for r in results if r.get("status") != 200 or not r.get("data", {}).get("response")
        ]

        print(f"\n{'=' * 60}")
        print(f"Test: {num_requests} concurrent requests")
        print(f"Same user: {same_user}")
        print(f"Time: {elapsed:.2f}s")
        print(f"Success: {success}/{num_requests}")
        print(f"Errors: {len(errors)}")

        if errors:
            print("\nErrors:")
            for e in errors[:5]:
                print(f"  - {e}")

        return {"success": success, "errors": len(errors), "elapsed": elapsed}


async def main():
    """Run concurrency tests."""
    print("Testing agent pool concurrency...")
    print("Make sure HTTP server is running: uv run ea http")

    # Test 1: Different users (should work fine)
    print("\n[Test 1] Different users - 10 concurrent requests")
    await test_concurrent_requests(10, same_user=False)

    # Test 2: Same user (tests pool handling)
    print("\n[Test 2] Same user - 10 concurrent requests")
    await test_concurrent_requests(10, same_user=True)

    # Test 3: Same user - 30 concurrent
    print("\n[Test 3] Same user - 30 concurrent requests")
    await test_concurrent_requests(30, same_user=True)


if __name__ == "__main__":
    asyncio.run(main())
