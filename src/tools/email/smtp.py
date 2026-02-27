"""Email SMTP sending."""

from pathlib import Path
from typing import Any

from src.app_logging import get_logger
from src.tools.email.imap import _load_accounts as load_imap_accounts

logger = get_logger()


def _detect_smtp_provider(email: str) -> tuple[str, str, int]:
    """Detect SMTP provider and return (provider, smtp_host, smtp_port)."""
    email_lower = email.lower()

    if "gmail.com" in email_lower or "googlemail.com" in email_lower:
        return ("gmail", "smtp.gmail.com", 587)
    elif "outlook.com" in email_lower or "hotmail.com" in email_lower or "live.com" in email_lower:
        return ("outlook", "smtp.office365.com", 587)
    elif "icloud.com" in email_lower or "me.com" in email_lower:
        return ("icloud", "smtp.mail.me.com", 587)
    elif "yahoo.com" in email_lower:
        return ("yahoo", "smtp.mail.yahoo.com", 587)

    return ("other", "", 587)


def send_via_smtp(
    account_name: str,
    to: list[str],
    subject: str,
    body: str,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    user_id: str = "",
) -> dict:
    """Send email via SMTP."""
    accounts = load_imap_accounts(user_id)

    # Find account by name
    account = None
    for acc in accounts.values():
        if acc.get("name") == account_name:
            account = acc
            break

    if not account:
        return {"success": False, "error": f"Account '{account_name}' not found"}

    email = account.get("email")
    password = account.get("password")

    if not email or not password:
        return {"success": False, "error": "Account missing credentials"}

    # Detect SMTP provider
    provider, smtp_host, smtp_port = _detect_smtp_provider(email)

    try:
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        # Create message
        msg = MIMEMultipart()
        msg["From"] = email
        msg["To"] = ", ".join(to)
        msg["Subject"] = subject

        if cc:
            msg["Cc"] = ", ".join(cc)

        msg.attach(MIMEText(body, "plain"))

        # Send
        server = smtplib.SMTP(smtp_host, smtp_port)
        server.starttls()
        server.login(email, password)

        all_recipients = to + (cc or []) + (bcc or [])
        server.sendmail(email, all_recipients, msg.as_string())
        server.quit()

        logger.info("email.sent", {"account": account_name, "to": to})
        return {"success": True, "message": f"Email sent to {', '.join(to)}"}

    except Exception as e:
        logger.error("email.send_error", {"account": account_name, "error": str(e)})
        return {"success": False, "error": str(e)}
