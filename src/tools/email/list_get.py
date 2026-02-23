"""Email list, get, and sync tools."""

from pathlib import Path
from typing import Any

import yaml
from langchain_core.tools import tool

from src.app_logging import get_logger
from src.tools.email import imap

logger = get_logger()


def _load_accounts(user_id: str) -> dict[str, Any]:
    """Load accounts from YAML."""
    path = Path(f"data/users/{user_id}/email/accounts.yaml")
    if not path.exists():
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


def _get_account_id_by_name(account_name: str, user_id: str) -> str | None:
    """Get account ID by name."""
    accounts = _load_accounts(user_id)
    for acc_id, acc in accounts.items():
        if acc["name"] == account_name:
            return acc_id
    return None


@tool
def email_sync(
    account_name: str,
    folder: str = "INBOX",
    limit: int = 100,
    user_id: str = "default",
) -> str:
    """Sync emails from email account to local store.

    Downloads emails from the email provider and stores locally for permanent access.
    Run this to update local email store.

    Args:
        account_name: Account name to sync
        folder: Folder to sync (default: INBOX)
        limit: Number of recent emails to sync (default: 100)
        user_id: User identifier (default: default)

    Returns:
        Sync status with count
    """
    account_id = _get_account_id_by_name(account_name, user_id)

    if not account_id:
        return f"Error: Account '{account_name}' not found. Use email_accounts to see available."

    try:
        count = imap.sync_folder(account_id, folder, limit, user_id)
        return f"Synced {count} emails from {account_name}/{folder}."
    except Exception as e:
        logger.error("email_sync_error", {"account": account_name, "error": str(e)})
        return f"Error syncing: {e}"


@tool
def email_list(
    account_name: str,
    folder: str = "INBOX",
    limit: int = 20,
    user_id: str = "default",
) -> str:
    """List emails from an account.

    Shows email list from local store (use email_sync first to fetch and store).

    Args:
        account_name: Account name
        folder: Folder to list (default: INBOX)
        limit: Number of emails to show (default: 20)
        user_id: User identifier (default: default)

    Returns:
        List of emails
    """
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
            date = email["date"] or ""

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
    user_id: str = "default",
) -> str:
    """Get full email content.

    Shows full email from local store (use email_sync first to fetch and store).

    Args:
        account_name: Account name
        email_id: Email ID (from email_list)
        user_id: User identifier (default: default)

    Returns:
        Email content
    """
    account_id = _get_account_id_by_name(account_name, user_id)

    if not account_id:
        return f"Error: Account '{account_name}' not found."

    try:
        email = imap.email_get_from_db(email_id, user_id)

        if not email:
            return "Error: Email not found. Run email_sync first."

        from_display = email["from_name"] or email["from_addr"]

        output = "## Email\n\n"
        output += f"**From:** {from_display} <{email['from_addr']}>\n"
        output += f"**To:** {', '.join(email['to_addrs'])}\n"
        output += f"**Date:** {email['date']}\n"
        output += f"**Subject:** {email['subject']}\n\n"

        if email["body_text"]:
            output += "---\n\n"
            output += email["body_text"]

        return output

    except Exception as e:
        logger.error("email_get_error", {"email_id": email_id, "error": str(e)})
        return f"Error getting email: {e}"
