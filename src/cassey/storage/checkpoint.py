"""Checkpoint storage configuration using PostgreSQL."""

import asyncio
from functools import partial
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg import Connection
from psycopg_pool import ConnectionPool

from cassey.config.settings import settings

# Global checkpointer instance
_checkpointer: BaseCheckpointSaver | None = None


class SanitizingCheckpointSaver(BaseCheckpointSaver):
    """
    Wrapper that sanitizes checkpoint state on load to prevent corruption errors.

    This wrapper wraps another checkpointer and automatically sanitizes the
    loaded state by removing orphaned tool_calls before LangGraph processes it.

    This prevents OpenAI 400 errors where an assistant message with tool_calls
    must be followed by tool messages.
    """

    def __init__(self, base_saver: BaseCheckpointSaver) -> None:
        """
        Initialize the sanitizing wrapper.

        Args:
            base_saver: The underlying checkpointer to wrap.
        """
        self._base_saver = base_saver

    def _sanitize_checkpoint(self, checkpoint_tuple: Any) -> Any:
        """Sanitize checkpoint by removing orphaned tool_calls."""
        if checkpoint_tuple is None or checkpoint_tuple.checkpoint is None:
            return checkpoint_tuple

        # Import here to avoid circular dependency
        from cassey.agent.checkpoint_utils import sanitize_corrupted_messages

        checkpoint = checkpoint_tuple.checkpoint

        # Get channel_values which contains the messages
        channel_values = checkpoint.get("channel_values", {})
        if not isinstance(channel_values, dict):
            return checkpoint_tuple

        messages = channel_values.get("messages", [])
        if not messages:
            return checkpoint_tuple

        # Try to sanitize - if issues are found, update the checkpoint
        try:
            sanitized_messages, actions = sanitize_corrupted_messages(messages)

            # Only update if sanitization actually changed something
            if len(sanitized_messages) != len(messages):
                # Create a new checkpoint tuple with sanitized messages
                import copy
                new_checkpoint = copy.deepcopy(checkpoint)
                new_checkpoint["channel_values"]["messages"] = sanitized_messages

                # Create a new checkpoint tuple with the sanitized checkpoint
                # CheckpointTuple has (checkpoint, metadata, config)
                if hasattr(checkpoint_tuple, "_asdict"):
                    # It's a NamedTuple
                    from collections import namedtuple
                    CheckpointTuple = type(checkpoint_tuple)
                    return CheckpointTuple(
                        checkpoint=new_checkpoint,
                        metadata=checkpoint_tuple.metadata,
                        config=checkpoint_tuple.config,
                    )
                elif hasattr(checkpoint_tuple, "checkpoint"):
                    # Simple object with checkpoint attribute
                    checkpoint_tuple.checkpoint = new_checkpoint

        except Exception as e:
            # If sanitization fails, log but don't break the flow
            print(f"Checkpoint sanitization failed: {e}")

        return checkpoint_tuple

    # Delegate sync methods with sanitization
    def get(self, config: Any, /, **kwargs: Any) -> Any:
        result = self._base_saver.get(config, **kwargs)
        return self._sanitize_checkpoint(result)

    def get_tuple(self, config: Any, /, **kwargs: Any) -> Any:
        result = self._base_saver.get_tuple(config, **kwargs)
        return self._sanitize_checkpoint(result)

    def list(self, config: Any, /, **kwargs: Any) -> Any:
        return self._base_saver.list(config, **kwargs)

    def put(
        self,
        config: Any,
        checkpoint: Any,
        metadata: Any,
        new_versions: Any,
        **kwargs: Any,
    ) -> Any:
        return self._base_saver.put(config, checkpoint, metadata, new_versions, **kwargs)

    def put_writes(
        self,
        config: Any,
        writes: Any,
        task_id: str,
        task_path: str = "",
        **kwargs: Any,
    ) -> Any:
        return self._base_saver.put_writes(config, writes, task_id, task_path, **kwargs)

    # Async methods with sanitization
    async def aget(self, config: Any, /, **kwargs: Any) -> Any:
        result = await self._base_saver.aget(config, **kwargs)
        return self._sanitize_checkpoint(result)

    async def aget_tuple(self, config: Any, /, **kwargs: Any) -> Any:
        result = await self._base_saver.aget_tuple(config, **kwargs)
        return self._sanitize_checkpoint(result)

    async def alist(self, config: Any, /, **kwargs: Any) -> Any:
        return await self._base_saver.alist(config, **kwargs)

    async def aput(
        self,
        config: Any,
        checkpoint: Any,
        metadata: Any,
        new_versions: Any,
        **kwargs: Any,
    ) -> Any:
        return await self._base_saver.aput(config, checkpoint, metadata, new_versions, **kwargs)

    async def aput_writes(
        self,
        config: Any,
        writes: Any,
        task_id: str,
        task_path: str = "",
        **kwargs: Any,
    ) -> Any:
        return await self._base_saver.aput_writes(config, writes, task_id, task_path, **kwargs)

    # Pass through other attributes
    def __getattr__(self, name: str) -> Any:
        return getattr(self._base_saver, name)

    @property
    def conn(self) -> Connection:
        """Get the database connection from the base saver."""
        return self._base_saver.conn if hasattr(self._base_saver, 'conn') else None


class AsyncPostgresSaver(BaseCheckpointSaver):
    """
    Async-compatible wrapper for PostgresSaver.

    The standard PostgresSaver doesn't implement async methods.
    This wrapper adds async support by running sync methods in a thread pool.
    """

    def __init__(self, conn: Connection) -> None:
        self._saver = PostgresSaver(conn)

    # Delegate all sync methods to the underlying saver
    def get(self, config: Any, /, **kwargs: Any) -> Any:
        return self._saver.get(config, **kwargs)

    def get_tuple(self, config: Any, /, **kwargs: Any) -> Any:
        return self._saver.get_tuple(config, **kwargs)

    def list(self, config: Any, /, **kwargs: Any) -> Any:
        return self._saver.list(config, **kwargs)

    def put(
        self,
        config: Any,
        checkpoint: Any,
        metadata: Any,
        new_versions: Any,
        **kwargs: Any,
    ) -> Any:
        return self._saver.put(config, checkpoint, metadata, new_versions, **kwargs)

    def put_writes(
        self,
        config: Any,
        writes: Any,
        task_id: str,
        task_path: str = "",
        **kwargs: Any,
    ) -> Any:
        return self._saver.put_writes(config, writes, task_id, task_path, **kwargs)

    # Implement async methods using asyncio.to_thread
    async def aget(self, config: Any, /, **kwargs: Any) -> Any:
        return await asyncio.to_thread(self.get, config, **kwargs)

    async def aget_tuple(self, config: Any, /, **kwargs: Any) -> Any:
        return await asyncio.to_thread(self.get_tuple, config, **kwargs)

    async def alist(self, config: Any, /, **kwargs: Any) -> Any:
        return await asyncio.to_thread(self.list, config, **kwargs)

    async def aput(
        self,
        config: Any,
        checkpoint: Any,
        metadata: Any,
        new_versions: Any,
        **kwargs: Any,
    ) -> Any:
        return await asyncio.to_thread(
            self.put, config, checkpoint, metadata, new_versions, **kwargs
        )

    async def aput_writes(
        self,
        config: Any,
        writes: Any,
        task_id: str,
        task_path: str = "",
        **kwargs: Any,
    ) -> Any:
        return await asyncio.to_thread(
            self.put_writes, config, writes, task_id, task_path, **kwargs
        )

    # Pass through other attributes
    def __getattr__(self, name: str) -> Any:
        return getattr(self._saver, name)

    @property
    def conn(self) -> Connection:
        return self._saver.conn


def get_checkpointer(
    storage_type: str | None = None,
    connection_string: str | None = None,
):
    """
    Get a checkpointer instance for conversation state persistence.

    Note: For PostgreSQL with async operations, use get_async_checkpointer().

    Args:
        storage_type: Storage backend ("postgres", "memory").
        connection_string: Database connection string.

    Returns:
        Configured checkpointer instance.
    """
    storage = storage_type or settings.CHECKPOINT_STORAGE

    if storage == "postgres":
        # For postgres, we need async - use memory as fallback
        return MemorySaver()

    else:  # memory
        return MemorySaver()


async def get_async_checkpointer(
    storage_type: str | None = None,
    connection_string: str | None = None,
    sanitize: bool = True,
):
    """
    Get an async checkpointer instance for conversation state persistence.

    This creates an AsyncPostgresSaver for PostgreSQL, wrapped with
    SanitizingCheckpointSaver to prevent corruption errors.

    Args:
        storage_type: Storage backend ("postgres", "memory").
        connection_string: Database connection string.
        sanitize: Whether to wrap with sanitizing layer (default True).

    Returns:
        Configured async checkpointer instance.
    """
    global _checkpointer

    storage = storage_type or settings.CHECKPOINT_STORAGE

    if storage == "postgres":
        # Return existing checkpointer if already initialized
        if _checkpointer is not None:
            return _checkpointer

        conn_string = connection_string or settings.POSTGRES_URL

        # Create sync connection
        conn = Connection.connect(
            conn_string,
            autocommit=True,
            prepare_threshold=0,
        )

        # Create async-compatible wrapper
        base_saver = AsyncPostgresSaver(conn)

        # Initialize the schema
        base_saver._saver.setup()

        # Wrap with sanitizing layer to prevent corruption errors
        if sanitize:
            _checkpointer = SanitizingCheckpointSaver(base_saver)
        else:
            _checkpointer = base_saver

        return _checkpointer

    else:  # memory
        _checkpointer = MemorySaver()
        return _checkpointer


async def close_checkpointer() -> None:
    """Close the checkpointer connection if applicable."""
    global _checkpointer

    if _checkpointer is not None and hasattr(_checkpointer, 'conn'):
        _checkpointer.conn.close()
        _checkpointer = None
