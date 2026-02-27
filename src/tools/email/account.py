"""Email account management tools."""

import uuid
from datetime import UTC, datetime

from langchain_core.tools import tool
from sqlalchemy import text

from src.app_logging import get_logger
from src.tools.email.imap import _get_account_engine, _load_accounts

logger = get_logger()


def _save_account(user_id: str, account_id: str, account: dict) -> None:
    """Save account to database."""
    engine = _get_account_engine(user_id)

    with engine.connect() as conn:
        conn.execute(
            text("""
                INSERT OR REPLACE INTO accounts
                (id, name, email, password, imap_host, imap_port, provider, folders, last_sync, last_timestamp, status, created_at)
                VALUES (:id, :name, :email, :password, :imap_host, :imap_port, :provider, :folders, :last_sync, :last_timestamp, :status, :created_at)
            """),
            {
                "id": account_id,
                "name": account.get("name", ""),
                "email": account.get("email", ""),
                "password": account.get("password", ""),
                "imap_host": account.get("imap_host", ""),
                "imap_port": account.get("imap_port", 993),
                "provider": account.get("provider", ""),
                "folders": ",".join(account.get("folders", [])),
                "last_sync": account.get("last_sync"),
                "last_timestamp": account.get("last_timestamp"),
                "status": account.get("status", "connected"),
                "created_at": account.get("created_at", int(datetime.now(UTC).timestamp())),
            },
        )
        conn.commit()


def _delete_account(user_id: str, account_id: str) -> None:
    """Delete account from database."""
    engine = _get_account_engine(user_id)

    with engine.connect() as conn:
        conn.execute(
            text("DELETE FROM accounts WHERE id = :id"),
            {"id": account_id},
        )
        conn.commit()


def _detect_provider(email: str) -> tuple[str, str, int]:
    """Detect email provider and return (provider, imap_host, imap_port)."""
    email_lower = email.lower()

    if "gmail.com" in email_lower or "googlemail.com" in email_lower:
        return ("gmail", "imap.gmail.com", 993)
    elif "outlook.com" in email_lower or "hotmail.com" in email_lower or "live.com" in email_lower:
        return ("outlook", "outlook.office365.com", 993)
    elif "icloud.com" in email_lower or "me.com" in email_lower:
        return ("icloud", "imap.mail.me.com", 993)
    elif "yahoo.com" in email_lower:
        return ("yahoo", "imap.mail.yahoo.com", 993)

    # Default - try generic
    return ("other", "", 993)


@tool
def email_connect(
    email: str,
    password: str,
    account_name: str | None = None,
    folders: list[str] | None = None,
    user_id: str = "",
) -> str:
    """Connect an email account.

    Connects to email using IMAP and verifies connection.
    Fetches folder list and prepares for sync.

    Args:
        email: Your email address (e.g., yourname@gmail.com)
        password: Your email password or app password (if 2FA enabled)
        account_name: Friendly name for this account (default: use email username)
        folders: Folders to sync (default: INBOX, SENT)
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

    # Detect provider
    provider, imap_host, imap_port = _detect_provider(email)

    if not imap_host:
        return f"Error: Could not detect email provider for {email}. Please use a supported provider (Gmail, Outlook, iCloud, Yahoo)."

    # Test IMAP connection
    try:
        from imap_tools import MailBox

        with MailBox(imap_host, imap_port).login(
            email, password, initial_folder=folders[0] if folders else "INBOX"
        ) as mailbox:
            folder_list = [f.name for f in mailbox.folder.list()]
            logger.info("email.connect_success", {"account": email, "folders": folder_list})

    except Exception as e:
        logger.error("email.connect_failed", {"account": email, "error": str(e)})
        return f"Error: Failed to connect to email: {e}\n\nTip: If you have 2FA enabled, use an app password instead of your regular password."

    # Check if account already exists for this email
    accounts = _load_accounts(user_id)
    for acc_id, acc in accounts.items():
        if acc.get("email") == email:
            return f"""Already connected!

Account: {acc["name"]}
Email: {acc["email"]}
Provider: {acc["provider"]}
Folders: {acc.get("folders", [])}

Use email_list to fetch emails."""

    # Save new account to database
    account_id = str(uuid.uuid4())
    username = email.split("@")[0] if "@" in email else email
    account = {
        "id": account_id,
        "name": account_name or username,
        "email": email,
        "password": password,
        "imap_host": imap_host,
        "imap_port": imap_port,
        "provider": provider,
        "folders": folders or ["INBOX", "SENT"],
        "status": "connected",
        "created_at": int(datetime.now(UTC).timestamp()),
    }

    _save_account(user_id, account_id, account)

    # Start background sync
    import asyncio
    from src.tools.email.imap import sync_emails

    async def _background_sync():
        try:
            await sync_emails(user_id, account_id, "INBOX", "new", 100)
            logger.info("email.auto_sync_complete", {"account": account["name"], "user_id": user_id})
        except Exception as e:
            logger.error("email.auto_sync_failed", {"account": account["name"], "error": str(e)})

    # Run sync in background (don't await)
    try:
        asyncio.create_task(_background_sync())
    except Exception:
        pass  # If can't create task, sync will happen on next manual call

    return f"""Connected successfully!

Account: {account["name"]}
Email: {email}
Provider: {provider}
Folders: {account["folders"]}

📧 Syncing your emails in the background... will be ready shortly!


@tool
def email_disconnect(account_name: str, user_id: str = "") -> str:
    """Disconnect and remove an email account.

    Removes the account and its local store from storage.

    Args:
        account_name: Account name to disconnect
        user_id: User identifier (default: default)

    Returns:
        Success or error message
    """
    accounts = _load_accounts(user_id)

    # Find account by name
    account_id = None
    for acc_id, acc in accounts.items():
        if acc["name"] == account_name:
            account_id = acc_id
            break

    if not account_id:
        return f"Error: Account '{account_name}' not found. Use email_accounts to see available."

    # Remove account from database
    _delete_account(user_id, account_id)

    logger.info("email.disconnected", {"account": account_name, "user_id": user_id})
    return f"Account '{account_name}' disconnected and removed."


@tool
def email_accounts(user_id: str = "") -> str:
    """List connected email accounts.

    Args:
        user_id: User identifier (default: default)

    Returns:
        List of connected accounts
    """
    accounts = _load_accounts(user_id)

    if not accounts:
        return "No email accounts connected. Use email_connect to add one."

    output = "Connected email accounts:\n"
    for acc in accounts.values():
        output += f"- {acc['name']}: {acc['email']} ({acc['provider']})\n"
        output += f"  Status: {acc['status']}, Folders: {acc.get('folders', [])}\n"

    return output
