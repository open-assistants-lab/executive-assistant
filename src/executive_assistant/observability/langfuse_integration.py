"""Langfuse integration for LLM observability and tracing.

This module provides Langfuse tracing for LangChain agents using the official
CallbackHandler pattern from langfuse.langchain.

Based on: https://langfuse.com/integrations/frameworks/langchain
"""

import logging
from typing import Any

from executive_assistant.config.settings import get_settings

logger = logging.getLogger(__name__)

# Singleton Langfuse client
_langfuse_client = None
_callback_handler = None


def get_langfuse_client():
    """Get or create the Langfuse client singleton.

    Returns None if Langfuse is not configured or import fails.
    """
    global _langfuse_client

    if _langfuse_client is not None:
        return _langfuse_client

    settings = get_settings()

    # Check if Langfuse is configured
    logger.debug(f"Checking Langfuse config: secret_key_set={bool(settings.LANGFUSE_SECRET_KEY)}, public_key_set={bool(settings.LANGFUSE_PUBLIC_KEY)}")
    if not settings.LANGFUSE_SECRET_KEY or not settings.LANGFUSE_PUBLIC_KEY:
        logger.debug("Langfuse not configured (missing keys)")
        return None

    try:
        from langfuse import Langfuse

        # Initialize client (Langfuse() is the correct API for explicit credentials)
        _langfuse_client = Langfuse(
            secret_key=settings.LANGFUSE_SECRET_KEY,
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            base_url=settings.LANGFUSE_BASE_URL,
        )

        logger.info(
            f"Langfuse client initialized (environment={settings.LANGFUSE_TRACING_ENVIRONMENT}, "
            f"base_url={settings.LANGFUSE_BASE_URL})"
        )

        return _langfuse_client

    except ImportError:
        logger.warning("langfuse package not installed. Run: pip install langfuse")
        return None
    except Exception as e:
        logger.error(f"Failed to initialize Langfuse: {e}")
        return None


def get_callback_handler():
    """Get or create the Langfuse CallbackHandler for LangChain.

    Returns None if Langfuse is not configured.

    Usage:
        handler = get_callback_handler()
        if handler:
            agent.invoke(input_data, config={"callbacks": [handler]})
    """
    global _callback_handler

    # Return cached handler if already created
    if _callback_handler is not None:
        return _callback_handler

    # Check if client is available
    logger.debug("Checking if Langfuse client is available...")
    if get_langfuse_client() is None:
        logger.debug("Langfuse client not available, cannot create callback handler")
        return None

    try:
        from langfuse.langchain import CallbackHandler

        # Create handler (no args needed in v3+)
        _callback_handler = CallbackHandler()

        logger.info("Langfuse CallbackHandler created successfully")

        return _callback_handler

    except ImportError:
        logger.warning("langfuse.langchain not available. Run: pip install langfuse")
        return None
    except Exception as e:
        logger.error(f"Failed to create Langfuse CallbackHandler: {e}")
        return None


def flush_langfuse():
    """Manually flush any pending Langfuse events.

    Should be called on application shutdown to ensure all traces are sent.
    """
    client = get_langfuse_client()
    if client:
        try:
            client.flush()
            logger.debug("Langfuse flushed manually")
        except Exception as e:
            logger.error(f"Error flushing Langfuse: {e}")


def shutdown_langfuse():
    """Shutdown Langfuse client.

    Should be called on application shutdown.
    """
    global _langfuse_client, _callback_handler

    client = get_langfuse_client()
    if client:
        try:
            client.shutdown()
            logger.info("Langfuse client shutdown")
        except Exception as e:
            logger.error(f"Error shutting down Langfuse: {e}")
        finally:
            _langfuse_client = None
            _callback_handler = None


def is_enabled() -> bool:
    """Check if Langfuse tracing is enabled and configured."""
    return get_langfuse_client() is not None


def get_tracing_environment() -> str | None:
    """Get the current Langfuse tracing environment."""
    settings = get_settings()
    return settings.LANGFUSE_TRACING_ENVIRONMENT if settings.LANGFUSE_SECRET_KEY else None


def create_trace_metadata(
    user_id: str | None = None,
    session_id: str | None = None,
    tags: list[str] | None = None,
    **metadata: Any,
) -> dict[str, Any]:
    """Create Langfuse trace metadata for LangChain config.

    Usage:
        metadata = create_trace_metadata(
            user_id="user_123",
            session_id="session_456",
            tags=["production", "api"],
            custom_field="value"
        )
        agent.invoke(input_data, config={"callbacks": [handler], "metadata": metadata})

    Args:
        user_id: User identifier for the trace
        session_id: Session identifier for the trace
        tags: Tags to label the trace
        **metadata: Additional metadata fields

    Returns:
        Dictionary formatted for LangChain config["metadata"]
    """
    trace_metadata: dict[str, Any] = {}

    if user_id:
        trace_metadata["langfuse_user_id"] = user_id
    if session_id:
        trace_metadata["langfuse_session_id"] = session_id
    if tags:
        trace_metadata["langfuse_tags"] = tags

    # Add any additional metadata
    trace_metadata.update(metadata)

    return trace_metadata
