"""Email SMTP sending."""

from pathlib import Path
from typing import Any

import yaml

from src.app_logging import get_logger
from src.tools.vault.store import get_vault

logger = get_logger()


def _load_accounts(user_id: str) -> dict[str, Any]:
    """Load accounts from YAML."""
    path = Path(f"data/users/{user_id}/email/accounts.yaml")
    if not path.exists():
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


def send_via_smtp(
    account_name: str,
    to: list[str],
    subject: str,
    body: str,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    user_id: str = "default",
) -> dict:
    """Send email via SMTP."""
    accounts = _load_accounts(user_id)

    # Find account
    account = None
    for acc in accounts.values():
        if acc["name"] == account_name:
            account = acc
            break

    if not account:
        return {"success": False, "error": f"Account '{account_name}' not found"}

    # Get credentials
    vault = get_vault(user_id)
    if not vault.is_unlocked():
        return {"success": False, "error": "Vault is locked"}

    cred = vault.get_credential(account["credential_name"])
    if not cred:
        return {"success": False, "error": "Credential not found"}

    try:
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        # Create message
        msg = MIMEMultipart()
        msg["From"] = cred.email
        msg["To"] = ", ".join(to)
        msg["Subject"] = subject

        if cc:
            msg["Cc"] = ", ".join(cc)

        msg.attach(MIMEText(body, "plain"))

        # Send
        server = smtplib.SMTP(cred.smtp_host, cred.smtp_port)
        server.starttls()
        server.login(cred.username, cred.password)

        all_recipients = to + (cc or []) + (bcc or [])
        server.sendmail(cred.email, all_recipients, msg.as_string())
        server.quit()

        logger.info("email.sent", {"account": account_name, "to": to})
        return {"success": True, "message": f"Email sent to {', '.join(to)}"}

    except Exception as e:
        logger.error("email.send_error", {"account": account_name, "error": str(e)})
        return {"success": False, "error": str(e)}
