#!/usr/bin/env python3
"""Gmail auto-sync daemon for HybridDB cache.

Two modes:
  --poll     Poll Gmail API every N seconds (simple, no GCP infra needed)
  --watch    Real-time push via gws +watch Pub/Sub (requires GCP project)

Usage:
  python3 scripts/gmail_daemon.py --poll --interval 300           # poll every 5 min
  python3 scripts/gmail_daemon.py --watch --project gws-cli-20260428  # real-time
"""

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
os.chdir(str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT))

from src.storage.gmail_cache import get_gmail_cache, _UPSERT_FLUSH, _fetch_one_email

SYNC_STATE_FILE = Path.home() / ".config" / "gws" / "sync_state.json"


def load_sync_state() -> dict:
    if SYNC_STATE_FILE.exists():
        try:
            return json.loads(SYNC_STATE_FILE.read_text())
        except Exception:
            pass
    return {"last_message_id": None, "last_ts": None}


def save_sync_state(state: dict) -> None:
    SYNC_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    SYNC_STATE_FILE.write_text(json.dumps(state))


def poll_loop(interval: int = 300):
    """Poll Gmail API for new messages and upsert into cache."""
    cache = get_gmail_cache()
    state = load_sync_state()
    last_id = state.get("last_message_id")
    running = True

    def handle_signal(sig, frame):
        nonlocal running
        print("\nStopping...")
        running = False

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    print(f"Polling every {interval}s. Last synced ID: {last_id or 'none (will fetch recent)'}")
    print("Press Ctrl-C to stop.\n")

    while running:
        try:
            # List recent messages (newest first), up to 50
            params = {"userId": "me", "maxResults": 50}
            cmd = [
                "gws", "gmail", "users", "messages", "list",
                "--params", json.dumps(params), "--format", "json",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                print(f"[{_now()}] list error: {result.stderr[:100]}")
                time.sleep(interval)
                continue

            messages = json.loads(result.stdout).get("messages", [])
            if not messages:
                print(f"[{_now()}] no messages", end="\r", flush=True)
                time.sleep(interval)
                continue

            # Stop when we hit the last known ID
            new_messages = []
            for msg in messages:
                if msg["id"] == last_id:
                    break
                new_messages.append(msg)

            if not new_messages:
                print(f"[{_now()}] nothing new         ", end="\r", flush=True)
                time.sleep(interval)
                continue

            # Fetch details and upsert
            count = 0
            batch: list[dict] = []
            for msg in reversed(new_messages):  # oldest first
                email_data = _fetch_one_email(msg["id"], msg.get("threadId", msg["id"]), fetch_body=False)
                if email_data:
                    batch.append(email_data)
                    count += 1

                if len(batch) >= _UPSERT_FLUSH:
                    cache.upsert_batch(batch)
                    batch.clear()

            if batch:
                cache.upsert_batch(batch)

            # Update state
            last_id = messages[0]["id"]
            save_sync_state({"last_message_id": last_id, "last_ts": int(time.time())})

            print(f"[{_now()}] synced {count} new | cache: {cache.count()}")

        except subprocess.TimeoutExpired:
            print(f"[{_now()}] timeout")
        except Exception as e:
            print(f"[{_now()}] error: {e}")

        time.sleep(interval)


def watch_mode(project: str, label_ids: str = "INBOX"):
    """Run gws +watch --once in a loop for real-time-like behavior.

    This avoids the 7-day watch expiry issue by using --once per cycle.
    For true real-time, use --watch with a long-running gws +watch process.
    """
    cache = get_gmail_cache()
    running = True

    def handle_signal(sig, frame):
        nonlocal running
        print("\nStopping...")
        running = False

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    print(f"Watch mode: project={project}, labels={label_ids}")
    print("Press Ctrl-C to stop.\n")

    while running:
        try:
            cmd = [
                "gws", "gmail", "+watch",
                "--project", project,
                "--label-ids", label_ids,
                "--once",
                "--msg-format", "metadata",
                "--format", "json",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

            if result.returncode != 0:
                print(f"[{_now()}] watch error: {result.stderr[:100]}")
                time.sleep(10)
                continue

            # gws +watch outputs NDJSON — one JSON object per line in stdout
            # (stderr has keyring + Pub/Sub diagnostics)
            count = 0
            for line in result.stdout.strip().split("\n"):
                line = line.strip()
                if not line:
                    continue
                try:
                    msg_data = json.loads(line)
                    # msg_data might be wrapped in Pub/Sub envelope
                    email_data = _extract_watch_message(msg_data)
                    if email_data:
                        cache.upsert(email_data)
                        count += 1
                except json.JSONDecodeError:
                    pass

            if count:
                cache.db.process_journal(limit=10000)
                print(f"[{_now()}] watch synced {count} new | cache: {cache.count()}")
            else:
                print(f"[{_now()}] watch idle", end="\r", flush=True)

        except subprocess.TimeoutExpired:
            print(f"[{_now()}] watch timeout")
        except Exception as e:
            print(f"[{_now()}] watch error: {e}")

        time.sleep(5)


def _extract_watch_message(data: dict) -> dict | None:
    """Extract Gmail message from Pub/Sub watch envelope."""
    # Try direct Gmail API format
    if "id" in data and "threadId" in data:
        msg_id = data["id"]
        thread_id = data.get("threadId", msg_id)
        return _fetch_one_email(msg_id, thread_id, fetch_body=False)

    # Try Pub/Sub envelope { message: { data: base64(historyId+emailAddress) } }
    if "message" in data:
        inner = data["message"]
        if "historyId" in inner:
            # This is a history notification, not a full message
            # We'd need to list recent messages to find what changed
            return None

    return None


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def main():
    parser = argparse.ArgumentParser(description="Gmail auto-sync daemon")
    parser.add_argument("--poll", action="store_true", help="Poll mode (simple, no GCP infra)")
    parser.add_argument("--watch", action="store_true", help="Watch mode (real-time, needs GCP Pub/Sub)")
    parser.add_argument("--interval", type=int, default=300, help="Poll interval in seconds (default: 300)")
    parser.add_argument("--project", type=str, default="gws-cli-20260428", help="GCP project for watch mode")
    parser.add_argument("--labels", type=str, default="INBOX", help="Labels for watch mode")
    args = parser.parse_args()

    if args.watch:
        watch_mode(args.project, args.labels)
    elif args.poll:
        poll_loop(args.interval)
    else:
        # Default: poll mode
        print("No mode specified. Using --poll with 5-minute interval.\n")
        poll_loop(args.interval)


if __name__ == "__main__":
    main()
