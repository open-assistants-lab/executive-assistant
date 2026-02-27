"""Email tools."""

from src.tools.email.account import email_accounts, email_connect, email_disconnect
from src.tools.email.list_get import (
    email_delete,
    email_get,
    email_list,
    email_stats,
    email_sync,
    run_email_sql,
)
from src.tools.email.search import email_search
from src.tools.email.send import email_send

__all__ = [
    "email_connect",
    "email_disconnect",
    "email_accounts",
    "email_sync",
    "email_list",
    "email_get",
    "email_delete",
    "email_search",
    "email_send",
    "email_stats",
    "run_email_sql",
]
