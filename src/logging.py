"""Logging module for Executive Assistant."""

import os
import json
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from contextlib import contextmanager

from dotenv import load_dotenv

load_dotenv()

from src.config import get_settings


class Logger:
    """Logger for Executive Assistant - logs to JSONL and Langfuse."""

    def __init__(self):
        settings = get_settings()
        config = settings.observability.logging

        self.enabled = config.enabled
        self.level = config.level
        self.json_dir = Path(config.json_dir)

        if self.enabled:
            self.json_dir.mkdir(parents=True, exist_ok=True)

        # Langfuse setup
        self.langfuse = None
        self._init_langfuse()

    def _init_langfuse(self):
        """Initialize Langfuse if available."""
        settings = get_settings()
        config = settings.observability.langfuse

        if not config.enabled:
            return

        public_key = os.environ.get("LANGFUSE_PUBLIC_KEY") or config.public_key
        secret_key = os.environ.get("LANGFUSE_SECRET_KEY") or config.secret_key
        host = os.environ.get("LANGFUSE_HOST") or config.host

        if public_key and secret_key:
            try:
                from langfuse import Langfuse

                self.langfuse = Langfuse(
                    public_key=public_key,
                    secret_key=secret_key,
                    host=host,
                )
                print(f"Logger: Langfuse enabled")
            except Exception as e:
                print(f"Logger: Langfuse init failed: {e}")
        else:
            print(f"Logger: Langfuse not configured")

    def _get_log_file(self) -> Path:
        """Get today's log file path."""
        today = datetime.now().strftime("%Y-%m-%d")
        return self.json_dir / f"{today}.jsonl"

    def log(self, event: str, data: dict[str, Any], user_id: str = "default"):
        """Log an event to JSONL and optionally to Langfuse."""
        if not self.enabled:
            return

        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event": event,
            "user_id": user_id,
            **data,
        }

        # Write to JSONL
        with open(self._get_log_file(), "a") as f:
            f.write(json.dumps(log_entry) + "\n")

        # Send to Langfuse if available
        if self.langfuse and event in ["agent.start", "agent.end", "tool.use"]:
            self._log_to_langfuse(log_entry)

    def _log_to_langfuse(self, entry: dict):
        """Log to Langfuse."""
        try:
            event = entry.get("event")

            if event == "agent.start":
                trace = self.langfuse.trace(
                    name="agent",
                    user_id=entry.get("user_id"),
                    metadata=entry,
                )
                entry["_langfuse_trace_id"] = trace.id

            elif event == "agent.end":
                # Update trace with end time
                trace_id = entry.get("_langfuse_trace_id")
                if trace_id:
                    # Langfuse traces are auto-tracked, just add final data
                    pass

            elif event == "tool.use":
                # Log as generation
                self.langfuse.generation(
                    name=entry.get("tool_name", "tool"),
                    user_id=entry.get("user_id"),
                    input=entry.get("input"),
                    output=entry.get("output"),
                    model=entry.get("model"),
                    metadata=entry,
                )

        except Exception as e:
            print(f"Logger: Langfuse log failed: {e}")

    @contextmanager
    def timer(self, event: str, data: Optional[dict] = None, user_id: str = "default"):
        """Context manager for timing operations."""
        if not self.enabled:
            yield
            return

        data = data or {}
        start_time = time.time()
        run_id = str(uuid.uuid4())

        data["run_id"] = run_id
        data["level"] = self.level
        data["started_at"] = datetime.now().isoformat()

        self.log(f"{event}.start", data, user_id)

        try:
            yield
        except Exception as e:
            error_data = {
                **data,
                "error": str(e),
                "error_type": type(e).__name__,
            }
            self.log(f"{event}.error", error_data, user_id)
            raise
        finally:
            duration_ms = int((time.time() - start_time) * 1000)
            data["duration_ms"] = duration_ms
            data["completed_at"] = datetime.now().isoformat()
            self.log(f"{event}.end", data, user_id)


# Global logger instance
_logger: Optional[Logger] = None


def get_logger() -> Logger:
    """Get or create logger instance."""
    global _logger
    if _logger is None:
        _logger = Logger()
    return _logger


def log_event(event: str, data: dict, user_id: str = "default"):
    """Log an event."""
    get_logger().log(event, data, user_id)


@contextmanager
def timer(event: str, data: Optional[dict] = None, user_id: str = "default"):
    """Timer context manager for logging duration."""
    yield get_logger().timer(event, data, user_id)
