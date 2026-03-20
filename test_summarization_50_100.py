#!/usr/bin/env python3
"""Test summarization with 50 interactions for new user, then 100 for desktop_user."""

import requests
import time

BASE_URL = "http://localhost:8080"

TEST_QUERIES = [
    "list my contacts",
    "add a contact test1@example.com named Test One",
    "list my todos",
    "add a todo: Test task one",
    "search the web for latest news",
    "what time is it in tokyo?",
    "list files in current directory",
    "create a file called test1.txt with hello world",
    "read the file test1.txt",
    "list my contacts",
    "add a contact test2@example.com named Test Two",
    "list my todos",
    "add a todo: Test task two",
    "search the web for weather",
    "what time is it in london?",
    "list files in data directory",
    "create a file called test2.txt with some content",
    "read the file test2.txt",
    "list my contacts",
    "add a contact test3@example.com named Test Three",
    "list my todos",
    "add a todo: Test task three",
    "search the web for python tutorials",
    "what time is it in paris?",
    "list files in src directory",
    "create a file called test3.txt with more content",
    "read the file test3.txt",
    "list my contacts",
    "add a contact test4@example.com named Test Four",
    "list my todos",
    "add a todo: Test task four",
    "search the web for AI news",
    "what time is it in sydney?",
    "list files in tests directory",
    "create a file called test4.txt with data",
    "read the file test4.txt",
    "list my contacts",
    "add a contact test5@example.com named Test Five",
    "list my todos",
    "add a todo: Test task five",
    "search the web for machine learning",
    "what time is it in berlin?",
    "list files in docker directory",
    "create a file called test5.txt with notes",
    "read the file test5.txt",
    "list my contacts",
    "add a contact test6@example.com named Test Six",
    "list my todos",
    "add a todo: Test task six",
]


def run_interactions(user_id: str, count: int):
    """Run specified number of interactions."""
    print(f"\n{'=' * 60}")
    print(f"Testing {user_id} with {count} interactions")
    print(f"{'=' * 60}")

    for i in range(count):
        query = TEST_QUERIES[i % len(TEST_QUERIES)]

        try:
            resp = requests.post(
                f"{BASE_URL}/message",
                json={"message": query, "user_id": user_id, "verbose": False},
                timeout=60,
            )
            data = resp.json()

            if data.get("error"):
                print(f"[{i + 1}/{count}] ERROR: {data['error']}")
            else:
                print(f"[{i + 1}/{count}] {query[:35]:<35} -> OK")

        except Exception as e:
            print(f"[{i + 1}/{count}] EXCEPTION: {e}")

        time.sleep(0.3)

    # Check results
    import subprocess

    result = subprocess.run(
        [
            "sqlite3",
            f"data/users/{user_id}/messages/messages.db",
            "SELECT role, COUNT(*) FROM messages GROUP BY role;",
        ],
        capture_output=True,
        text=True,
    )
    print(f"\nMessage counts:")
    print(result.stdout)

    # Check for summaries
    result = subprocess.run(
        [
            "sqlite3",
            f"data/users/{user_id}/messages/messages.db",
            "SELECT COUNT(*) FROM messages WHERE role='summary';",
        ],
        capture_output=True,
        text=True,
    )
    summaries = result.stdout.strip()
    print(f"Summaries: {summaries}")


def main():
    print("Starting summarization test")
    print(f"Trigger threshold: 500 tokens")

    # Test 1: 50 interactions with new user
    print("\n" + "=" * 60)
    print("TEST 1: 50 interactions with new user")
    print("=" * 60)
    run_interactions("summarization_test_50", 50)

    # Test 2: 100 interactions with desktop_user
    print("\n" + "=" * 60)
    print("TEST 2: 100 interactions with desktop_user")
    print("=" * 60)
    run_interactions("desktop_user", 100)

    print("\n" + "=" * 60)
    print("TESTS COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
