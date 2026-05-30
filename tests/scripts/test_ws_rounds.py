"""Test: Talk to agent via WebSocket for N rounds, then verify message storage.

Usage:
    uv run python tests/scripts/test_ws_rounds.py [--rounds 100] [--port 8000]

Requires the EA HTTP server running on the specified port.
"""

import asyncio
import json
import sys
import time
from pathlib import Path

# Add project root to path for direct script execution
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import websockets


async def test_ws_rounds(rounds: int = 100, port: int = 8000):
    ws_url = f"ws://localhost:{port}/ws/conversation"

    print(f"Connecting to {ws_url} ...")
    async with websockets.connect(ws_url) as ws:
        print("Connected. Starting rounds...")

        round_times: list[float] = []
        total_sent = 0
        total_assistant = 0

        for i in range(1, rounds + 1):
            t0 = time.monotonic()

            msg = {"type": "user_message", "content": f"hello round {i}"}
            await ws.send(json.dumps(msg))
            total_sent += 1

            done = False
            while not done:
                raw = await ws.recv()
                data = json.loads(raw)
                t = data.get("type", "")
                if t == "done":
                    done = True
                    total_assistant += 1
                elif t == "error":
                    print(f"  Round {i}: ERROR: {data.get('message', '')}")
                    done = True

            elapsed = time.monotonic() - t0
            round_times.append(elapsed)

            if i % 10 == 0 or i == 1:
                avg = sum(round_times) / len(round_times)
                print(f"  Round {i}/{rounds} done in {elapsed:.1f}s (avg {avg:.1f}s)")

    print(f"\n=== Results ===")
    print(f"Rounds completed: {rounds}")
    print(f"Messages sent (user): {total_sent}")
    print(f"Assistant responses: {total_assistant}")
    print(f"Total time: {sum(round_times):.1f}s")
    print(f"Avg round time: {sum(round_times)/len(round_times):.1f}s")
    print(f"Fastest: {min(round_times):.1f}s")
    print(f"Slowest: {max(round_times):.1f}s")

    # Now verify via MessageStore
    print("\n--- Checking MessageStore ---")
    from src.storage.messages import get_message_store

    store = get_message_store("default_user", "personal")
    count = store.count_messages()

    recent = store.get_recent_messages(count=10)
    print(f"Total messages in store: {count}")
    print(f"Last 10 messages:")
    for m in reversed(recent):
        print(f"  [{m.role}] {m.content[:80]}")

    # Verify we have at least 2*rounds messages (user + assistant)
    expected_min = rounds * 2
    if count >= expected_min:
        print(f"\n✓ PASS: {count} >= {expected_min} (2×{rounds} minimum)")
    else:
        print(f"\n✗ FAIL: Only {count} messages, expected ≥ {expected_min}")

    return count >= expected_min


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Test WebSocket agent for N rounds")
    parser.add_argument("--rounds", type=int, default=100, help="Number of rounds")
    parser.add_argument("--port", type=int, default=8000, help="HTTP server port")
    args = parser.parse_args()

    success = asyncio.run(test_ws_rounds(rounds=args.rounds, port=args.port))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
