"""Email REST endpoints for Flutter browse mode.

GET  /emails              — list emails
GET  /emails/:id           — single email
GET  /emails/search?q=...  — hybrid search
POST /emails/sync          — trigger sync from Gmail/Outlook
"""

from fastapi import APIRouter, Depends

from src.storage.email_db import (
    count_emails,
    get_email,
    list_emails,
    mark_read,
    search_emails,
)

router = APIRouter(prefix="/emails", tags=["emails"])


@router.get("")
async def handle_list(
    user_id: str = "default_user",
    limit: int = 50,
    offset: int = 0,
    is_read: bool | None = None,
):
    emails = list_emails(user_id, limit=limit, offset=offset, is_read=is_read)
    total = count_emails(user_id)
    unread = count_emails(user_id, is_read=False)
    return {
        "emails": emails,
        "total": total,
        "unread": unread,
        "limit": limit,
        "offset": offset,
    }


@router.get("/search")
async def handle_search(q: str, user_id: str = "default_user", limit: int = 20):
    emails = search_emails(user_id, q, limit=limit)
    return {"emails": emails, "query": q}


@router.get("/{email_id}")
async def handle_get(email_id: str, user_id: str = "default_user"):
    email = get_email(user_id, email_id)
    if not email:
        return {"error": "not_found", "email_id": email_id}
    # Mark as read on open
    mark_read(user_id, email_id)
    return email


@router.post("/sync")
async def handle_sync(user_id: str = "default_user", provider: str = "gmail"):
    """Trigger a manual email sync. Returns immediately, sync runs in background."""
    import asyncio

    from src.config.settings import get_settings

    settings = get_settings()

    if provider in ("gmail", "google"):
        if not settings.email.gws_client_id:
            return {"error": "gws_client_id not configured"}
        # Schedule background sync
        asyncio.create_task(_sync_gmail(user_id, settings))
    elif provider in ("outlook", "m365"):
        if not settings.email.m365_client_id:
            return {"error": "m365_client_id not configured"}
        asyncio.create_task(_sync_outlook(user_id, settings))

    return {"status": "sync_started", "provider": provider}


async def _sync_gmail(user_id: str, settings):
    """Background Gmail sync via gws CLI."""
    import json

    from src.app_logging import get_logger

    logger = get_logger()

    try:
        proc = await asyncio.create_subprocess_exec(
            "gws", "gmail", "messages", "list",
            "--filter", "is:unread OR newer_than:1d",
            "--format", "json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={
                **__import__("os").environ,
                "GOOGLE_WORKSPACE_CLI_CLIENT_ID": settings.email.gws_client_id,
                "GOOGLE_WORKSPACE_CLI_CLIENT_SECRET": settings.email.gws_client_secret,
            },
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            logger.warning("gws_sync_failed", {"stderr": stderr.decode()[:200]}, user_id=user_id)
            return

        data = json.loads(stdout)
        messages = data if isinstance(data, list) else data.get("messages", [])

        emails = []
        for msg in messages:
            emails.append({
                "id": msg.get("id", "") or msg.get("threadId", ""),
                "from": _extract_header(msg, "From"),
                "to": _extract_header(msg, "To"),
                "subject": _extract_header(msg, "Subject"),
                "snippet": msg.get("snippet", ""),
                "body": msg.get("snippet", ""),
                "received_at": _extract_header(msg, "Date"),
                "is_read": "UNREAD" not in (msg.get("labelIds", [])),
                "labels": msg.get("labelIds", []),
                "thread_id": msg.get("threadId", ""),
                "provider": "gmail",
            })

        stored = store_emails(user_id, emails)
        logger.info("gws_sync_done", {"stored": stored, "total": len(emails)}, user_id=user_id)
    except Exception as e:
        logger.error("gws_sync_error", {"error": str(e)[:200]}, user_id=user_id)


async def _sync_outlook(user_id: str, settings):
    """Background Outlook sync via m365 CLI."""
    # Deferred: requires m365 CLI setup. Same pattern as _sync_gmail.
    pass


def _extract_header(msg: dict, name: str) -> str:
    headers = msg.get("payload", {}).get("headers", [])
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


from src.storage.email_db import store_emails  # noqa: E402
