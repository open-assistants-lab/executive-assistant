#!/usr/bin/env python3
"""Run 50 test cycles and monitor summarization middleware."""

import requests
import json
import sys

USER_ID = "desktop_user"
BASE_URL = "http://localhost:8000"

TEST_QUERIES = [
    "what time is it?",
    "list files in current directory",
    "create a file called test1.txt with hello world",
    "read the file test1.txt",
    "delete the file test1.txt",
    "list my contacts",
    "add a contact test1@example.com named Test One",
    "list my todos",
    "add a todo: Test task one",
    "search the web for weather in tokyo",
    "what time is it in london?",
    "list files in data directory",
    "create a file called notes.txt with some notes",
    "read the file notes.txt",
    "delete the file notes.txt",
    "list my contacts",
    "add a contact test2@example.com named Test Two",
    "list my todos",
    "add a todo: Test task two",
    "search the web for news about python",
    "what time is it in paris?",
    "list files in src directory",
    "create a file called data.json with {}",
    "read the file data.json",
    "delete the file data.json",
    "list my contacts",
    "add a contact test3@example.com named Test Three",
    "list my todos",
    "add a todo: Test task three",
    "search the web for best restaurants in san francisco",
    "what time is it in berlin?",
    "list files in tests directory",
    "create a file called readme.md with # Test",
    "read the file readme.md",
    "delete the file readme.md",
    "list my contacts",
    "add a contact test4@example.com named Test Four",
    "list my todos",
    "add a todo: Test task four",
    "search the web for python tutorials",
    "what time is it in sydney?",
    "list files in docker directory",
    "create a file called config.yaml with version: 1",
    "read the file config.yaml",
    "delete the file config.yaml",
    "list my contacts",
    "add a contact test5@example.com named Test Five",
    "list my todos",
    "add a todo: Test task five",
    "search the web for machine learning news",
]


def run_cycle(query: str, cycle: int):
    """Run a single cycle and return results."""
    print(f"\n{'=' * 60}")
    print(f"CYCLE {cycle}/50: {query}")
    print("=" * 60)

    try:
        resp = requests.post(
            f"{BASE_URL}/message",
            json={"message": query, "user_id": USER_ID, "verbose": True},
            timeout=60,
        )
        data = resp.json()

        if data.get("error"):
            print(f"ERROR: {data['error']}")
            return None

        response = data.get("response", "")
        verbose = data.get("verbose_data")

        # Check for summarization in middleware events
        summ_ran = False
        if verbose and verbose.get("middleware_events"):
            for event in verbose["middleware_events"]:
                if "Summarization" in event.get("name", ""):
                    summ_ran = True
                    print(f"\n*** SUMMARIZATION TRIGGERED ***")
                    print(f"Event: {json.dumps(event, indent=2)}")
                    break

        print(f"Response: {response[:100]}...")
        print(f"Summarization ran: {summ_ran}")

        return {
            "cycle": cycle,
            "query": query,
            "response": response,
            "summarization_ran": summ_ran,
            "middleware_events": verbose.get("middleware_events") if verbose else [],
        }

    except Exception as e:
        print(f"ERROR: {e}")
        return None


def main():
    print("Starting 50-cycle test with summarization monitoring")
    print(f"User: {USER_ID}")
    print(f"Base URL: {BASE_URL}")

    results = []
    summarization_count = 0

    for i in range(50):
        query = TEST_QUERIES[i % len(TEST_QUERIES)]
        result = run_cycle(query, i + 1)

        if result:
            results.append(result)
            if result["summarization_ran"]:
                summarization_count += 1

        # Small delay between requests
        import time

        time.sleep(0.2)

    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print("=" * 60)
    print(f"Total cycles: 50")
    print(f"Summarization triggered: {summarization_count} times")

    # Save results to file
    with open("data/evaluations/50_cycle_test.json", "w") as f:
        json.dump({"results": results, "summarization_count": summarization_count}, f, indent=2)

    print(f"\nResults saved to data/evaluations/50_cycle_test.json")

    # Check final message count
    import subprocess

    result = subprocess.run(
        ["sqlite3", f"data/users/{USER_ID}/messages/messages.db", "SELECT COUNT(*) FROM messages;"],
        capture_output=True,
        text=True,
    )
    print(f"\nFinal message count in DB: {result.stdout.strip()}")


if __name__ == "__main__":
    main()
