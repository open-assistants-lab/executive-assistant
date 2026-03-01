"""Email read tools - list, get, search."""

from datetime import UTC, datetime

from langchain_core.tools import tool
from sqlalchemy import text

from src.app_logging import get_logger
from src.tools.email.db import get_account_id_by_name, get_engine

logger = get_logger()


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


@tool
def email_get(
    email_id: str,
    account_name: str,
    user_id: str = "",
) -> str:
    """Get full email content.

    Args:
        email_id: Email ID (from email_list)
        account_name: Account name
        user_id: User ID (REQUIRED)

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
                WHERE account_id = :account_id AND message_id = :email_id
            """),
            {"account_id": account_id, "email_id": email_id},
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

    # Mark as read
    with engine.connect() as conn:
        conn.execute(
            text(
                "UPDATE emails SET read = 1 WHERE account_id = :account_id AND message_id = :email_id"
            ),
            {"account_id": account_id, "email_id": email_id},
        )
        conn.commit()

    return output.strip()


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
