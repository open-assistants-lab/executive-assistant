#!/usr/bin/env python3
"""Test summarization with low threshold to verify callback works."""

import requests
import json
import time

USER_ID = "summarization_test"
BASE_URL = "http://localhost:8080"


def check_db_for_summary():
    """Check if summary exists in DB."""
    import subprocess

    result = subprocess.run(
        [
            "sqlite3",
            f"data/users/{USER_ID}/messages/messages.db",
            "SELECT id, role, substr(content, 1, 50) FROM messages WHERE role = 'summary';",
        ],
        capture_output=True,
        text=True,
    )
    return result.stdout


def check_log_for_callback():
    """Check if on_summarize callback was called."""
    import subprocess

    result = subprocess.run(
        ["grep", "message_manager.summarization", "data/logs/2026-03-17.jsonl"],
        capture_output=True,
        text=True,
    )
    return result.stdout


def main():
    print("Testing summarization with LOW threshold (100 tokens)")
    print("=" * 60)

    # First, clear any existing test data
    import subprocess

    subprocess.run(["rm", "-rf", f"data/users/{USER_ID}"], capture_output=True)

    # Send simple messages until we hit the threshold
    # With 100 token trigger, ~10-20 simple messages should trigger it

    test_queries = [
        "hello",
        "hi there",
        "how are you",
        "good",
        "thanks",
        "ok",
        "yes",
        "no",
        "maybe",
        "sure",
        "yes please",
        "no thanks",
        "maybe later",
        "ok got it",
        "sounds good",
        "perfect",
        "great",
        "nice",
        "cool",
        "wow",
    ]

    for i, query in enumerate(test_queries):
        print(f"\nMessage {i + 1}: {query}")

        resp = requests.post(
            f"{BASE_URL}/message",
            json={"message": query, "user_id": USER_ID, "verbose": True},
            timeout=30,
        )

        data = resp.json()
        if data.get("error"):
            print(f"  Error: {data['error']}")
        else:
            # Check verbose data for any indication
            verbose = data.get("verbose_data")
            if verbose and verbose.get("middleware_events"):
                # Check if summarization middleware ran
                summ_events = [
                    e
                    for e in verbose["middleware_events"]
                    if "Summarization" in e.get("name", "") and e.get("event") == "on_chain_end"
                ]
                if summ_events:
                    print(f"  SummarizationMiddleware ran")

        time.sleep(0.3)

    print("\n" + "=" * 60)
    print("CHECKING RESULTS:")
    print("=" * 60)

    # Check DB for summary
    summary_result = check_db_for_summary()
    print(f"\nSummary in DB: {summary_result if summary_result else 'NONE'}")

    # Check logs for callback
    log_result = check_log_for_callback()
    print(f"\nCallback logs found: {len(log_result.split(chr(10)))} lines")
    if log_result:
        print("Last few lines:")
        for line in log_result.split("\n")[-3:]:
            print(f"  {line[:100]}...")


if __name__ == "__main__":
    main()
