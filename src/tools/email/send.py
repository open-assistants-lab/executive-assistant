"""Email send tool."""

from langchain_core.tools import tool
from sqlalchemy import text

from src.app_logging import get_logger
from src.tools.email.db import get_account_id_by_name, get_engine, load_accounts

logger = get_logger()


def get_email_by_id(email_id: str, account_id: str, user_id: str) -> dict | None:
    """Get email by ID from local DB."""
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


def send_via_smtp(
    account_name: str,
    to: list[str],
    subject: str,
    body: str,
    cc: list[str] | None = None,
    user_id: str = "",
) -> dict:
    """Send email via SMTP."""
    accounts = load_accounts(user_id)
    account_id = get_account_id_by_name(account_name, user_id)
    if not account_id:
        return {"success": False, "error": f"Account '{account_name}' not found"}

    account = accounts.get(account_id, {})
    email = account.get("email")
    password = account.get("password")
    smtp_host = account.get("smtp_host")
    smtp_port = account.get("smtp_port", 587)

    if not all([email, password, smtp_host]):
        return {"success": False, "error": "Account missing SMTP credentials"}

    try:
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        msg = MIMEMultipart()
        msg["From"] = email
        msg["To"] = ", ".join(to)
        msg["Subject"] = subject

        if cc:
            msg["Cc"] = ", ".join(cc)

        msg.attach(MIMEText(body, "plain"))

        all_recipients = to + (cc or [])

        server = smtplib.SMTP(smtp_host, smtp_port)
        server.starttls()
        server.login(email, password)
        server.sendmail(email, all_recipients, msg.as_string())
        server.quit()

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

        original_email = get_email_by_id(reply_to, account_id, user_id)
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
        result = send_via_smtp(
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
