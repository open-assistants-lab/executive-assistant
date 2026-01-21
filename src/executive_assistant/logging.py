"""Logging configuration using Loguru.

Provides structured logging with colorized console output and optional file logging.
Bridges stdlib logging to Loguru for consistent output across all libraries.
"""

import logging
import sys
from pathlib import Path

from loguru import logger

from executive_assistant.config.settings import settings


def configure_logging(
    log_level: str | None = None,
    log_file: str | Path | None = None,
    rotation: str = "10 MB",
    retention: str = "7 days",
) -> None:
    """
    Configure Loguru logging for the application.

    Args:
        log_level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL). Defaults to INFO.
        log_file: Optional path to log file. If None, only console logging is used.
        rotation: Log file rotation size (e.g., "10 MB", "1 day").
        retention: How long to keep log files (e.g., "7 days", "1 week").

    Examples:
        >>> configure_logging()  # Default console logging at INFO level
        >>> configure_logging(log_level="DEBUG")  # Debug level
        >>> configure_logging(log_file="executive_assistant.log")  # With file logging
    """
    # Remove default handler
    logger.remove()

    # Determine log level from settings or parameter
    level = log_level or getattr(settings, "LOG_LEVEL", "INFO")

    # Add console handler with colorized output
    logger.add(
        sys.stdout,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        ),
        level=level,
        colorize=True,
        backtrace=True,
        diagnose=True,
    )

    # Optional: Add file handler
    if log_file:
        logger.add(
            log_file,
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
            level=level,
            rotation=rotation,
            retention=retention,
            compression="zip",  # Compress rotated logs
            backtrace=True,
            diagnose=True,
        )

    # Intercept stdlib logging and redirect to Loguru
    # This ensures that logs from third-party libraries also use Loguru formatting
    class InterceptHandler(logging.Handler):
        """Intercept stdlib logging messages and redirect to Loguru."""

        def emit(self, record: logging.LogRecord) -> None:
            # Get corresponding Loguru level if it exists
            try:
                level = logger.level(record.levelname).name
            except ValueError:
                level = record.levelno

            # Find the caller from the original stack
            frame, depth = logging.currentframe(), 2
            while frame.f_code.co_filename == logging.__file__:
                frame = frame.f_back
                depth += 1

            logger.opt(depth=depth, exception=record.exc_info).log(
                level, record.getMessage()
            )

    # Configure stdlib logging to use our intercept handler
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    # Silence noisy loggers
    for logger_name in ["httpx", "httpcore", "uvicorn"]:
        logging.getLogger(logger_name).setLevel(logging.WARNING)





def format_log_context(kind: str, **fields: object) -> str:
    """
    Format a log context prefix for consistent, searchable logs.

    Example:
        [kind=message channel=telegram user=anon_telegram_123 conversation=123 type=status]
    """
    parts: list[str] = [f"kind={kind}"]
    for key, value in fields.items():
        if value is None or value == "":
            continue
        parts.append(f"{key}={value}")
    return f"[{' '.join(parts)}]"


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
