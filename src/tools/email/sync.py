"""Email sync - backfill and interval sync."""

import asyncio
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

from langchain_core.tools import tool
from sqlalchemy import create_engine, text

from src.app_logging import get_logger
from src.config import get_settings

logger = get_logger()
SETTINGS = get_settings()


def _get_db_path(user_id: str) -> str:
    """Get SQLite database path for user."""
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
    return engine


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


def _parse_email_date(date_str: str) -> int:
    """Parse email date string to Unix timestamp."""
    if not date_str:
        return int(datetime.now(UTC).timestamp())
    try:
        dt = parsedate_to_datetime(date_str)
        return int(dt.timestamp())
    except Exception:
        return int(datetime.now(UTC).timestamp())


def _email_to_dict(msg) -> dict[str, Any]:
    """Convert imap_tools message to dict."""
    attachments = []
    if msg.attachments:
        for att in msg.attachments:
            attachments.append(
                {
                    "filename": att.filename,
                    "size": len(att.payload) if att.payload else 0,
                    "content_type": att.content_type,
                }
            )

    date_ts = (
        _parse_email_date(msg.date_str) if msg.date_str else int(datetime.now(UTC).timestamp())
    )

    return {
        "message_id": str(msg.uid),
        "from_addr": msg.from_,
        "from_name": msg.from_values.name if msg.from_values else None,
        "to_addrs": [str(a) for a in msg.to],
        "cc_addrs": [str(a) for a in msg.cc],
        "subject": msg.subject or "",
        "body_text": msg.text or "",
        "timestamp": date_ts,
        "in_reply_to": msg.headers.get("In-Reply-To", [None])[0] if msg.headers else None,
        "thread_references": msg.headers.get("References", [None])[0] if msg.headers else None,
        "is_forwarded": bool(
            msg.headers.get("X-FWD", [None])[0] or msg.headers.get("Forwarded", [None])[0]
        )
        if msg.headers
        else False,
        "read": not msg.flags.Seen if hasattr(msg.flags, "Seen") else True,
        "flagged": msg.flags.Flagged if hasattr(msg.flags, "Flagged") else False,
        "has_attachments": bool(attachments),
        "attachments": attachments,
    }


def _get_imap_connection(account_id: str, user_id: str):
    """Get IMAP connection for account."""
    accounts = _load_accounts(user_id)
    account = accounts.get(account_id)
    if not account:
        raise ValueError(f"Account {account_id} not found")

    email = account.get("email")
    password = account.get("password")
    imap_host = account.get("imap_host")
    imap_port = account.get("imap_port", 993)

    if not email or not password or not imap_host:
        raise ValueError(f"Account {account_id} is missing credentials")

    from imap_tools import MailBox

    return MailBox(imap_host, imap_port).login(email, password)


def _sync_folder(
    account_id: str,
    folder: str,
    mode: str = "new",
    limit: int = 100,
    user_id: str = "",
) -> int:
    """Sync emails from a folder.

    Modes:
        - "new": Fetch emails newer than last_timestamp (quick sync)
        - "full": Fetch all emails (backfill, newest -> earliest)

    Args:
        account_id: Account ID
        folder: Folder name
        mode: "new" or "full"
        limit: Max emails to fetch
        user_id: User ID

    Returns:
        Number of emails synced
    """
    engine = _get_engine(user_id)
    accounts = _load_accounts(user_id)
    account = accounts.get(account_id)
    if not account:
        raise ValueError(f"Account {account_id} not found")

    with _get_imap_connection(account_id, user_id) as mailbox:
        mailbox.folder.set(folder)

        if mode == "full":
            # Full backfill - fetch all in batches (newest first)
            synced = 0

            existing_ids = set()
            with engine.connect() as conn:
                result = conn.execute(
                    text(
                        "SELECT message_id FROM emails WHERE account_id = :account_id AND folder = :folder"
                    ),
                    {"account_id": account_id, "folder": folder},
                )
                for row in result:
                    existing_ids.add(row[0])

            batch_count = 0
            max_batches = 50  # Safety limit

            while batch_count < max_batches:
                messages = list(mailbox.fetch(limit=limit, reverse=True))

                if not messages:
                    break

                for msg in messages:
                    msg_uid = str(msg.uid)
                    if msg_uid in existing_ids:
                        continue

                    email_data = _email_to_dict(msg)
                    email_data["account_id"] = account_id
                    email_data["folder"] = folder
                    email_data["created_at"] = int(datetime.now(UTC).timestamp())

                    with engine.connect() as conn:
                        conn.execute(
                            text("""
                                INSERT OR REPLACE INTO emails
                                (account_id, folder, message_id, from_addr, from_name,
                                 to_addrs, cc_addrs, subject, body_text, timestamp,
                                 in_reply_to, thread_references, is_forwarded,
                                 read, flagged, has_attachments, attachments, tags, created_at)
                                VALUES
                                (:account_id, :folder, :message_id, :from_addr, :from_name,
                                 :to_addrs, :cc_addrs, :subject, :body_text, :timestamp,
                                 :in_reply_to, :thread_references, :is_forwarded,
                                 :read, :flagged, :has_attachments, :attachments, :tags, :created_at)
                            """),
                            {
                                **email_data,
                                "to_addrs": ",".join(email_data["to_addrs"]),
                                "cc_addrs": ",".join(email_data["cc_addrs"]),
                                "attachments": str(email_data["attachments"]),
                                "read": 1 if email_data["read"] else 0,
                                "flagged": 1 if email_data["flagged"] else 0,
                                "has_attachments": 1 if email_data["has_attachments"] else 0,
                                "is_forwarded": 1 if email_data.get("is_forwarded") else 0,
                                "tags": "",
                            },
                        )
                        conn.commit()

                    existing_ids.add(msg_uid)
                    synced += 1

                batch_count += 1

                # If we got fewer than limit, we're done
                if len(messages) < limit:
                    break

            if synced > 0:
                account["last_sync"] = int(datetime.now(UTC).timestamp())
                account["last_timestamp"] = int(datetime.now(UTC).timestamp())
                _save_account(user_id, account_id, account)

            logger.info(
                "email.backfill_complete",
                {"account_id": account_id, "folder": folder, "count": synced},
            )
            return synced

        else:
            # Quick sync - fetch recent emails
            last_timestamp = account.get("last_timestamp", 0)
            synced = 0

            existing_ids = set()
            with engine.connect() as conn:
                result = conn.execute(
                    text(
                        "SELECT message_id FROM emails WHERE account_id = :account_id AND folder = :folder"
                    ),
                    {"account_id": account_id, "folder": folder},
                )
                for row in result:
                    existing_ids.add(row[0])

            messages = list(mailbox.fetch(limit=limit, reverse=True))

            newest_timestamp = last_timestamp

            for msg in messages:
                msg_uid = str(msg.uid)
                if msg_uid in existing_ids:
                    continue

                email_data = _email_to_dict(msg)
                email_data["account_id"] = account_id
                email_data["folder"] = folder
                email_data["created_at"] = int(datetime.now(UTC).timestamp())

                with engine.connect() as conn:
                    conn.execute(
                        text("""
                            INSERT OR REPLACE INTO emails
                            (account_id, folder, message_id, from_addr, from_name,
                             to_addrs, cc_addrs, subject, body_text, timestamp,
                             in_reply_to, thread_references, is_forwarded,
                             read, flagged, has_attachments, attachments, tags, created_at)
                            VALUES
                            (:account_id, :folder, :message_id, :from_addr, :from_name,
                             :to_addrs, :cc_addrs, :subject, :body_text, :timestamp,
                             :in_reply_to, :thread_references, :is_forwarded,
                             :read, :flagged, :has_attachments, :attachments, :tags, :created_at)
                        """),
                        {
                            **email_data,
                            "to_addrs": ",".join(email_data["to_addrs"]),
                            "cc_addrs": ",".join(email_data["cc_addrs"]),
                            "attachments": str(email_data["attachments"]),
                            "read": 1 if email_data["read"] else 0,
                            "flagged": 1 if email_data["flagged"] else 0,
                            "has_attachments": 1 if email_data["has_attachments"] else 0,
                            "is_forwarded": 1 if email_data.get("is_forwarded") else 0,
                            "tags": "",
                        },
                    )
                    conn.commit()

                if email_data["timestamp"] > newest_timestamp:
                    newest_timestamp = email_data["timestamp"]
                synced += 1

            if synced > 0:
                account["last_sync"] = int(datetime.now(UTC).timestamp())
                account["last_timestamp"] = newest_timestamp
                _save_account(user_id, account_id, account)

            logger.info(
                "email.quick_sync_complete",
                {"account_id": account_id, "folder": folder, "count": synced},
            )
            return synced


async def _sync_emails(
    user_id: str,
    account_id: str,
    folder: str = "INBOX",
    mode: str = "new",
    limit: int = 100,
) -> int:
    """Async wrapper for sync_folder."""
    return await asyncio.to_thread(_sync_folder, account_id, folder, mode, limit, user_id)


def start_background_sync(user_id: str, account_id: str) -> None:
    """Start background backfill sync (newest -> earliest)."""

    async def _backfill():
        try:
            limit = SETTINGS.email_sync.backfill_limit or 500
            count = await _sync_emails(user_id, account_id, "INBOX", "full", limit)
            logger.info(
                "email.backfill_complete",
                {"user_id": user_id, "account_id": account_id, "count": count},
            )
        except Exception as e:
            logger.error(
                "email.backfill_error",
                {"user_id": user_id, "account_id": account_id, "error": str(e)},
            )

    try:
        asyncio.create_task(_backfill())
    except Exception:
        pass


# Interval sync scheduler
_scheduler_task: asyncio.Task | None = None
_running = False


async def start_interval_sync() -> None:
    """Start background interval sync for all accounts."""
    global _scheduler_task, _running

    if _scheduler_task is not None:
        return

    if not SETTINGS.email_sync.enabled:
        logger.info("email_sync.disabled")
        return

    _running = True
    _scheduler_task = asyncio.create_task(_run_interval_sync())
    logger.info("email_sync.started", {"interval_minutes": SETTINGS.email_sync.interval_minutes})


async def stop_interval_sync() -> None:
    """Stop background interval sync."""
    global _scheduler_task, _running
    _running = False

    if _scheduler_task:
        _scheduler_task.cancel()
        try:
            await _scheduler_task
        except asyncio.CancelledError:
            pass
        _scheduler_task = None

    logger.info("email_sync.stopped")


async def _run_interval_sync() -> None:
    """Main interval sync loop."""
    interval_seconds = SETTINGS.email_sync.interval_minutes * 60

    while _running:
        try:
            await _sync_all_accounts()
        except Exception as e:
            logger.error("email_sync.error", {"error": str(e)})

        for _ in range(interval_seconds):
            if not _running:
                break
            await asyncio.sleep(1)


async def _sync_all_accounts() -> None:
    """Sync all connected accounts."""
    from src.storage.user import get_all_user_ids

    user_ids = get_all_user_ids()
    batch_size = SETTINGS.email_sync.batch_size

    for user_id in user_ids:
        accounts = _load_accounts(user_id)
        for account_id, account in accounts.items():
            try:
                await _sync_emails(
                    user_id=user_id,
                    account_id=account_id,
                    folder="INBOX",
                    mode="new",
                    limit=batch_size,
                )
            except Exception as e:
                logger.error(
                    "email_sync.account_error",
                    {"account": account["name"], "error": str(e)},
                )


@tool
def email_sync(
    account_name: str,
    mode: str = "new",
    folder: str = "INBOX",
    user_id: str = "",
) -> str:
    """Manually sync emails for an account.

    Args:
        account_name: Account name to sync
        mode: Sync mode - "new" (quick) or "full" (backfill all)
        folder: Folder to sync (default: INBOX)
        user_id: User ID (REQUIRED)

    Returns:
        Sync status
    """
    if not user_id:
        return "Error: user_id is required."

    from src.tools.email.account import _get_account_id_by_name

    account_id = _get_account_id_by_name(account_name, user_id)
    if not account_id:
        return f"Error: Account '{account_name}' not found."

    import asyncio

    async def _sync():
        limit = (
            SETTINGS.email_sync.backfill_limit if mode == "full" else SETTINGS.email_sync.batch_size
        )
        count = await _sync_emails(user_id, account_id, folder, mode, limit)
        return count

    try:
        count = asyncio.get_event_loop().run_until_complete(_sync())
        return f"Synced {count} emails ({mode} mode) for {account_name}."
    except Exception as e:
        return f"Error syncing: {e}"
