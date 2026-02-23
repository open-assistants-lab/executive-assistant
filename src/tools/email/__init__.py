"""Email tools."""

from src.tools.email.account import email_accounts, email_connect, email_disconnect
from src.tools.email.list_get import email_get, email_list, email_sync
from src.tools.email.search import email_search
from src.tools.email.send import email_send

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
