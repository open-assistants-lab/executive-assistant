"""Email IMAP operations and caching."""

from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text

from src.app_logging import get_logger
from src.tools.email.vector import get_email_vector_store

logger = get_logger()


def _parse_email_date(date_str: str) -> int:
    """Parse email date string to Unix timestamp."""
    if not date_str:
        return int(datetime.now(UTC).timestamp())
    try:
        dt = parsedate_to_datetime(date_str)
        return int(dt.timestamp())
    except Exception:
        try:
            dt = datetime.strptime(date_str, "%d %b %Y %H:%M:%S %z")
            return int(dt.timestamp())
        except Exception:
            return int(datetime.now(UTC).timestamp())


def _get_db_path(user_id: str) -> Path:
    """Get SQLite database path for user."""
    if not user_id or user_id == "default":
        raise ValueError(f"Invalid user_id: {user_id}")
    # Get project root relative to current working directory
    cwd = Path.cwd()
    base_dir = cwd / "data" / "users" / user_id / "email"
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir / "emails.db"


def _get_engine(user_id: str):
    """Get SQLAlchemy engine."""
    db_path = _get_db_path(user_id)
    engine = create_engine(f"sqlite:///{db_path}")
    _init_db(engine)
    return engine


# Alias for backward compatibility
_get_account_db_path = _get_db_path


def _init_db(engine) -> None:
    """Initialize database schema."""
    with engine.connect() as conn:
        # Emails table
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

        # Create index on timestamp for sorting
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_emails_timestamp ON emails(timestamp)"))

        # Create index on created_at for sorting
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_emails_created_at ON emails(created_at)"))

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
                email TEXT NOT NULL,
                password TEXT NOT NULL,
                imap_host TEXT NOT NULL,
                imap_port INTEGER DEFAULT 993,
                provider TEXT NOT NULL,
                folders TEXT NOT NULL,
                last_sync INTEGER,
                last_timestamp INTEGER,
                status TEXT DEFAULT 'connected',
                created_at INTEGER NOT NULL
            )
        """)
        )

        conn.commit()


def _get_account_engine(user_id: str):
    """Get SQLAlchemy engine for accounts."""
    db_path = _get_db_path(user_id)
    engine = create_engine(f"sqlite:///{db_path}")
    _init_db(engine)
    return engine


def _load_accounts(user_id: str) -> dict[str, Any]:
    """Load accounts from database."""
    engine = _get_account_engine(user_id)

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


def _get_account_id_by_name(account_name: str, user_id: str) -> str | None:
    """Get account ID by name or email.

    Searches in order:
    1. Account name (exact match)
    2. Email address (fallback)
    """
    accounts = _load_accounts(user_id)
    for acc_id, acc in accounts.items():
        if acc.get("name") == account_name:
            return acc_id
        if acc.get("email") == account_name:
            return acc_id
    return None


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

    # Parse date to Unix timestamp
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


def sync_folder(
    account_id: str,
    folder: str,
    mode: str = "new",
    limit: int = 100,
    user_id: str = "",
) -> int:
    """Sync emails from a folder to local store.

    Modes:
        - "new": Fetch emails newer than last_sync (quick sync)
        - "older": Fetch emails older than oldest in DB (backfill)

    Args:
        account_id: Account ID
        folder: Folder name
        mode: "new" or "older"
        limit: Max emails to fetch
        user_id: User ID

    Returns:
        Number of emails synced
    """
    try:
        engine = _get_engine(user_id)

        # Get sync parameters from account
        accounts = _load_accounts(user_id)
        account = accounts.get(account_id)
        if not account:
            raise ValueError(f"Account {account_id} not found")

        with _get_imap_connection(account_id, user_id) as mailbox:
            mailbox.folder.set(folder)

            # Determine date range based on mode
            with engine.connect() as conn:
                if mode == "new":
                    # Get last sync timestamp
                    last_sync = account.get("last_timestamp")
                    if last_sync:
                        from imap_tools import AND

                        # Convert timestamp to date for IMAP query
                        sync_date = datetime.fromtimestamp(last_sync).date()
                        query = AND(date_gte=sync_date)
                        messages = list(mailbox.fetch(limit=limit, reverse=True, criteria=query))
                    else:
                        # First sync - get all
                        messages = list(mailbox.fetch(limit=limit, reverse=True))
                elif mode == "older":
                    # Get oldest timestamp in DB
                    oldest = conn.execute(
                        text("""
                            SELECT MIN(timestamp) FROM emails
                            WHERE account_id = :account_id AND folder = :folder
                        """),
                        {"account_id": account_id, "folder": folder},
                    ).fetchone()[0]

                    if oldest:
                        from imap_tools import AND

                        # Convert timestamp to date for IMAP query
                        oldest_date = datetime.fromtimestamp(oldest).date()
                        query = AND(date_lt=oldest_date)
                        messages = list(mailbox.fetch(limit=limit, reverse=False, criteria=query))
                    else:
                        # No emails in DB, do a full sync
                        messages = list(mailbox.fetch(limit=limit, reverse=True))
                else:
                    raise ValueError(f"Unknown sync mode: {mode}")

            vector_store = get_email_vector_store(user_id)
            synced = 0
            newest_timestamp = 0

            for msg in messages:
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

                # Track newest timestamp
                if email_data["timestamp"] > newest_timestamp:
                    newest_timestamp = email_data["timestamp"]

                # Add to vector store
                vector_store.add_email(
                    email_id=email_data["message_id"],
                    subject=email_data["subject"],
                    from_addr=email_data["from_addr"],
                    to_addrs=",".join(email_data["to_addrs"]),
                    cc_addrs=",".join(email_data["cc_addrs"]) if email_data["cc_addrs"] else None,
                    body_text=email_data["body_text"],
                    metadata={
                        "account_id": account_id,
                        "folder": folder,
                        "timestamp": email_data["timestamp"],
                    },
                )

                synced += 1

            # Update account with last_sync info
            account["last_sync"] = int(datetime.now(UTC).timestamp())
            account["last_timestamp"] = newest_timestamp
            _save_account(user_id, account_id, account)

            logger.info(
                "email.synced",
                {"account_id": account_id, "folder": folder, "mode": mode, "count": synced},
            )
            return synced

    except Exception as e:
        logger.error("email.sync_error", {"account_id": account_id, "mode": mode, "error": str(e)})
        raise


def email_list_from_db(
    account_id: str, folder: str, limit: int = 20, user_id: str = ""
) -> list[dict]:
    """Get emails from local store."""
    engine = _get_engine(user_id)

    with engine.connect() as conn:
        result = conn.execute(
            text("""
            SELECT account_id, folder, message_id, from_addr, from_name,
                   to_addrs, subject, timestamp, read, flagged, has_attachments,
                   in_reply_to, is_forwarded, tags
            FROM emails
            WHERE account_id = :account_id AND folder = :folder
            ORDER BY timestamp DESC
            LIMIT :limit
        """),
            {"account_id": account_id, "folder": folder, "limit": limit},
        )

        emails = []
        for row in result:
            emails.append(
                {
                    "id": row["message_id"],
                    "account_id": row["account_id"],
                    "folder": row["folder"],
                    "message_id": row["message_id"],
                    "from_addr": row["from_addr"],
                    "from_name": row["from_name"],
                    "to_addrs": row["to_addrs"],
                    "subject": row["subject"],
                    "timestamp": row["timestamp"],
                    "read": bool(row["read"]),
                    "flagged": bool(row["flagged"]),
                    "has_attachments": bool(row["has_attachments"]),
                    "in_reply_to": row["in_reply_to"],
                    "is_forwarded": bool(row["is_forwarded"]),
                    "tags": row["tags"] or "",
                }
            )

        return emails


def email_get_from_db(
    email_id: str, account_id: str = "", folder: str = "INBOX", user_id: str = ""
) -> dict | None:
    """Get full email from local store."""
    engine = _get_engine(user_id)

    with engine.connect() as conn:
        result = conn.execute(
            text("""
            SELECT * FROM emails WHERE message_id = :email_id AND account_id = :account_id AND folder = :folder
        """),
            {"email_id": email_id, "account_id": account_id, "folder": folder},
        ).fetchone()

        if not result:
            return None

        row = result._mapping
        return {
            "id": row["message_id"],
            "account_id": row["account_id"],
            "folder": row["folder"],
            "message_id": row["message_id"],
            "from_addr": row["from_addr"],
            "from_name": row["from_name"],
            "to_addrs": row["to_addrs"].split(",") if row["to_addrs"] else [],
            "cc_addrs": row["cc_addrs"].split(",") if row["cc_addrs"] else [],
            "subject": row["subject"],
            "body_text": row["body_text"],
            "timestamp": row["timestamp"],
            "in_reply_to": row["in_reply_to"],
            "references": row["thread_references"],
            "is_forwarded": bool(row["is_forwarded"]),
            "read": bool(row["read"]),
            "flagged": bool(row["flagged"]),
            "has_attachments": bool(row["has_attachments"]),
            "attachments": row["attachments"],
            "tags": row["tags"] or "",
        }


def email_stats(user_id: str = "", account_name: str = "") -> dict:
    """Get email statistics for an account, or all accounts if no account specified."""
    if not user_id:
        return {"error": "user_id is required"}

    engine = _get_engine(user_id)
    accounts = _load_accounts(user_id)

    def get_account_stats(account_id: str, name: str) -> dict:
        with engine.connect() as conn:
            total = conn.execute(
                text("SELECT COUNT(*) FROM emails WHERE account_id = :account_id"),
                {"account_id": account_id},
            ).fetchone()[0]

            if total == 0:
                return {"account": name, "total": 0, "read": 0, "unread": 0, "flagged": 0}

            date_range = conn.execute(
                text("""
                    SELECT MIN(timestamp), MAX(timestamp)
                    FROM emails
                    WHERE account_id = :account_id
                """),
                {"account_id": account_id},
            ).fetchone()

            read_counts = conn.execute(
                text("""
                    SELECT SUM(read), SUM(flagged)
                    FROM emails
                    WHERE account_id = :account_id
                """),
                {"account_id": account_id},
            ).fetchone()

        read = read_counts[0] or 0
        return {
            "account": name,
            "total": total,
            "earliest": date_range[0],
            "latest": date_range[1],
            "read": read,
            "unread": total - read,
            "flagged": read_counts[1] or 0,
        }

    if account_name:
        account_id = _get_account_id_by_name(account_name, user_id)
        if not account_id:
            return {"error": f"Account '{account_name}' not found"}
        return get_account_stats(account_id, account_name)

    results = {}
    grand_total = 0
    for acc_id, acc in accounts.items():
        stats = get_account_stats(acc_id, acc.get("name", ""))
        results[acc.get("name", acc_id)] = stats
        grand_total += stats["total"]

    return {"accounts": results, "total": grand_total}


def run_email_sql(user_id: str = "", query: str = "") -> dict:
    """Run a SELECT query on email database.

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
        - "SELECT COUNT(*) FROM emails WHERE timestamp > strftime('%s', 'now') - 86400*30"
        - "SELECT * FROM emails WHERE from_addr LIKE '%@google.com%' LIMIT 10"
        - "SELECT COUNT(*) as cnt, from_addr FROM emails GROUP BY from_addr ORDER BY cnt DESC LIMIT 5"

    Args:
        user_id: User ID (REQUIRED)
        query: SQL SELECT query (no semicolons, no comments)

    Returns:
        Query results or error message
    """
    if not user_id:
        return {"error": "user_id is required"}
    if not query:
        return {"error": "query is required"}

    # Security: Only allow SELECT
    query_lower = query.strip().lower()
    if not query_lower.startswith("select"):
        return {"error": "Only SELECT queries are allowed"}

    # Block dangerous patterns
    forbidden = ["insert", "update", "delete", "drop", "create", "alter", ";", "--", "/*"]
    for word in forbidden:
        if word in query_lower:
            return {"error": f"Keyword '{word}' is not allowed"}

    engine = _get_engine(user_id)

    try:
        with engine.connect() as conn:
            result = conn.execute(text(query))
            rows = result.fetchall()
            columns = result.keys()

            # Convert to list of dicts
            results = []
            for row in rows:
                results.append(dict(zip(columns, row)))

            return {
                "columns": list(columns),
                "rows": results,
                "count": len(results),
            }
    except Exception as e:
        return {"error": str(e)}


def email_delete(
    user_id: str,
    account_name: str,
    email_id: str,
    target: str = "local",
) -> dict:
    """Delete an email from local DB, server, or both.

    Args:
        user_id: User ID
        account_name: Account name
        email_id: Email ID (message_id from email_list)
        target: "local" (default), "server", or "both"

    Returns:
        Result dict with status and details
    """
    if not user_id:
        return {"error": "user_id is required"}
    if not account_name:
        return {"error": "account_name is required"}
    if not email_id:
        return {"error": "email_id is required"}
    if target not in ("local", "server", "both"):
        return {"error": "target must be 'local', 'server', or 'both'"}

    account_id = _get_account_id_by_name(account_name, user_id)
    if not account_id:
        return {"error": f"Account '{account_name}' not found"}

    results = {"local": None, "server": None}

    # Get email for server deletion
    engine = _get_engine(user_id)
    with engine.connect() as conn:
        email = conn.execute(
            text("""
                SELECT folder, message_id FROM emails
                WHERE account_id = :account_id AND message_id = :email_id
            """),
            {"account_id": account_id, "email_id": email_id},
        ).fetchone()

        if not email:
            return {"error": f"Email {email_id} not found in local DB"}

        folder = email[0]
        message_id = email[1]

    # Delete from local DB
    if target in ("local", "both"):
        try:
            with engine.connect() as conn:
                conn.execute(
                    text("""
                        DELETE FROM emails
                        WHERE account_id = :account_id AND message_id = :email_id
                    """),
                    {"account_id": account_id, "email_id": email_id},
                )
                conn.commit()
            results["local"] = "deleted"
        except Exception as e:
            results["local"] = f"error: {str(e)}"

    # Delete from server
    if target in ("server", "both"):
        try:
            with _get_imap_connection(account_id, user_id) as mailbox:
                mailbox.folder.set(folder)
                mailbox.delete(message_id)
            results["server"] = "deleted"
        except Exception as e:
            results["server"] = f"error: {str(e)}"

    return {"status": "success", "results": results}
