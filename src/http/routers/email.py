from fastapi import APIRouter

from src.http.models import EmailConnectRequest

router = APIRouter(prefix="/email", tags=["email"])


@router.get("/accounts")
async def list_email_accounts(user_id: str = "default_user"):
    """List connected email accounts."""
    from src.sdk.tools_core.email import email_accounts

    result = email_accounts.invoke({"user_id": user_id})
    return {"accounts": result}


@router.post("/accounts")
async def connect_email(req: EmailConnectRequest):
    """Connect an email account."""
    from src.sdk.tools_core.email import email_connect

    args = {"user_id": req.user_id, "email": req.email, "password": req.password}
    if req.provider is not None:
        args["provider"] = req.provider
    result = email_connect.invoke(args)
    return {"result": str(result)}


@router.delete("/accounts/{account_name}")
async def disconnect_email(account_name: str, user_id: str = "default_user"):
    """Disconnect an email account."""
    from src.sdk.tools_core.email import email_disconnect

    result = email_disconnect.invoke({"user_id": user_id, "account_name": account_name})
    return {"result": str(result)}


@router.get("/messages")
async def list_emails(
    account_name: str = "default",
    limit: int = 20,
    folder: str = "INBOX",
    user_id: str = "default_user",
):
    """List emails from an account."""
    from src.sdk.tools_core.email import email_list

    result = email_list.invoke(
        {"user_id": user_id, "account_name": account_name, "limit": limit, "folder": folder}
    )
    return {"emails": result}


@router.get("/messages/{email_id}")
async def get_email(
    email_id: str,
    account_name: str = "default",
    user_id: str = "default_user",
):
    """Get a specific email."""
    from src.sdk.tools_core.email import email_get

    result = email_get.invoke(
        {"user_id": user_id, "account_name": account_name, "email_id": email_id}
    )
    return {"email": result}


@router.get("/search")
async def search_emails(
    query: str,
    account_name: str = "default",
    user_id: str = "default_user",
):
    """Search emails."""
    from src.sdk.tools_core.email import email_search

    result = email_search.invoke({"user_id": user_id, "account_name": account_name, "query": query})
    return {"results": result}


@router.post("/send")
async def send_email(
    to: str,
    subject: str,
    body: str,
    account_name: str = "default",
    user_id: str = "default_user",
):
    """Send an email."""
    from src.sdk.tools_core.email import email_send

    result = email_send.invoke(
        {
            "user_id": user_id,
            "account_name": account_name,
            "to": to,
            "subject": subject,
            "body": body,
        }
    )
    return {"result": str(result)}
