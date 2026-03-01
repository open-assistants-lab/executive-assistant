"""Email account management tools."""

import uuid
from datetime import UTC, datetime

from langchain_core.tools import tool

from src.app_logging import get_logger
from src.config import get_settings
from src.tools.email.db import (
    delete_account as db_delete_account,
)
from src.tools.email.db import (
    detect_provider,
    load_accounts,
    save_account,
)
from src.tools.email.sync import start_background_sync

logger = get_logger()
SETTINGS = get_settings()


@tool
def email_connect(
    email: str,
    password: str,
    account_name: str | None = None,
    user_id: str = "",
) -> str:
    """Connect an email account.

    Connects to email via IMAP, verifies credentials, and starts
    automatic backfill sync (newest to oldest).

    Args:
        email: Your email address (e.g., yourname@gmail.com)
        password: Your email password or app password (if 2FA enabled)
        account_name: Friendly name for this account (default: email username)
        user_id: User ID from the conversation (REQUIRED)

    Returns:
        Success or error message
    """
    if not user_id:
        return "Error: user_id is required."

    if not email:
        return "Error: email address is required."

    if not password:
        return "Error: password is required."

    logger.info("email_connect_called", {"user_id": user_id, "email": email})

    provider, imap_host, imap_port, smtp_host, smtp_port = detect_provider(email)

    if not imap_host:
        return f"Error: Could not detect email provider for {email}. Please use Gmail, Outlook, iCloud, or Yahoo."

    # Test IMAP connection
    try:
        from imap_tools import MailBox

        with MailBox(imap_host, imap_port).login(email, password) as mailbox:
            folder_list = [f.name for f in mailbox.folder.list()]
            logger.info("email.connect_success", {"account": email, "folders": folder_list})

    except Exception as e:
        logger.error("email.connect_failed", {"account": email, "error": str(e)})
        return f"Error: Failed to connect to email: {e}\n\nTip: If you have 2FA enabled, use an app password."

    # Check if account already exists
    accounts = load_accounts(user_id)
    for acc_id, acc in accounts.items():
        if acc.get("email") == email:
            return f"""Already connected!

Account: {acc["name"]}
Email: {acc["email"]}
Provider: {acc["provider"]}

Use email_list to fetch emails."""

    # Save new account
    account_id = str(uuid.uuid4())
    username = account_name or email.split("@")[0]
    account = {
        "id": account_id,
        "name": username,
        "email": email,
        "password": password,
        "imap_host": imap_host,
        "imap_port": imap_port,
        "smtp_host": smtp_host,
        "smtp_port": smtp_port,
        "provider": provider,
        "folders": ["INBOX"],
        "status": "connected",
        "created_at": int(datetime.now(UTC).timestamp()),
    }

    save_account(user_id, account_id, account)

    # Start background backfill sync
    start_background_sync(user_id, account_id)

    return f"""Connected successfully!

Account: {username}
Email: {email}
Provider: {provider}

📧 Syncing your emails in the background (newest first)..."""


@tool
def email_disconnect(account_name: str, user_id: str = "") -> str:
    """Disconnect and remove an email account.

    Args:
        account_name: Account name to disconnect
        user_id: User identifier (REQUIRED)

    Returns:
        Success or error message
    """
    from src.tools.email.db import get_account_id_by_name

    account_id = get_account_id_by_name(account_name, user_id)
    if not account_id:
        return f"Error: Account '{account_name}' not found. Use email_accounts to see available."

    db_delete_account(user_id, account_id)

    logger.info("email.disconnected", {"account": account_name, "user_id": user_id})
    return f"Account '{account_name}' disconnected and removed."


@tool
def email_accounts(user_id: str = "") -> str:
    """List connected email accounts.

    Args:
        user_id: User identifier (REQUIRED)

    Returns:
        List of connected accounts
    """
    accounts = load_accounts(user_id)

    if not accounts:
        return "No email accounts connected. Use email_connect to add one."

    output = "Connected email accounts:\n"
    for acc in accounts.values():
        output += f"- {acc['name']}: {acc['email']} ({acc['provider']})\n"
        output += f"  Status: {acc['status']}, Folders: {acc.get('folders', [])}\n"

    return output
