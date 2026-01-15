"""User confirmation tool for large operations."""

from langchain_core.tools import tool
from contextvars import ContextVar

# Context variable to store pending proposal
_pending_proposal: ContextVar[dict | None] = ContextVar("_pending_proposal", default=None)


@tool
def request_confirmation(
    action: str,
    details: str,
) -> str:
    """
    Request user confirmation before performing a large operation.

    Use this tool when you're about to:
    - Store more than 5 documents in KB
    - Create database tables with many rows
    - Perform operations on multiple files
    - Any other significant operation

    The user's response will be available in the next message.

    Args:
        action: Brief description of what you plan to do (e.g., "Store 12 documents in KB")
        details: More detailed explanation of the operation

    Returns:
        Confirmation request message to show the user.

    Examples:
        >>> request_confirmation("Store 15 documents in KB", "Splitting MFA.txt by Article, covering all 19 articles with summaries and metadata")
        "📋 Proposed Action: Store 15 documents in KB\\n\\nDetails: Splitting MFA.txt by Article...\\n\\nPlease confirm with 'yes' to proceed."
    """
    # Store the proposal for the next handler to check
    _pending_proposal.set({"action": action, "details": details})

    return (
        f"📋 *Proposed Action: {action}*\n\n"
        f"{details}\n\n"
        f"Reply 'yes' to confirm, 'no' to cancel, or 'modify' to change the plan."
    )


def get_pending_proposal() -> dict | None:
    """Get the pending proposal awaiting user confirmation."""
    return _pending_proposal.get()


def clear_pending_proposal() -> None:
    """Clear the pending proposal."""
    _pending_proposal.set(None)


def check_user_confirmation(message: str) -> tuple[bool, str | None]:
    """
    Check if user's message is a response to a pending confirmation request.

    Args:
        message: User's message text

    Returns:
        Tuple of (is_confirmation_response, approved_rejected_cancelled)
        - approved_rejected_cancelled: 'approved', 'rejected', 'cancelled', or None
    """
    proposal = get_pending_proposal()
    if not proposal:
        return False, None

    msg_lower = message.lower().strip()

    # Check for approval
    if msg_lower in ("yes", "y", "confirm", "proceed", "go ahead", "do it"):
        clear_pending_proposal()
        return True, "approved"

    # Check for rejection
    if msg_lower in ("no", "n", "cancel", "stop", "don't"):
        clear_pending_proposal()
        return True, "rejected"

    # Check for modification request
    if msg_lower in ("modify", "change", "different"):
        return True, "modify"

    # Not a direct response to confirmation
    return False, None
