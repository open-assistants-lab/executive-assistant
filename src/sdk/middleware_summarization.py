"""Summarization middleware for reducing token count in conversation history.

SDK-native implementation: replaces src/middleware/summarization.py.
Reimplements LangChain's SummarizationMiddleware from scratch:
- Token counting via tiktoken (cl100k_base encoding)
- Message truncation when token count exceeds threshold
- Summary generation via AgentLoop.run_single()
- Callback on successful summary
- Duplicate prevention guard
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

import tiktoken

from src.app_logging import get_logger
from src.sdk.messages import Message
from src.sdk.middleware import Middleware
from src.sdk.state import AgentState

logger = get_logger()

SummaryCallback = Callable[[str], Awaitable[None]] | Callable[[str], Any]

SUMMARY_SYSTEM_PROMPT = (
    "You are a conversation summarizer. Produce a concise summary that preserves "
    "all key facts, decisions, user preferences, and action items. "
    "Write in third person. Be specific and preserve proper nouns."
)

SUMMARY_USER_TEMPLATE = (
    "Summarize the following conversation segment in 200-500 words:\n\n{conversation}"
)

_APPROX_TOKENS_PER_CHAR = 0.25
_FALLBACK_TOKEN_RATIO = 4


class SummarizationMiddleware(Middleware):
    """Middleware that summarizes conversation history when token count exceeds threshold.

    Token counting uses tiktoken (cl100k_base) with a str-based fallback.
    When the message history exceeds trigger_tokens, the oldest messages are
    summarized and replaced with a single system message containing the summary.
    The most recent keep_tokens worth of messages are always preserved.

    Args:
        trigger_tokens: Start summarization when total tokens exceed this.
        keep_tokens: Always keep at least this many tokens of recent messages.
        model: LLM model identifier for summary generation.
        on_summarize: Optional callback invoked with summary content on success.
    """

    def __init__(
        self,
        trigger_tokens: int = 50000,
        keep_tokens: int = 1000,
        model: str = "ollama:minimax-m2.5",
        on_summarize: SummaryCallback | None = None,
    ):
        self.trigger_tokens = trigger_tokens
        self.keep_tokens = keep_tokens
        self.model = model
        self._on_summarize = on_summarize
        self._last_summary_msg_count: int = 0
        self._encoding: Any = None

    def _get_encoding(self) -> Any:
        if self._encoding is None:
            try:
                self._encoding = tiktoken.get_encoding("cl100k_base")
            except Exception:
                self._encoding = None
        return self._encoding

    def count_tokens(self, text: str) -> int:
        enc = self._get_encoding()
        if enc is not None:
            try:
                return len(enc.encode(text))
            except Exception:
                pass
        return max(1, int(len(text) * _APPROX_TOKENS_PER_CHAR))

    def _count_message_tokens(self, msg: Message) -> int:
        content = msg.content if isinstance(msg.content, str) else json.dumps(msg.content)
        total = self.count_tokens(content)
        total += 4
        if msg.role == "assistant" and msg.tool_calls:
            for tc in msg.tool_calls:
                total += self.count_tokens(tc.name)
                total += self.count_tokens(json.dumps(tc.arguments))
        if msg.role == "tool" and msg.name:
            total += self.count_tokens(msg.name)
        return total

    def _total_tokens(self, messages: list[Message]) -> int:
        return sum(self._count_message_tokens(m) for m in messages)

    def _messages_to_conversation_text(self, messages: list[Message]) -> str:
        lines = []
        for msg in messages:
            role = msg.role
            content = msg.content if isinstance(msg.content, str) else json.dumps(msg.content)
            lines.append(f"{role}: {content}")
        return "\n\n".join(lines)

    async def _generate_summary(self, conversation_text: str) -> str | None:
        try:
            from src.sdk.loop import AgentLoop
            from src.sdk.providers.factory import create_provider

            provider = create_provider(self.model)
            loop = AgentLoop(provider=provider)

            summary_messages = [
                Message.system(SUMMARY_SYSTEM_PROMPT),
                Message.user(SUMMARY_USER_TEMPLATE.format(conversation=conversation_text)),
            ]

            result = await loop.run_single(summary_messages)
            if result:
                content = result.content if isinstance(result.content, str) else str(result.content)
                return content.strip() or None
            return None
        except Exception as e:
            logger.warning(
                "summarization.generation_failed",
                {"error": str(e)},
                user_id="system",
            )
            return None

    async def abefore_model(self, state: AgentState) -> dict[str, Any] | None:
        messages = state.messages
        current_msg_count = len(messages)

        if current_msg_count <= self._last_summary_msg_count and self._last_summary_msg_count > 0:
            logger.debug(
                "summarization.skipped",
                {"reason": "already_summarized_in_cycle", "msg_count": current_msg_count},
                user_id="system",
            )
            return None

        total_tokens = self._total_tokens(messages)

        if total_tokens <= self.trigger_tokens:
            return None

        logger.info(
            "summarization.triggered",
            {
                "total_tokens": total_tokens,
                "trigger_tokens": self.trigger_tokens,
                "msg_count": current_msg_count,
            },
            user_id="system",
        )

        tokens_to_keep = self.keep_tokens
        recent_tokens = 0
        split_idx = len(messages)

        for i in range(len(messages) - 1, -1, -1):
            msg_tokens = self._count_message_tokens(messages[i])
            if recent_tokens + msg_tokens > tokens_to_keep and i < len(messages) - 1:
                split_idx = i + 1
                break
            recent_tokens += msg_tokens
        else:
            split_idx = 1

        if split_idx <= 1:
            logger.warning(
                "summarization.cannot_split",
                {"msg_count": current_msg_count},
                user_id="system",
            )
            return None

        old_messages = messages[:split_idx]
        system_messages = [m for m in old_messages if m.role == "system"]
        non_system_old = [m for m in old_messages if m.role != "system"]

        if not non_system_old:
            return None

        conversation_text = self._messages_to_conversation_text(non_system_old)
        summary_content = await self._generate_summary(conversation_text)

        if summary_content is None:
            logger.warning(
                "summarization.failed_no_summary",
                {"old_msg_count": len(non_system_old)},
                user_id="system",
            )
            return None

        content_lower = summary_content.lower()
        failure_reasons = []
        if "too long to summarize" in content_lower:
            failure_reasons.append("content_too_long_for_summary")
        if "failed to summarize" in content_lower:
            failure_reasons.append("summary_generation_failed")
        if "cannot summarize" in content_lower:
            failure_reasons.append("summary_not_possible")
        if len(summary_content) < 200:
            failure_reasons.append(f"summary_too_short ({len(summary_content)} chars)")

        if failure_reasons:
            logger.warning(
                "summarization.failed",
                {
                    "failure_reasons": failure_reasons,
                    "summary_preview": summary_content[:100],
                },
                user_id="system",
            )
            return None

        self._last_summary_msg_count = current_msg_count

        summary_msg = Message.system(f"## Conversation Summary\n\n{summary_content}")

        new_messages = list(system_messages) + [summary_msg] + list(messages[split_idx:])

        logger.info(
            "summarization.completed",
            {
                "old_msg_count": current_msg_count,
                "new_msg_count": len(new_messages),
                "summary_length": len(summary_content),
                "tokens_before": total_tokens,
            },
            user_id="system",
        )

        if self._on_summarize is not None:
            try:
                result = self._on_summarize(summary_content)
                if hasattr(result, "__await__"):
                    await result
            except Exception as e:
                logger.warning(
                    "summarization.callback_failed",
                    {"error": str(e)},
                    user_id="system",
                )

        return {"messages": new_messages}

    def before_model(self, state: AgentState) -> dict[str, Any] | None:
        total_tokens = self._total_tokens(state.messages)
        if total_tokens <= self.trigger_tokens:
            return None

        logger.info(
            "summarization.sync_trigger_needed",
            {"total_tokens": total_tokens, "trigger_tokens": self.trigger_tokens},
            user_id="system",
        )
        return None


__all__ = ["SummarizationMiddleware"]
