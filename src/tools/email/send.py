"""Email send tool."""

from langchain_core.tools import tool

from src.app_logging import get_logger
from src.tools.email.smtp import send_via_smtp

logger = get_logger()


@tool
def email_send(
    account_name: str,
    to: str,
    subject: str,
    body: str,
    cc: str | None = None,
    user_id: str = "default",
) -> str:
    """Send an email.

    Args:
        account_name: Account name to send from
        to: Recipient email address (comma-separated for multiple)
        subject: Email subject
        body: Email body content
        cc: CC recipients (optional)
        user_id: User identifier (default: default)

    Returns:
        Success or error message
    """
    # Parse recipients
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
            return result["message"]
        else:
            return f"Error: {result['error']}"

    except Exception as e:
        logger.error("email_send_error", {"account": account_name, "error": str(e)})
        return f"Error sending email: {e}"
