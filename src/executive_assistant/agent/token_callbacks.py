"""Token usage callback handler for LangChain."""

import logging
import time
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import BaseMessage
from langchain_core.outputs import LLMResult

logger = logging.getLogger(__name__)


class TokenUsageCallback(BaseCallbackHandler):
    """Callback handler that logs token usage from LLM calls."""
    
    def __init__(self):
        self._start_time: float | None = None
        self._input_tokens = 0
        self._output_tokens = 0
    
    def on_llm_start(
        self,
        serialized: dict[str, Any] | None,
        prompts: list[str],
        **kwargs: Any,
    ) -> None:
        """Called when LLM starts."""
        self._start_time = time.time()
        self._input_tokens = 0
        self._output_tokens = 0
    
    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Called when LLM ends - log token usage."""
        elapsed = time.time() - (self._start_time or time.time())
        
        # Extract token usage from response
        total_input = 0
        total_output = 0
        
        for gen in response.generations:
            for g in gen:
                # Try to get usage from generation info
                if hasattr(g, 'generation_info') and g.generation_info:
                    usage = g.generation_info.get('token_usage') or g.generation_info.get('usage')
                    if usage:
                        total_input += usage.get('prompt_tokens', 0) or usage.get('input_tokens', 0)
                        total_output += usage.get('completion_tokens', 0) or usage.get('output_tokens', 0)
                
                # Try message usage_metadata
                if hasattr(g, 'message') and g.message:
                    msg = g.message
                    if hasattr(msg, 'usage_metadata') and msg.usage_metadata:
                        total_input += msg.usage_metadata.get('input_tokens', 0)
                        total_output += msg.usage_metadata.get('output_tokens', 0)
        
        total = total_input + total_output
        if total > 0:
            logger.info(f"🤖 LLM_USAGE: {elapsed:.2f}s | tokens: in={total_input} out={total_output} total={total}")
        else:
            logger.debug(f"🤖 LLM_CALL: {elapsed:.2f}s (no token usage available)")
    
    def on_llm_error(self, error: BaseException, **kwargs: Any) -> None:
        """Called on LLM error."""
        elapsed = time.time() - (self._start_time or time.time())
        logger.warning(f"🤖 LLM_ERROR: {elapsed:.2f}s | error={error}")
