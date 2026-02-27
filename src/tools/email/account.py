"""Email account management tools."""

import uuid
from datetime import UTC, datetime

from langchain_core.tools import tool
from sqlalchemy import create_engine, text

from src.app_logging import get_logger
from src.config import get_settings
from src.tools.email.sync import start_background_sync

logger = get_logger()

SETTINGS = get_settings()


def _get_db_path(user_id: str) -> str:
    """Get SQLite database path for user."""
    from pathlib import Path

    if not user_id or user_id == "default":
        raise ValueError(f"Invalid user_id: {user_id}")
    cwd = Path.cwd()
    base_dir = cwd / "data" / "users" / user_id / "email"
    base_dir.mkdir(parents=True, exist_ok=True)
    return str(base_dir / "emails.db")


def _get_engine(user_id: str):
    """Get SQLAlchemy engine."""
    db_path = _get_db_path(user_id)
    engine = create_engine(f"sqlite:///{db_path}")
    _init_db(engine)
    return engine


def _init_db(engine) -> None:
    """Initialize database schema."""
    with engine.connect() as conn:
        conn.execute(
            text("""
            CREATE TABLE IF NOT EXISTS accounts (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                password TEXT NOT NULL,
                imap_host TEXT NOT NULL,
                imap_port INTEGER DEFAULT 993,
                smtp_host TEXT NOT NULL,
                smtp_port INTEGER DEFAULT 587,
                provider TEXT NOT NULL,
                folders TEXT NOT NULL,
                last_sync INTEGER,
                last_timestamp INTEGER,
                status TEXT DEFAULT 'connected',
                created_at INTEGER NOT NULL
            )
        """)
        )

        conn.execute(
            text("""
            CREATE TABLE IF NOT EXISTS emails (
                account_id TEXT NOT NULL,
                folder TEXT NOT NULL,
                message_id TEXT NOT NULL,
                from_addr TEXT,
                from_name TEXT,
                to_addrs TEXT,
                cc_addrs TEXT,
                subject TEXT,
                body_text TEXT,
                timestamp INTEGER NOT NULL,
                in_reply_to TEXT,
                thread_references TEXT,
                is_forwarded INTEGER DEFAULT 0,
                read INTEGER DEFAULT 0,
                flagged INTEGER DEFAULT 0,
                has_attachments INTEGER DEFAULT 0,
                attachments TEXT,
                tags TEXT,
                created_at INTEGER NOT NULL,
                PRIMARY KEY (account_id, folder, message_id)
            )
        """)
        )

        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_emails_timestamp ON emails(timestamp)"))

        conn.commit()


def _detect_provider(email: str) -> tuple[str, str, int, str, int]:
    """Detect email provider and return (provider, imap_host, imap_port, smtp_host, smtp_port)."""
    email_lower = email.lower()

    if "gmail.com" in email_lower or "googlemail.com" in email_lower:
        return ("gmail", "imap.gmail.com", 993, "smtp.gmail.com", 587)
    elif "outlook.com" in email_lower or "hotmail.com" in email_lower or "live.com" in email_lower:
        return ("outlook", "outlook.office365.com", 993, "smtp.office365.com", 587)
    elif "icloud.com" in email_lower or "me.com" in email_lower:
        return ("icloud", "imap.mail.me.com", 993, "smtp.mail.me.com", 587)
    elif "yahoo.com" in email_lower:
        return ("yahoo", "imap.mail.yahoo.com", 993, "smtp.mail.yahoo.com", 587)

    return ("other", "", 993, "", 587)


def _load_accounts(user_id: str) -> dict:
    """Load accounts from database."""
    engine = _get_engine(user_id)

    with engine.connect() as conn:
        result = conn.execute(text("SELECT * FROM accounts"))
        accounts = {}
        for row in result:
            row_dict = dict(row._mapping)
            accounts[row_dict["id"]] = {
                "id": row_dict["id"],
                "name": row_dict["name"],
                "email": row_dict.get("email", ""),
                "password": row_dict.get("password", ""),
                "imap_host": row_dict.get("imap_host", ""),
                "imap_port": row_dict.get("imap_port", 993),
                "smtp_host": row_dict.get("smtp_host", ""),
                "smtp_port": row_dict.get("smtp_port", 587),
                "provider": row_dict.get("provider", ""),
                "folders": row_dict.get("folders", "").split(",")
                if row_dict.get("folders")
                else [],
                "last_sync": row_dict.get("last_sync"),
                "last_timestamp": row_dict.get("last_timestamp"),
                "status": row_dict.get("status", "connected"),
                "created_at": row_dict.get("created_at"),
            }
        return accounts


def _get_account_id_by_name(account_name: str, user_id: str) -> str | None:
    """Get account ID by name or email."""
    accounts = _load_accounts(user_id)
    for acc_id, acc in accounts.items():
        if acc.get("name") == account_name:
            return acc_id
        if acc.get("email") == account_name:
            return acc_id
    return None


def _save_account(user_id: str, account_id: str, account: dict) -> None:
    """Save account to database."""
    engine = _get_engine(user_id)

    with engine.connect() as conn:
        conn.execute(
            text("""
                INSERT OR REPLACE INTO accounts
                (id, name, email, password, imap_host, imap_port, smtp_host, smtp_port, provider, folders, last_sync, last_timestamp, status, created_at)
                VALUES (:id, :name, :email, :password, :imap_host, :imap_port, :smtp_host, :smtp_port, :provider, :folders, :last_sync, :last_timestamp, :status, :created_at)
            """),
            {
                "id": account_id,
                "name": account.get("name", ""),
                "email": account.get("email", ""),
                "password": account.get("password", ""),
                "imap_host": account.get("imap_host", ""),
                "imap_port": account.get("imap_port", 993),
                "smtp_host": account.get("smtp_host", ""),
                "smtp_port": account.get("smtp_port", 587),
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
    engine = _get_engine(user_id)

    with engine.connect() as conn:
        conn.execute(text("DELETE FROM accounts WHERE id = :id"), {"id": account_id})
        conn.commit()


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

    provider, imap_host, imap_port, smtp_host, smtp_port = _detect_provider(email)

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
    accounts = _load_accounts(user_id)
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

    _save_account(user_id, account_id, account)

    # Start background backfill sync (newest -> earliest)
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
    accounts = _load_accounts(user_id)

    account_id = None
    for acc_id, acc in accounts.items():
        if acc["name"] == account_name:
            account_id = acc_id
            break

    if not account_id:
        return f"Error: Account '{account_name}' not found. Use email_accounts to see available."

    _delete_account(user_id, account_id)

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
    accounts = _load_accounts(user_id)

    if not accounts:
        return "No email accounts connected. Use email_connect to add one."

    output = "Connected email accounts:\n"
    for acc in accounts.values():
        output += f"- {acc['name']}: {acc['email']} ({acc['provider']})\n"
        output += f"  Status: {acc['status']}, Folders: {acc.get('folders', [])}\n"

    return output
