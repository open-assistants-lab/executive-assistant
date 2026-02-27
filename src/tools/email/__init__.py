"""Email tools."""

from src.tools.email.account import email_accounts, email_connect, email_disconnect
from src.tools.email.read import email_get, email_list, email_search
from src.tools.email.send import email_send
from src.tools.email.sync import email_sync

__all__ = [
    "email_connect",
    "email_disconnect",
    "email_accounts",
    "email_sync",
    "email_list",
    "email_get",
    "email_search",
    "email_send",
]
