"""Email search tool - semantic search."""

from datetime import datetime

from langchain_core.tools import tool

from src.app_logging import get_logger
from src.tools.email import imap
from src.tools.email.vector import get_email_vector_store

logger = get_logger()


def _get_account_id_by_name(account_name: str, user_id: str) -> str | None:
    """Get account ID by name or email.

    Searches in order:
    1. Account name (exact match)
    2. Email address (fallback)
    """
    accounts = imap._load_accounts(user_id)
    for acc_id, acc in accounts.items():
        if acc.get("name") == account_name:
            return acc_id
        if acc.get("email") == account_name:
            return acc_id
    return None


@tool
def email_search(
    account_name: str,
    query: str,
    limit: int = 10,
    user_id: str = "",
) -> str:
    """Search emails using semantic search.

    Uses AI-powered semantic search to find emails based on meaning,
    not just keyword matching. Great for finding emails about topics
    even when specific words aren't used.

    Args:
        account_name: Account name to search
        query: Search query in natural language (e.g., "meeting about budget", "email from John about project")
        limit: Number of results to return (default: 10)
        user_id: User ID (REQUIRED)

    Returns:
        Matching emails with relevance scores
    """
    if not user_id:
        return "Error: user_id is required. Please provide your user ID."

    account_id = _get_account_id_by_name(account_name, user_id)

    if not account_id:
        return f"Error: Account '{account_name}' not found. Use email_accounts to see available."

    try:
        vector_store = get_email_vector_store(user_id)
        results = vector_store.search(query, limit)

        if not results:
            return f"No emails found matching '{query}'. Try a different query or run email_sync first."

        # Get full email details from SQLite
        output = f"## Search results for '{query}'\n\n"

        for result in results:
            # Filter by account_id
            if result["metadata"].get("account_id") != account_id:
                continue

            email_id = result["id"]
            email = imap.email_get_from_db(email_id, account_id, "INBOX", user_id)

            if email:
                status = "📭" if email["read"] else "📬"
                from_display = email["from_name"] or email["from_addr"]
                subject = email["subject"] or "(No subject)"
                date_ts = email.get("timestamp", 0)
                if date_ts:
                    date = datetime.fromtimestamp(date_ts).strftime("%Y-%m-%d %H:%M")
                else:
                    date = ""
                score = result.get("score", 0)

                output += f"{status} **[{score:.2f}] {from_display}**\n"
                output += f"   {subject}\n"
                output += f"   {date}\n"
                output += f"   ID: {email_id}\n\n"

        return output or f"No emails found matching '{query}' in this account."

    except Exception as e:
        logger.error("email_search_error", {"account": account_name, "error": str(e)})
        return f"Error searching emails: {e}"
