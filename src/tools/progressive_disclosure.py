"""Progressive disclosure tool - allows agent to query historical context."""

from datetime import date, timedelta
from typing import Any

from langchain_core.tools import tool

from src.storage.conversation import get_conversation_store, JournalEntry, Message


class ProgressiveDisclosureTool:
    """Tool for querying historical conversation context."""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.conversation = get_conversation_store(user_id)

    @tool("get_conversation_history")
    def get_conversation_history(
        self,
        days: int = 7,
        date_str: str | None = None,
    ) -> str:
        """Get conversation history for progressive disclosure.

        Use this tool when user asks about past conversations, what was discussed,
        or wants to recall previous interactions.

        Args:
            days: Number of days to look back (default: 7)
            date_str: Specific date in YYYY-MM-DD format (optional)

        Returns:
            Formatted conversation summary
        """
        if date_str:
            try:
                target_date = date.fromisoformat(date_str)
                messages = self.conversation.get_messages(
                    start_date=target_date,
                    end_date=target_date,
                )
                if not messages:
                    return f"No messages found for {date_str}"

                result = f"Conversation on {date_str}:\n"
                for msg in messages:
                    result += f"- {msg.role}: {msg.content[:200]}\n"
                return result

            except ValueError:
                return "Invalid date format. Use YYYY-MM-DD."

        # Get journal summaries first
        journal_entries = self.conversation.get_recent_journal(days)

        if journal_entries:
            result = f"Recent conversation summaries (last {days} days):\n\n"
            for entry in journal_entries:
                result += f"📅 {entry.date}: {entry.summary}\n\n"
        else:
            result = f"No journal summaries for last {days} days.\n\n"

        # Also get recent messages
        recent = self.conversation.get_recent_messages(10)
        if recent:
            result += "Recent messages:\n"
            for msg in recent:
                result += f"- {msg.role}: {msg.content[:100]}\n"

        return result

    @tool("search_conversation")
    def search_conversation(self, query: str) -> str:
        """Search through conversation history by keyword.

        Use this when user asks about specific topics or keywords from past conversations.

        Args:
            query: Keyword or phrase to search for

        Returns:
            Matching messages
        """
        messages = self.conversation.get_recent_messages(100)

        matches = []
        query_lower = query.lower()
        for msg in messages:
            if query_lower in msg.content.lower():
                matches.append(f"- {msg.role} ({msg.ts.date()}): {msg.content[:150]}")

        if not matches:
            return f"No messages found matching '{query}'"

        return f"Found {len(matches)} matches:\n" + "\n".join(matches[:20])


def create_progressive_disclosure_tools(user_id: str) -> list[Any]:
    """Create progressive disclosure tools for an agent."""
    tool_instance = ProgressiveDisclosureTool(user_id)
    return [tool_instance.get_conversation_history, tool_instance.search_conversation]
