"""Email list, get, and sync tools."""

from datetime import datetime

from langchain_core.tools import tool

from src.app_logging import get_logger
from src.tools.email import imap

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
def email_sync(
    account_name: str,
    folder: str = "INBOX",
    mode: str = "new",
    limit: int = 100,
    user_id: str = "",
) -> str:
    """Sync emails from email account to local store.

    Two sync modes:
    - "new" (default): Sync emails newer than last sync (quick sync)
    - "older": Sync emails older than what's in local DB (backfill)

    Use "new" for regular sync (only fetches new emails).
    Use "older" to fetch older emails that aren't in local storage yet.

    Args:
        account_name: Account name to sync
        folder: Folder to sync (default: INBOX)
        mode: "new" or "older" (default: "new")
        limit: Max emails to fetch per sync (default: 100)
        user_id: User ID (REQUIRED)

    Returns:
        Sync status with count
    """
    if not user_id:
        return "Error: user_id is required. Please provide your user ID."

    account_id = _get_account_id_by_name(account_name, user_id)

    if not account_id:
        return f"Error: Account '{account_name}' not found. Use email_accounts to see available."

    try:
        count = imap.sync_folder(account_id, folder, mode, limit, user_id)
        mode_desc = "new" if mode == "new" else "older"
        return f"Synced {count} {mode_desc} emails from {account_name}/{folder}."
    except Exception as e:
        logger.error("email_sync_error", {"account": account_name, "mode": mode, "error": str(e)})
        return f"Error syncing: {e}"


@tool
def email_list(
    account_name: str,
    folder: str = "INBOX",
    limit: int = 20,
    user_id: str = "",
) -> str:
    """List emails from an account.

    Shows email list from local store (use email_sync first to fetch and store).

    Args:
        account_name: Account name
        folder: Folder to list (default: INBOX)
        limit: Number of emails to show (default: 20)
        user_id: User ID (REQUIRED)

    Returns:
        List of emails
    """
    if not user_id:
        return "Error: user_id is required. Please provide your user ID."
    account_id = _get_account_id_by_name(account_name, user_id)

    if not account_id:
        return f"Error: Account '{account_name}' not found. Use email_accounts to see available."

    try:
        emails = imap.email_list_from_db(account_id, folder, limit, user_id)

        if not emails:
            return f"No emails in {account_name}/{folder}. Run email_sync first."

        output = f"## Emails in {account_name}/{folder}\n\n"
        for i, email in enumerate(emails, 1):
            status = "📭" if email["read"] else "📬"
            flagged = "🚩" if email["flagged"] else ""
            attach = "📎" if email["has_attachments"] else ""
            reply = "↩️" if email.get("in_reply_to") else ""
            forward = "📤" if email.get("is_forwarded") else ""
            tags = f"🏷️{email.get('tags')}" if email.get("tags") else ""

            from_display = email["from_name"] or email["from_addr"]
            subject = email["subject"] or "(No subject)"
            date_ts = email.get("timestamp", 0)
            if date_ts:
                date = datetime.fromtimestamp(date_ts).strftime("%Y-%m-%d %H:%M")
            else:
                date = ""

            output += f"{status}{flagged}{attach}{reply}{forward}{tags} **{from_display}**\n"
            output += f"   {subject}\n"
            output += f"   {date}\n\n"

        return output

    except Exception as e:
        logger.error("email_list_error", {"account": account_name, "error": str(e)})
        return f"Error listing emails: {e}"


@tool
def email_get(
    account_name: str,
    email_id: str,
    user_id: str = "",
) -> str:
    """Get full email content.

    Shows full email from local store (use email_sync first to fetch and store).

    Args:
        account_name: Account name
        email_id: Email ID (from email_list)
        user_id: User ID (REQUIRED)

    Returns:
        Email content
    """
    if not user_id:
        return "Error: user_id is required. Please provide your user ID."

    account_id = _get_account_id_by_name(account_name, user_id)

    if not account_id:
        return f"Error: Account '{account_name}' not found."

    try:
        email = imap.email_get_from_db(email_id, account_id, "INBOX", user_id)

        if not email:
            return "Error: Email not found. Run email_sync first."

        from_display = email["from_name"] or email["from_addr"]

        date_ts = email.get("date", 0)
        if date_ts:
            date = datetime.fromtimestamp(date_ts).strftime("%Y-%m-%d %H:%M:%S")
        else:
            date = ""

        output = "## Email\n\n"
        output += f"**From:** {from_display} <{email['from_addr']}>\n"
        output += f"**To:** {', '.join(email['to_addrs'])}\n"
        output += f"**Date:** {date}\n"
        output += f"**Subject:** {email['subject']}\n\n"

        if email["body_text"]:
            output += "---\n\n"
            output += email["body_text"]

        return output

    except Exception as e:
        logger.error("email_get_error", {"email_id": email_id, "error": str(e)})
        return f"Error getting email: {e}"


@tool
def email_stats(
    account_name: str = "",
    user_id: str = "",
) -> str:
    """Get email statistics for an account, or all accounts if no account specified.

    Returns total email count, date range (earliest/latest timestamps),
    and read/unread/flagged counts.

    Args:
        account_name: Account name to get stats for (optional - if empty, returns all accounts)
        user_id: User ID (REQUIRED)

    Returns:
        Formatted stats or error message
    """
    if not user_id:
        return "Error: user_id is required."

    try:
        stats = imap.email_stats(user_id, account_name)

        if "error" in stats:
            return f"Error: {stats['error']}"

        if "accounts" in stats:
            output = "## Email Stats (All Accounts)\n\n"
            output += f"**Total across all accounts:** {stats['total']}\n\n"
            for name, data in stats["accounts"].items():
                output += f"### {name}\n"
                output += f"- Total: {data['total']}, Read: {data['read']}, Unread: {data['unread']}, Flagged: {data['flagged']}\n"
            return output

        earliest = (
            datetime.fromtimestamp(stats["earliest"]).strftime("%Y-%m-%d")
            if stats["earliest"]
            else "N/A"
        )
        latest = (
            datetime.fromtimestamp(stats["latest"]).strftime("%Y-%m-%d")
            if stats["latest"]
            else "N/A"
        )

        output = f"## Email Stats: {stats['account']}\n\n"
        output += f"- **Total emails:** {stats['total']}\n"
        output += f"- **Date range:** {earliest} to {latest}\n"
        output += f"- **Read:** {stats['read']}\n"
        output += f"- **Unread:** {stats['unread']}\n"
        output += f"- **Flagged:** {stats['flagged']}\n"

        return output

    except Exception as e:
        logger.error("email_stats_error", {"account": account_name, "error": str(e)})
        return f"Error getting stats: {e}"


@tool
def run_email_sql(
    query: str,
    user_id: str = "",
) -> str:
    """Run a SELECT query on the email database.

    WARNING: Only SELECT queries are allowed. No INSERT, UPDATE, DELETE, or DROP.

    Available columns in 'emails' table:
        - account_id: Account identifier
        - folder: Folder name (e.g., 'INBOX', 'SENT')
        - message_id: IMAP message UID
        - from_addr: Sender email address
        - from_name: Sender display name
        - to_addrs: Comma-separated recipient emails
        - cc_addrs: Comma-separated CC emails
        - subject: Email subject line
        - body_text: Email body text content
        - timestamp: Unix timestamp of email date (INTEGER)
        - in_reply_to: In-Reply-To header
        - thread_references: References header
        - is_forwarded: Boolean (0/1)
        - read: Boolean (0/1)
        - flagged: Boolean (0/1)
        - has_attachments: Boolean (0/1)
        - attachments: JSON string of attachments
        - tags: Comma-separated tags
        - created_at: Unix timestamp of when synced (INTEGER)

    Example queries:
        - "SELECT COUNT(*) FROM emails"
        - "SELECT COUNT(*) FROM emails WHERE timestamp > strftime('%s', 'now') - 86400*30"
        - "SELECT * FROM emails WHERE from_addr LIKE '%@google.com%' LIMIT 10"
        - "SELECT from_addr, COUNT(*) as cnt FROM emails GROUP BY from_addr ORDER BY cnt DESC LIMIT 5"

    Args:
        query: SQL SELECT query (no semicolons, no comments)
        user_id: User ID (REQUIRED)

    Returns:
        Query results or error message
    """
    if not user_id:
        return "Error: user_id is required."

    if not query:
        return "Error: query is required."

    try:
        result = imap.run_email_sql(user_id, query)

        if "error" in result:
            return f"Error: {result['error']}"

        output = f"## Query Results ({result['count']} rows)\n\n"
        output += f"Columns: {', '.join(result['columns'])}\n\n"

        # Format rows
        for i, row in enumerate(result["rows"][:20]):  # Limit to 20 rows
            output += f"{i + 1}. {row}\n"

        if result["count"] > 20:
            output += f"\n... and {result['count'] - 20} more rows"

        return output

    except Exception as e:
        logger.error("run_email_sql_error", {"error": str(e)})
        return f"Error running query: {e}"


@tool
def email_delete(
    account_name: str = "",
    email_id: str = "",
    target: str = "local",
    user_id: str = "",
) -> str:
    """Delete an email from local database, server, or both.

    NOTE: This tool requires human approval before execution.

    Use target='local' to delete only from local database.
    Use target='server' to delete only from email server (IMAP).
    Use target='both' to delete from both local and server.

    Args:
        account_name: Account name (auto-detected if not provided)
        email_id: Email ID (from email_list)
        target: "local" (default), "server", or "both"
        user_id: User ID (REQUIRED)

    Returns:
        Confirmation or error message
    """
    if not user_id:
        return "Error: user_id is required."

    if not account_name:
        # Auto-detect from user's accounts
        accounts = imap._load_accounts(user_id)
        if not accounts:
            return "Error: No email accounts connected."
        account_name = list(accounts.values())[0].get("name", "")
        if not account_name:
            return "Error: Could not determine account name."

    if target not in ("local", "server", "both"):
        return "Error: target must be 'local', 'server', or 'both'."

    try:
        result = imap.email_delete(user_id, account_name, email_id, target)

        if "error" in result:
            return f"Error: {result['error']}"

        output = "## Email Deleted\n\n"
        output += f"**Email ID:** {email_id}\n"
        output += f"**Account:** {account_name}\n"
        output += f"**Target:** {target}\n\n"
        output += "**Results:**\n"
        output += f"- Local: {result['results']['local']}\n"
        output += f"- Server: {result['results']['server']}\n"

        return output

    except Exception as e:
        logger.error("email_delete_error", {"account": account_name, "error": str(e)})
        return f"Error deleting email: {e}"
