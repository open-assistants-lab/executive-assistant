"""Resource cleanup utilities for graceful shutdown.

This module provides functions to properly release resources on application shutdown,
including database connections, caches, and file handles.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Track resources that need cleanup
_lancedb_connections: list[Any] = []
_cache_clear_functions: list[tuple[str, Any]] = []


def register_lancedb_connection(conn: Any) -> None:
    """Register a LanceDB connection for cleanup on shutdown.
    
    Args:
        conn: LanceDB connection to register
    """
    _lancedb_connections.append(conn)
    logger.debug(f"Registered LanceDB connection for cleanup: {conn}")


def register_cache_clear(name: str, clear_func: Any) -> None:
    """Register a cache clear function for cleanup on shutdown.
    
    Args:
        name: Name of the cache (for logging)
        clear_func: Function to call to clear the cache
    """
    _cache_clear_functions.append((name, clear_func))
    logger.debug(f"Registered cache clear function: {name}")


def cleanup_all() -> None:
    """Cleanup all registered resources.
    
    This should be called during application shutdown to ensure
    all resources are properly released.
    """
    logger.info("Starting resource cleanup...")
    
    # Clear all registered caches
    for name, clear_func in _cache_clear_functions:
        try:
            clear_func()
            logger.debug(f"Cleared cache: {name}")
        except Exception as e:
            logger.warning(f"Failed to clear cache {name}: {e}")
    
    _cache_clear_functions.clear()
    
    # Close LanceDB connections
    for conn in _lancedb_connections:
        try:
            # LanceDB doesn't have explicit close, but we can clear references
            if hasattr(conn, 'close'):
                conn.close()
            logger.debug(f"Closed LanceDB connection: {conn}")
        except Exception as e:
            logger.warning(f"Failed to close LanceDB connection: {e}")
    
    _lancedb_connections.clear()
    
    # Clear global checkpointer
    try:
        from executive_assistant.storage.checkpoint import close_checkpointer
        close_checkpointer()
        logger.debug("Closed checkpointer")
    except Exception as e:
        logger.warning(f"Failed to close checkpointer: {e}")
    
    # Clear MCP client cache
    try:
        from executive_assistant.tools.registry import clear_mcp_cache
        clear_mcp_cache()
        logger.debug("Cleared MCP client cache")
    except Exception as e:
        logger.warning(f"Failed to clear MCP cache: {e}")
    
    logger.info("Resource cleanup complete")


def reset_connection_cache() -> None:
    """Reset the LanceDB connection cache."""
    try:
        from executive_assistant.storage.lancedb_storage import reset_connection_cache as lancedb_reset
        lancedb_reset()
        logger.debug("Reset LanceDB connection cache")
    except Exception as e:
        logger.warning(f"Failed to reset LanceDB cache: {e}")


# Auto-register known caches on module import
def _auto_register_caches() -> None:
    """Automatically register known cache clear functions."""
    try:
        from executive_assistant.storage.lancedb_storage import reset_connection_cache
        register_cache_clear("lancedb_connections", reset_connection_cache)
    except ImportError:
        pass


_auto_register_caches()
