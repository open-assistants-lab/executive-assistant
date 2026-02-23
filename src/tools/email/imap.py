"""Email IMAP operations and caching."""

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import create_engine, text

from src.app_logging import get_logger
from src.tools.email.vector import get_email_vector_store
from src.tools.vault.store import get_vault

logger = get_logger()


def _get_db_path(user_id: str) -> Path:
    """Get SQLite database path for user."""
    base_dir = Path(f"data/users/{user_id}/email")
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir / "emails.db"


def _get_engine(user_id: str):
    """Get SQLAlchemy engine."""
    db_path = _get_db_path(user_id)
    engine = create_engine(f"sqlite:///{db_path}")
    _init_db(engine)
    return engine


def _init_db(engine) -> None:
    """Initialize database schema."""
    with engine.connect() as conn:
        # Emails table
        conn.execute(
            text("""
            CREATE TABLE IF NOT EXISTS emails (
                id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                folder TEXT NOT NULL,
                message_id TEXT,
                from_addr TEXT,
                from_name TEXT,
                to_addrs TEXT,
                cc_addrs TEXT,
                subject TEXT,
                body_text TEXT,
                date TEXT,
                in_reply_to TEXT,
                thread_references TEXT,
                is_forwarded INTEGER DEFAULT 0,
                read INTEGER DEFAULT 0,
                flagged INTEGER DEFAULT 0,
                has_attachments INTEGER DEFAULT 0,
                attachments TEXT,
                tags TEXT,
                created_at TEXT
            )
        """)
        )

        # FTS5 virtual table
        conn.execute(
            text("""
            CREATE VIRTUAL TABLE IF NOT EXISTS emails_fts USING fts5(
                subject, body_text, content='emails', content_rowid='rowid'
            )
        """)
        )

        # Accounts table
        conn.execute(
            text("""
            CREATE TABLE IF NOT EXISTS accounts (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                credential_name TEXT NOT NULL,
                email TEXT NOT NULL,
                provider TEXT NOT NULL,
                folders TEXT NOT NULL,
                last_sync TEXT,
                status TEXT DEFAULT 'connected',
                created_at TEXT
            )
        """)
        )

        conn.commit()


def _load_accounts(user_id: str) -> dict[str, Any]:
    """Load accounts from YAML."""
    path = Path(f"data/users/{user_id}/email/accounts.yaml")
    if not path.exists():
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


def _get_imap_connection(account_id: str, user_id: str):
    """Get IMAP connection for account."""
    accounts = _load_accounts(user_id)
    account = accounts.get(account_id)
    if not account:
        raise ValueError(f"Account {account_id} not found")

    vault = get_vault(user_id)
    if not vault.is_unlocked():
        raise ValueError("Vault is locked")

    cred = vault.get_credential(account["credential_name"])
    if not cred:
        raise ValueError(f"Credential {account['credential_name']} not found")

    from imap_tools import MailBox

    return MailBox(cred.imap_host, cred.imap_port).login(cred.username, cred.password)


def _email_to_dict(msg) -> dict[str, Any]:
    """Convert imap_tools message to dict."""
    # Parse attachments
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

    return {
        "id": str(uuid.uuid4()),
        "message_id": msg.uid,
        "from_addr": msg.from_,
        "from_name": msg.from_values.name if msg.from_values else None,
        "to_addrs": [str(a) for a in msg.to],
        "cc_addrs": [str(a) for a in msg.cc],
        "subject": msg.subject or "",
        "body_text": msg.text or "",
        "date": msg.date_str or "",
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


def sync_folder(account_id: str, folder: str, limit: int = 100, user_id: str = "default") -> int:
    """Sync emails from a folder to local store."""
    try:
        with _get_imap_connection(account_id, user_id) as mailbox:
            # Select folder
            mailbox.folder.set(folder)

            # Fetch recent emails
            messages = list(mailbox.fetch(limit=limit, reverse=True))

            engine = _get_engine(user_id)
            vector_store = get_email_vector_store(user_id)
            synced = 0

            for msg in messages:
                email_data = _email_to_dict(msg)
                email_data["account_id"] = account_id
                email_data["folder"] = folder
                email_data["created_at"] = datetime.utcnow().isoformat()

                with engine.connect() as conn:
                    # Insert or replace
                    conn.execute(
                        text("""
                        INSERT OR REPLACE INTO emails
                        (id, account_id, folder, message_id, from_addr, from_name,
                         to_addrs, cc_addrs, subject, body_text, date,
                         in_reply_to, thread_references, is_forwarded,
                         read, flagged, has_attachments, attachments, tags, created_at)
                        VALUES
                        (:id, :account_id, :folder, :message_id, :from_addr, :from_name,
                         :to_addrs, :cc_addrs, :subject, :body_text, :date,
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

                # Also store in vector store for semantic search
                vector_store.add_email(
                    email_id=email_data["id"],
                    subject=email_data["subject"],
                    from_addr=email_data["from_addr"],
                    to_addrs=",".join(email_data["to_addrs"]),
                    cc_addrs=",".join(email_data["cc_addrs"]) if email_data["cc_addrs"] else None,
                    body_text=email_data["body_text"],
                    metadata={
                        "account_id": account_id,
                        "folder": folder,
                        "date": email_data["date"],
                    },
                )

                synced += 1

            logger.info(
                "email.synced", {"account_id": account_id, "folder": folder, "count": synced}
            )
            return synced

    except Exception as e:
        logger.error("email.sync_error", {"account_id": account_id, "error": str(e)})
        raise


def email_list_from_db(
    account_id: str, folder: str, limit: int = 20, user_id: str = "default"
) -> list[dict]:
    """Get emails from local store."""
    engine = _get_engine(user_id)

    with engine.connect() as conn:
        result = conn.execute(
            text("""
            SELECT id, account_id, folder, message_id, from_addr, from_name,
                   to_addrs, subject, date, read, flagged, has_attachments,
                   in_reply_to, is_forwarded, tags
            FROM emails
            WHERE account_id = :account_id AND folder = :folder
            ORDER BY date DESC
            LIMIT :limit
        """),
            {"account_id": account_id, "folder": folder, "limit": limit},
        )

        emails = []
        for row in result:
            emails.append(
                {
                    "id": row[0],
                    "account_id": row[1],
                    "folder": row[2],
                    "message_id": row[3],
                    "from_addr": row[4],
                    "from_name": row[5],
                    "to_addrs": row[6],
                    "subject": row[7],
                    "date": row[8],
                    "read": bool(row[9]),
                    "flagged": bool(row[10]),
                    "has_attachments": bool(row[11]),
                    "in_reply_to": row[12],
                    "is_forwarded": bool(row[13]),
                    "tags": row[14] or "",
                }
            )

        return emails


def email_get_from_db(email_id: str, user_id: str = "default") -> dict | None:
    """Get full email from local store."""
    engine = _get_engine(user_id)

    with engine.connect() as conn:
        result = conn.execute(
            text("""
            SELECT * FROM emails WHERE id = :id
        """),
            {"id": email_id},
        ).fetchone()

        if not result:
            return None

        row = result._mapping
        return {
            "id": row["id"],
            "account_id": row["account_id"],
            "folder": row["folder"],
            "message_id": row["message_id"],
            "from_addr": row["from_addr"],
            "from_name": row["from_name"],
            "to_addrs": row["to_addrs"].split(",") if row["to_addrs"] else [],
            "cc_addrs": row["cc_addrs"].split(",") if row["cc_addrs"] else [],
            "subject": row["subject"],
            "body_text": row["body_text"],
            "date": row["date"],
            "in_reply_to": row["in_reply_to"],
            "references": row["thread_references"],
            "is_forwarded": bool(row["is_forwarded"]),
            "read": bool(row["read"]),
            "flagged": bool(row["flagged"]),
            "has_attachments": bool(row["has_attachments"]),
            "attachments": row["attachments"],
            "tags": row["tags"] or "",
        }
