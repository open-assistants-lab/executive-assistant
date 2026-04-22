"""Adapter to inject LongMemEval sessions into our ConversationStore.

This allows our agent's memory system to be tested on the LongMemEval benchmark.
"""

import json
import sqlite3
from datetime import datetime
from typing import Any

from src.storage.messages import ConversationStore


def parse_longmemeval_date(date_str: str) -> datetime:
    """Parse LongMemEval date format like '2023/05/30 (Tue) 21:40'.

    Converts to ISO format for storage.
    """
    patterns = [
        "%Y/%m/%d (%a) %H:%M",
        "%Y/%m/%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
    ]

    for pattern in patterns:
        try:
            return datetime.strptime(date_str, pattern)
        except ValueError:
            continue

    raise ValueError(f"Cannot parse date: {date_str}")


def normalize_date_for_storage(date_str: str) -> str:
    """Normalize LongMemEval date to ISO format for internal storage."""
    dt = parse_longmemeval_date(date_str)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


class LongMemEvalAdapter:
    """Adapter that converts LongMemEval sessions into our ConversationStore.

    This allows running the LongMemEval benchmark against our actual agent
    memory system, testing how well our retrieval + agent answers questions.
    """

    def __init__(self, user_id: str = "benchmark"):
        self.user_id = user_id
        self.store = ConversationStore(user_id)
        self._original_store_path = self.store.messages_db_path

    def reset(self) -> None:
        """Clear all messages for this user."""
        conn = sqlite3.connect(self.store.messages_db_path)
        conn.execute("DELETE FROM messages")
        conn.commit()
        conn.close()

    def inject_sessions(
        self,
        sessions: list[list[dict[str, str]]],
        session_dates: list[str],
    ) -> None:
        """Inject LongMemEval sessions into the conversation store.

        Args:
            sessions: List of sessions, each session is a list of turns.
                     Each turn is {"role": "user"|"assistant", "content": "..."}
            session_dates: List of timestamp strings for each session.
        """
        self.reset()

        for session_idx, (session, session_date) in enumerate(zip(sessions, session_dates)):
            normalized_date = normalize_date_for_storage(session_date)
            for turn in session:
                role = turn["role"]
                content = turn["content"]
                self._add_message_with_timestamp(role, content, normalized_date)

    def _add_message_with_timestamp(
        self,
        role: str,
        content: str,
        timestamp: str,
        metadata: dict | None = None,
    ) -> int:
        """Add a message with a specific timestamp.

        This bypasses the auto-generated timestamp to preserve temporal ordering
        from LongMemEval sessions.
        """
        conn = sqlite3.connect(self.store.messages_db_path)
        cursor = conn.execute(
            "INSERT INTO messages (ts, role, content, metadata) VALUES (?, ?, ?, ?)",
            [timestamp, role, content, json.dumps(metadata) if metadata else None],
        )
        msg_id = cursor.lastrowid
        conn.commit()
        conn.close()

        from src.sdk.tools_core.apps import get_embedding

        embedding = get_embedding(content)
        self.store.collection.add(
            ids=[str(msg_id)],
            embeddings=[embedding],
            documents=[content],
            metadatas=[{"role": role, "ts": timestamp}],
        )

        return msg_id

    def get_conversation_for_agent(
        self,
        limit_sessions: int | None = None,
    ) -> list[dict[str, Any]]:
        """Get conversation formatted for the agent.

        This returns the messages in the format expected by our agent:
        [{"role": "user"|"assistant", "content": "..."}]

        Args:
            limit_sessions: If provided, only return this many sessions.

        Returns:
            List of message dicts
        """
        if limit_sessions:
            messages = self.store.get_messages(limit=limit_sessions * 10)
        else:
            messages = self.store.get_recent_messages(count=10000)

        return [{"role": msg.role, "content": msg.content} for msg in messages]

    def get_full_context(self, max_tokens: int = 128000) -> str:
        """Get full conversation context as a formatted string.

        This creates a prompt-friendly representation of all sessions.

        Args:
            max_tokens: Maximum tokens to return (approximate)

        Returns:
            Formatted string of all conversation context
        """
        messages = self.store.get_recent_messages(count=100000)

        lines = []
        current_session_date = None

        for msg in messages:
            msg_date = datetime.fromisoformat(msg.ts.replace("Z", "+00:00"))
            date_str = msg_date.strftime("%Y-%m-%d")

            if date_str != current_session_date:
                current_session_date = date_str
                lines.append(f"\n=== {date_str} ===\n")

            role_label = "User" if msg.role == "user" else "Assistant"
            lines.append(f"{role_label}: {msg.content}")

        context = "\n".join(lines)

        return context[: max_tokens * 4]

    def verify_injection(self) -> dict[str, Any]:
        """Verify that sessions were properly injected."""
        messages = self.store.get_recent_messages(count=100000)

        return {
            "total_messages": len(messages),
            "user_messages": sum(1 for m in messages if m.role == "user"),
            "assistant_messages": sum(1 for m in messages if m.role == "assistant"),
            "date_range": (f"{messages[0].ts} to {messages[-1].ts}" if messages else "empty"),
        }


def format_sessions_as_context(
    sessions: list[list[dict[str, str]]],
    session_dates: list[str],
    format_type: str = "chatml",
    max_context_chars: int = 100000,
) -> str:
    """Format sessions as a string context (alternative to using ConversationStore).

    This can be used when you want to provide context directly to the agent
    without going through our memory system.

    Args:
        sessions: LongMemEval sessions
        session_dates: Dates for each session
        format_type: 'chatml' for ChatML format, 'natural' for natural conversation
        max_context_chars: Maximum characters to include (truncates from oldest sessions)

    Returns:
        Formatted string representation
    """
    if format_type == "chatml":
        lines = []
        for session_idx, (session, session_date) in enumerate(zip(sessions, session_dates)):
            lines.append(f"<|session|>{session_date}<|session|>")
            for turn in session:
                role = "user" if turn["role"] == "user" else "assistant"
                lines.append(f"<|{role}|>\n{turn['content']}<|end|>")
        context = "\n".join(lines)
    elif format_type == "natural":
        lines = []
        for session_idx, (session, session_date) in enumerate(zip(sessions, session_dates)):
            lines.append(f"\n--- Conversation on {session_date} ---\n")
            for turn in session:
                role = "User" if turn["role"] == "user" else "Assistant"
                lines.append(f"{role}: {turn['content']}")
        context = "\n".join(lines)
    else:
        raise ValueError(f"Unknown format_type: {format_type}")

    # Truncate from the beginning (oldest sessions) if too long
    # Approximate: 1 token ≈ 4 characters
    if len(context) > max_context_chars:
        context = "..." + context[-(max_context_chars - 3) :]

    return context
