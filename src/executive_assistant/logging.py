"""Logging configuration using Loguru.

Provides structured logging with colorized console output and optional file logging.
Bridges stdlib logging to Loguru for consistent output across all libraries.
"""

import atexit
import logging
import queue
import sys
from logging.handlers import QueueHandler, QueueListener, RotatingFileHandler
from pathlib import Path

from loguru import logger

from executive_assistant.config.settings import settings


_queue_listener: QueueListener | None = None

def configure_logging(
    log_level: str | None = None,
    log_file: str | Path | None = None,
    rotation: str = "10 MB",
    retention: str = "7 days",
) -> None:
    """
    Configure async logging using stdlib QueueHandler + QueueListener.

    Args:
        log_level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL). Defaults to INFO.
        log_file: Optional path to log file. If None, only console logging is used.
        rotation: Log file rotation size (e.g., "10 MB", "1 day").
        retention: How long to keep log files (e.g., "7 days", "1 week").
    """
    global _queue_listener

    # Remove default Loguru handler
    logger.remove()

    level = log_level or getattr(settings, "LOG_LEVEL", "INFO")
    file_path = log_file or getattr(settings, "LOG_FILE", None)

    # Build stdlib handlers
    fmt = "%Y-%m-%d %H:%M:%S.%f"
    formatter = logging.Formatter(
        fmt="%(asctime)s.%(msecs)03d | %(levelname)-5s | %(message)s",
        datefmt="%H:%M:%S",
    )

    handlers: list[logging.Handler] = []
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)
    handlers.append(console_handler)

    if file_path:
        max_bytes = _parse_bytes(rotation)
        backup_count = _parse_retention(retention)
        file_handler = RotatingFileHandler(
            file_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        handlers.append(file_handler)

    # Queue-based async logging
    log_queue: queue.SimpleQueue = queue.SimpleQueue()
    queue_handler = QueueHandler(log_queue)

    root = logging.getLogger()
    root.handlers = [queue_handler]
    root.setLevel(level)

    if _queue_listener:
        _queue_listener.stop()

    _queue_listener = QueueListener(log_queue, *handlers, respect_handler_level=True)
    _queue_listener.start()
    atexit.register(_queue_listener.stop)

    # Route Loguru into stdlib logging (which is async via the queue)
    def _loguru_sink(message):
        record = message.record
        exc = record.get("exception")
        if exc:
            exc_info = (exc.type, exc.value, exc.traceback)
        else:
            exc_info = None
        logging.getLogger(record["name"]).log(
            record["level"].no,
            record["message"],
            exc_info=exc_info,
        )

    logger.add(_loguru_sink, level=level, backtrace=True, diagnose=True)

    # Silence noisy loggers
    for logger_name in ["httpx", "httpcore", "uvicorn"]:
        logging.getLogger(logger_name).setLevel(logging.WARNING)




def _parse_bytes(value: str) -> int:
    try:
        parts = value.strip().split()
        number = float(parts[0])
        unit = parts[1].lower() if len(parts) > 1 else "b"
        if unit.startswith("kb"):
            return int(number * 1024)
        if unit.startswith("mb"):
            return int(number * 1024 * 1024)
        if unit.startswith("gb"):
            return int(number * 1024 * 1024 * 1024)
        return int(number)
    except Exception:
        return 10 * 1024 * 1024


def _parse_retention(value: str) -> int:
    try:
        for token in value.split():
            if token.isdigit():
                return max(1, int(token))
    except Exception:
        pass
    return 7



def format_log_context(kind: str, **fields: object) -> str:
    """
    Format a log context prefix for consistent, human-readable logs.

    Example:
        CH=telegram USER=anon_telegram_123 CONV=123 TYPE=status | recv_text
    """
    channel = fields.pop("channel", None)
    component = fields.pop("component", None)

    parts: list[str] = []
    if channel:
        parts.append(f"CH={channel}")
    elif component:
        parts.append(f"SYS={component}")

    key_map = {
        "user": "USER",
        "conversation": "CONV",
        "type": "TYPE",
        "update_id": "UPDATE",
        "message_id": "MSG",
        "tool": "TOOL",
        "scope": "SCOPE",
        "status": "STATUS",
    }

    for key, value in fields.items():
        if value is None or value == "":
            continue
        label = key_map.get(key, key.upper())
        parts.append(f"{label}={value}")

    context = " ".join(parts).strip()
    if context:
        return f"{context} | {kind}"
    return str(kind)


def truncate_log_text(text: str, limit: int = 200) -> str:
    """Trim long log messages while preserving basic readability."""
    if text is None:
        return ""
    cleaned = " ".join(str(text).split())
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[:limit]}..."

def get_logger(name: str | None = None):
    """
    Get a Loguru logger instance.

    Args:
        name: Optional logger name (for module-level logging).

    Returns:
        Loguru logger instance.

    Examples:
        >>> from executive_assistant.logging import get_logger
        >>> logger = get_logger(__name__)
        >>> logger.info("Hello, world!")
    """
    if name:
        return logger.bind(name=name)
    return logger


# Convenience exports
__all__ = ["configure_logging", "format_log_context", "truncate_log_text", "get_logger", "logger"]
