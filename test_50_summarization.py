#!/usr/bin/env python3
"""Run 50 test cycles to trigger summarization."""

import requests
import time

USER_ID = "desktop_user"
BASE_URL = "http://localhost:8080"

TEST_QUERIES = [
    "list my contacts",
    "add a contact test1@example.com named Test One",
    "list my todos",
    "add a todo: Test task one for summarization",
    "search the web for latest news",
    "what time is it in tokyo?",
    "list files in current directory",
    "create a file called test1.txt with hello world",
    "read the file test1.txt",
    "list my contacts",
    "add a contact test2@example.com named Test Two",
    "list my todos",
    "add a todo: Test task two for summarization",
    "search the web for weather",
    "what time is it in london?",
    "list files in data directory",
    "create a file called test2.txt with some content",
    "read the file test2.txt",
    "list my contacts",
    "add a contact test3@example.com named Test Three",
    "list my todos",
    "add a todo: Test task three for summarization",
    "search the web for python tutorials",
    "what time is it in paris?",
    "list files in src directory",
    "create a file called test3.txt with more content",
    "read the file test3.txt",
    "list my contacts",
    "add a contact test4@example.com named Test Four",
    "list my todos",
    "add a todo: Test task four for summarization",
    "search the web for AI news",
    "what time is it in sydney?",
    "list files in tests directory",
    "create a file called test4.txt with data",
    "read the file test4.txt",
    "list my contacts",
    "add a contact test5@example.com named Test Five",
    "list my todos",
    "add a todo: Test task five for summarization",
    "search the web for machine learning",
    "what time is it in berlin?",
    "list files in docker directory",
    "create a file called test5.txt with notes",
    "read the file test5.txt",
    "list my contacts",
    "add a contact test6@example.com named Test Six",
    "list my todos",
    "add a todo: Test task six for summarization",
]


def main():
    print(f"Starting 50-cycle test as {USER_ID}")
    print(f"Trigger threshold: 20000 tokens")
    print("=" * 60)

    success = 0
    errors = 0

    for i in range(50):
        query = TEST_QUERIES[i % len(TEST_QUERIES)]

        try:
            resp = requests.post(
                f"{BASE_URL}/message", json={"message": query, "user_id": USER_ID}, timeout=60
            )
            data = resp.json()

            if data.get("error"):
                print(f"[{i + 1}/50] ERROR: {data['error']}")
                errors += 1
            else:
                response = data.get("response", "")
                # Show first 60 chars of response
                print(f"[{i + 1}/50] {query[:40]:<40} -> {response[:60]}...")
                success += 1

        except Exception as e:
            print(f"[{i + 1}/50] EXCEPTION: {e}")
            errors += 1

        # Small delay between requests
        time.sleep(0.5)

    print("=" * 60)
    print(f"Complete: {success} success, {errors} errors")
    print("Check Langfuse for summarization events!")


if __name__ == "__main__":
    main()
