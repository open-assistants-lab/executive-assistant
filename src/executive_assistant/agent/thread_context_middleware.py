"""Middleware to ensure thread_id ContextVar propagates to tool execution."""

import logging
import traceback
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain.tools.tool_node import ToolCallRequest

from executive_assistant.storage.thread_storage import get_thread_id, set_thread_id

logger = logging.getLogger(__name__)


class ThreadContextMiddleware(AgentMiddleware):
    """
    Middleware that ensures thread_id ContextVar is preserved during tool execution.

    This fixes the issue where Python ContextVars don't propagate across
    LangGraph's async task boundaries when executing tools.

    Also provides comprehensive error logging for all tool failures.
    """

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler,
    ) -> Any:
        """Wrap tool call to ensure thread_id context is available and log all errors."""
        # Capture current thread_id from context
        thread_id = get_thread_id()
        tool_name = request.tool_call.get('name', 'unknown')
        tool_args = request.tool_call.get('args', {})

        if thread_id:
            # Set it again right before tool execution to ensure it's in this context
            set_thread_id(thread_id)
            logger.debug(f"ThreadContextMiddleware: Restored thread_id={thread_id} before tool={tool_name}")

        # Execute tool with comprehensive error logging
        try:
            result = await handler(request)
            return result
        except Exception as e:
            # Log ALL errors at DEBUG level with full context
            logger.debug(
                f"ERROR in tool '{tool_name}' (thread_id={thread_id}):\n"
                f"  Tool args: {tool_args}\n"
                f"  Error type: {type(e).__name__}\n"
                f"  Error message: {str(e)}\n"
                f"  Full traceback:\n{traceback.format_exc()}"
            )
            # Re-raise to allow retry middleware to handle it
            raise
