"""Email account models."""

from typing import Literal

from pydantic import BaseModel, Field


class EmailAccount(BaseModel):
    """Connected email account."""

    id: str
    name: str = Field(description="User-friendly name, e.g., 'Work Gmail'")
    credential_name: str = Field(description="Reference to vault credential")
    email: str = Field(description="Email address")
    provider: Literal["gmail", "outlook", "yahoo", "office365", "imap"]
    folders: list[str] = Field(default=["INBOX", "SENT"])
    last_sync: str | None = None
    status: Literal["connected", "error", "disconnected"] = "connected"


class EmailFolder(BaseModel):
    """Email folder info."""

    name: str
    uidvalidity: int
    uidnext: int
    message_count: int


class EmailMessage(BaseModel):
    """Email message metadata."""

    id: str
    account_id: str
    folder: str
    message_id: str | None = None
    from_addr: str
    from_name: str | None = None
    to_addrs: list[str] = []
    cc_addrs: list[str] = []
    subject: str
    body_text: str = ""
    body_html: str = ""
    date: str
    read: bool = True
    flagged: bool = False
    has_attachments: bool = False
    attachments: list[dict] = []
