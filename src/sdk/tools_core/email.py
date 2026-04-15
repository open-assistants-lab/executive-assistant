"""Email tools — SDK-native implementation."""

import asyncio
import uuid
from datetime import UTC, datetime

from sqlalchemy import text

from src.app_logging import get_logger
from src.config import get_settings
from src.sdk.tools import ToolAnnotations, tool
from src.sdk.tools_core.email_db import (
    delete_account as db_delete_account,
)
from src.sdk.tools_core.email_db import (
    detect_provider,
    get_account_id_by_name,
    get_engine,
    load_accounts,
    save_account,
)
from src.sdk.tools_core.email_sync import start_background_sync

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

    logger.info("email_connect_called", {"email": email}, user_id=user_id)

    provider, imap_host, imap_port, smtp_host, smtp_port = detect_provider(email)

    if not imap_host:
        return f"Error: Could not detect email provider for {email}. Please use Gmail, Outlook, iCloud, or Yahoo."

    try:
        from imap_tools import MailBox

        with MailBox(imap_host, imap_port).login(email, password) as mailbox:
            folder_list = [f.name for f in mailbox.folder.list()]
            logger.info(
                "email.connect_success", {"account": email, "folders": folder_list}, user_id=user_id
            )

    except Exception as e:
        logger.error("email.connect_failed", {"account": email, "error": str(e)}, user_id=user_id)
        return f"Error: Failed to connect to email: {e}\n\nTip: If you have 2FA enabled, use an app password."

    accounts = load_accounts(user_id)
    for acc_id, acc in accounts.items():
        if acc.get("email") == email:
            return f"""Already connected!

Account: {acc["name"]}
Email: {acc["email"]}
Provider: {acc["provider"]}

Use email_list to fetch emails."""

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

    start_background_sync(user_id, account_id)

    return f"""Connected successfully!

Account: {username}
Email: {email}
Provider: {provider}

📧 Syncing your emails in the background (newest first)..."""


email_connect.annotations = ToolAnnotations(title="Connect Email", open_world=True)


@tool
def email_disconnect(account_name: str, user_id: str = "") -> str:
    """Disconnect and remove an email account.

    Args:
        account_name: Account name to disconnect
        user_id: User identifier (REQUIRED)

    Returns:
        Success or error message
    """
    if not user_id:
        return "Error: user_id is required."

    account_id = get_account_id_by_name(account_name, user_id)
    if not account_id:
        return f"Error: Account '{account_name}' not found. Use email_accounts to see available."

    db_delete_account(user_id, account_id)

    logger.info("email.disconnected", {"account": account_name}, user_id=user_id)
    return f"Account '{account_name}' disconnected and removed."


email_disconnect.annotations = ToolAnnotations(title="Disconnect Email", destructive=True)


@tool
def email_accounts(user_id: str = "") -> str:
    """List connected email accounts.

    Args:
        user_id: User identifier (REQUIRED)

    Returns:
        List of connected accounts
    """
    if not user_id:
        return "Error: user_id is required."

    accounts = load_accounts(user_id)

    if not accounts:
        return "No email accounts connected. Use email_connect to add one."

    output = "Connected email accounts:\n"
    for acc in accounts.values():
        output += f"- {acc['name']}: {acc['email']} ({acc['provider']})\n"
        output += f"  Status: {acc['status']}, Folders: {acc.get('folders', [])}\n"

    return output


email_accounts.annotations = ToolAnnotations(
    title="List Email Accounts", read_only=True, idempotent=True
)


@tool
def email_list(
    account_name: str,
    folder: str = "INBOX",
    limit: int = 20,
    user_id: str = "",
) -> str:
    """List emails from an account.

    Args:
        account_name: Account name to list emails from
        folder: Folder name (default: INBOX)
        limit: Max emails to return (default: 20, max: 100)
        user_id: User ID (REQUIRED)

    Returns:
        Formatted list of emails
    """
    if not user_id:
        return "Error: user_id is required."

    account_id = get_account_id_by_name(account_name, user_id)
    if not account_id:
        return f"Error: Account '{account_name}' not found."

    engine = get_engine(user_id)
    limit = min(limit, 100)

    with engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT message_id, from_addr, from_name, subject, timestamp,
                       read, flagged, has_attachments, in_reply_to, is_forwarded
                FROM emails
                WHERE account_id = :account_id AND folder = :folder
                ORDER BY timestamp DESC
                LIMIT :limit
            """),
            {"account_id": account_id, "folder": folder, "limit": limit},
        )

        rows = result.fetchall()

    if not rows:
        return f"No emails in {folder}."

    output = f"Emails in {folder} (showing {len(rows)}):\n\n"
    for i, row in enumerate(rows, 1):
        (
            msg_id,
            from_addr,
            from_name,
            subject,
            ts,
            read,
            flagged,
            has_attach,
            in_reply,
            forwarded,
        ) = row
        read_str = "📭" if not read else "📬"
        flag_str = "⭐" if flagged else ""
        attach_str = "📎" if has_attach else ""
        reply_str = "↩️" if in_reply else ""

        from_display = from_name or from_addr
        subject_preview = (
            (subject[:50] + "...") if subject and len(subject) > 50 else subject or "(No subject)"
        )

        date_str = datetime.fromtimestamp(ts, UTC).strftime("%Y-%m-%d %H:%M") if ts else "Unknown"

        output += f"{i}. {read_str}{flag_str}{attach_str}{reply_str} {from_display}\n"
        output += f"   {subject_preview}\n"
        output += f"   {date_str}\n"
        output += f"   ID: {msg_id}\n\n"

    return output.strip()


email_list.annotations = ToolAnnotations(title="List Emails", read_only=True, idempotent=True)


@tool
def email_get(
    email_id: str,
    account_name: str,
    user_id: str = "",
    folder: str = "INBOX",
) -> str:
    """Get full email content.

    Args:
        email_id: Email ID (from email_list)
        account_name: Account name
        user_id: User ID (REQUIRED)
        folder: Email folder (default: INBOX)

    Returns:
        Full email content
    """
    if not user_id:
        return "Error: user_id is required."

    account_id = get_account_id_by_name(account_name, user_id)
    if not account_id:
        return f"Error: Account '{account_name}' not found."

    engine = get_engine(user_id)

    with engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT * FROM emails
                WHERE account_id = :account_id AND folder = :folder AND message_id = :email_id
            """),
            {"account_id": account_id, "folder": folder, "email_id": email_id},
        ).fetchone()

    if not result:
        return f"Error: Email {email_id} not found."

    row = result._mapping

    from_display = (
        f"{row['from_name']} <{row['from_addr']}>" if row["from_name"] else row["from_addr"]
    )
    to_list = row["to_addrs"].replace(",", ", ") if row["to_addrs"] else ""
    cc_list = row["cc_addrs"].replace(",", ", ") if row["cc_addrs"] else ""

    date_str = (
        datetime.fromtimestamp(row["timestamp"], UTC).strftime("%Y-%m-%d %H:%M:%S")
        if row["timestamp"]
        else "Unknown"
    )

    output = f"""From: {from_display}
To: {to_list}
{"CC: " + cc_list if cc_list else ""}
Date: {date_str}
Subject: {row["subject"]}
{"(Reply-To: " + row["in_reply_to"] + ")" if row["in_reply_to"] else ""}
{"(Forwarded)" if row["is_forwarded"] else ""}

{row["body_text"] or "(No body)"}"""

    with engine.connect() as conn:
        conn.execute(
            text(
                "UPDATE emails SET read = 1 WHERE account_id = :account_id AND message_id = :email_id"
            ),
            {"account_id": account_id, "email_id": email_id},
        )
        conn.commit()

    return output.strip()


email_get.annotations = ToolAnnotations(title="Get Email", read_only=True, idempotent=True)


@tool
def email_search(
    query: str,
    account_name: str,
    folder: str = "INBOX",
    limit: int = 20,
    user_id: str = "",
) -> str:
    """Search emails by subject or sender.

    Args:
        query: Search query (matches subject or sender)
        account_name: Account name to search
        folder: Folder to search (default: INBOX)
        limit: Max results (default: 20, max: 100)
        user_id: User ID (REQUIRED)

    Returns:
        Matching emails
    """
    if not user_id:
        return "Error: user_id is required."

    if not query:
        return "Error: query is required."

    account_id = get_account_id_by_name(account_name, user_id)
    if not account_id:
        return f"Error: Account '{account_name}' not found."

    engine = get_engine(user_id)
    limit = min(limit, 100)
    search_pattern = f"%{query}%"

    with engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT message_id, from_addr, from_name, subject, timestamp,
                       read, flagged, has_attachments
                FROM emails
                WHERE account_id = :account_id
                  AND folder = :folder
                  AND (subject LIKE :query OR from_addr LIKE :query OR from_name LIKE :query)
                ORDER BY timestamp DESC
                LIMIT :limit
            """),
            {
                "account_id": account_id,
                "folder": folder,
                "query": search_pattern,
                "limit": limit,
            },
        )

        rows = result.fetchall()

    if not rows:
        return f"No emails matching '{query}' in {folder}."

    output = f"Found {len(rows)} emails matching '{query}' in {folder}:\n\n"
    for i, row in enumerate(rows, 1):
        msg_id, from_addr, from_name, subject, ts, read, flagged, has_attach = row
        read_str = "📭" if not read else "📬"
        flag_str = "⭐" if flagged else ""
        attach_str = "📎" if has_attach else ""

        from_display = from_name or from_addr
        subject_preview = (
            (subject[:50] + "...") if subject and len(subject) > 50 else subject or "(No subject)"
        )

        date_str = datetime.fromtimestamp(ts, UTC).strftime("%Y-%m-%d %H:%M") if ts else "Unknown"

        output += f"{i}. {read_str}{flag_str}{attach_str} {from_display}\n"
        output += f"   {subject_preview}\n"
        output += f"   {date_str}\n"
        output += f"   ID: {msg_id}\n\n"

    return output.strip()


email_search.annotations = ToolAnnotations(title="Search Emails", read_only=True)


def _get_email_by_id(email_id: str, account_id: str, user_id: str) -> dict | None:
    engine = get_engine(user_id)
    with engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT from_addr, to_addrs, cc_addrs, subject, in_reply_to, thread_references
                FROM emails
                WHERE account_id = :account_id AND message_id = :email_id
            """),
            {"account_id": account_id, "email_id": email_id},
        ).fetchone()
        if result:
            return dict(result._mapping)
    return None


def _send_via_smtp(
    account_name: str,
    to: list[str],
    subject: str,
    body: str,
    cc: list[str] | None = None,
    user_id: str = "",
) -> dict:
    accounts = load_accounts(user_id)
    account_id = get_account_id_by_name(account_name, user_id)
    if not account_id:
        return {"success": False, "error": f"Account '{account_name}' not found"}

    account = accounts.get(account_id, {})
    email_addr = account.get("email")
    password = account.get("password")
    smtp_host = account.get("smtp_host")
    smtp_port = account.get("smtp_port", 587)

    if not all([email_addr, password, smtp_host]):
        return {"success": False, "error": "Account missing SMTP credentials"}

    try:
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        msg = MIMEMultipart()
        msg["From"] = email_addr
        msg["To"] = ", ".join(to)
        msg["Subject"] = subject

        if cc:
            msg["Cc"] = ", ".join(cc)

        msg.attach(MIMEText(body, "plain"))

        all_recipients = to + (cc or [])

        server = smtplib.SMTP(smtp_host, smtp_port)
        try:
            server.starttls()
            server.login(email_addr, password)
            server.sendmail(email_addr, all_recipients, msg.as_string())
        finally:
            try:
                server.quit()
            except Exception:
                try:
                    server.close()
                except Exception:
                    pass

        logger.info("email_sent", {"account": account_name, "to": to}, user_id=user_id)

        return {"success": True, "message": f"Email sent to {', '.join(to)}"}
    except Exception as e:
        logger.error(
            "email_send_error", {"account": account_name, "error": str(e)}, user_id=user_id
        )
        return {"success": False, "error": str(e)}


@tool
def email_send(
    account_name: str,
    to: str,
    subject: str,
    body: str,
    cc: str | None = None,
    reply_to: str | None = None,
    reply_all: bool = False,
    user_id: str = "",
) -> str:
    """Send an email or reply to an existing email.

    Args:
        account_name: Account name to send from
        to: Recipient email address (comma-separated for multiple)
        subject: Email subject
        body: Email body content
        cc: CC recipients (optional)
        reply_to: Email ID to reply to (optional - if set, sends as reply)
        reply_all: If replying, include all recipients (default: False)
        user_id: User ID (REQUIRED)

    Returns:
        Success or error message
    """
    if not user_id:
        return "Error: user_id is required."

    original_email = None
    if reply_to:
        account_id = get_account_id_by_name(account_name, user_id)
        if not account_id:
            return f"Error: Account '{account_name}' not found."

        original_email = _get_email_by_id(reply_to, account_id, user_id)
        if not original_email:
            return f"Error: Email {reply_to} not found."

        original_to = original_email.get("to_addrs", "")
        original_cc = original_email.get("cc_addrs", "")
        sender = original_email.get("from_addr", "")

        if reply_all:
            accounts = load_accounts(user_id)
            self_email = accounts.get(account_id, {}).get("email", "")

            to_list = [sender]
            for addr in original_to.split(","):
                addr = addr.strip()
                if addr and addr != self_email:
                    to_list.append(addr)

            cc_list = []
            for addr in original_cc.split(","):
                addr = addr.strip()
                if addr and addr != self_email:
                    cc_list.append(addr)
        else:
            to_list = [sender]
            cc_list = None

        if not subject.lower().startswith("re:"):
            subject = f"Re: {subject}"
    else:
        to_list = [t.strip() for t in to.split(",")]
        cc_list = [c.strip() for c in cc.split(",")] if cc else None

    try:
        result = _send_via_smtp(
            account_name=account_name,
            to=to_list,
            subject=subject,
            body=body,
            cc=cc_list,
            user_id=user_id,
        )

        if result["success"]:
            if reply_to:
                return f"✅ Reply sent to {', '.join(to_list)}"
            return result["message"]
        else:
            return f"Error: {result['error']}"

    except Exception as e:
        logger.error(
            "email_send_error", {"account": account_name, "error": str(e)}, user_id=user_id
        )
        return f"Error sending email: {e}"


email_send.annotations = ToolAnnotations(title="Send Email", open_world=True)


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

    account_id = get_account_id_by_name(account_name, user_id)
    if not account_id:
        return f"Error: Account '{account_name}' not found."

    from src.sdk.tools_core.email_sync import _sync_emails as _do_sync

    async def _sync():
        limit = (
            SETTINGS.email_sync.backfill_limit if mode == "full" else SETTINGS.email_sync.batch_size
        )
        count = await _do_sync(user_id, account_id, folder, mode, limit)
        return count

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    try:
        if loop and loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, _sync())
                count = future.result(timeout=120)
        else:
            count = asyncio.run(_sync())
        return f"Synced {count} emails ({mode} mode) for {account_name}."
    except Exception as e:
        return f"Error syncing: {e}"


email_sync.annotations = ToolAnnotations(title="Sync Emails")
