from __future__ import annotations

import logging

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

logger = logging.getLogger(__name__)


async def delete_thread_checkpoint(database_url: str, thread_id: str | None) -> bool:
    """Delete checkpoint history for a thread ID.

    Returns True when deletion was attempted successfully, False otherwise.
    """
    if not thread_id:
        return False

    db_uri = database_url.replace("postgresql+asyncpg://", "postgresql://")
    try:
        async with AsyncPostgresSaver.from_conn_string(db_uri) as checkpointer:
            await checkpointer.adelete_thread(thread_id)
        return True
    except Exception:
        logger.exception("Failed to delete checkpoint thread: %s", thread_id)
        return False
