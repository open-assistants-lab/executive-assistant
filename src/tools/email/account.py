"""Email account management tools."""

import uuid
from pathlib import Path
from typing import Any

import yaml
from langchain_core.tools import tool

from src.app_logging import get_logger
from src.tools.vault.store import get_vault

logger = get_logger()


def _get_accounts_path(user_id: str) -> Path:
    """Get accounts.yaml path for user."""
    base_dir = Path(f"data/users/{user_id}/email")
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir / "accounts.yaml"


def _load_accounts(user_id: str) -> dict[str, dict]:
    """Load accounts from YAML."""
    path = _get_accounts_path(user_id)
    if not path.exists():
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


def _save_accounts(user_id: str, accounts: dict[str, Any]) -> None:
    """Save accounts to YAML."""
    path = _get_accounts_path(user_id)
    with open(path, "w") as f:
        yaml.dump(accounts, f, default_flow_style=False)


@tool
def email_connect(
    credential_name: str,
    account_name: str | None = None,
    folders: list[str] | None = None,
    user_id: str = "default",
) -> str:
    """Connect an email account.

    Connects to email using credentials from vault and verifies connection.
    Fetches folder list and prepares for sync.

    Args:
        credential_name: Name of credential in vault (e.g., 'work-gmail')
        account_name: Friendly name for this account (default: use credential name)
        folders: Folders to sync (default: INBOX, SENT)
        user_id: User identifier (default: default)

    Returns:
        Success or error message
    """
    vault = get_vault(user_id)

    if not vault.is_unlocked():
        return "Error: Vault is locked. Use vault_unlock first."

    # Get credential
    cred = vault.get_credential(credential_name)
    if not cred:
        return f"Error: Credential '{credential_name}' not found. Use credential_list to see available."

    # Test IMAP connection
    try:
        from imap_tools import MailBox

        with MailBox(cred.imap_host, cred.imap_port).login(
            cred.username, cred.password, initial_folder=folders[0] if folders else "INBOX"
        ) as mailbox:
            # Get folder list
            folder_list = [f.name for f in mailbox.folder.list()]
            logger.info(
                "email.connect_success", {"account": credential_name, "folders": folder_list}
            )

    except Exception as e:
        logger.error("email.connect_failed", {"account": credential_name, "error": str(e)})
        return f"Error: Failed to connect to email: {e}"

    # Save account
    account_id = str(uuid.uuid4())
    account = {
        "id": account_id,
        "name": account_name or credential_name,
        "credential_name": credential_name,
        "email": cred.email,
        "provider": cred.provider,
        "folders": folders or ["INBOX", "SENT"],
        "status": "connected",
    }

    accounts = _load_accounts(user_id)
    accounts[account_id] = account
    _save_accounts(user_id, accounts)

    return f"""Connected successfully!

Account: {account["name"]}
Email: {cred.email}
Provider: {cred.provider}
Folders: {account["folders"]}

Use email_list to fetch emails."""


@tool
def email_disconnect(account_name: str, user_id: str = "default") -> str:
    """Disconnect and remove an email account.

    Removes the account and its local store from storage.

    Args:
        account_name: Account name to disconnect
        user_id: User identifier (default: default)

    Returns:
        Success or error message
    """
    accounts = _load_accounts(user_id)

    # Find account by name
    account_id = None
    for acc_id, acc in accounts.items():
        if acc["name"] == account_name:
            account_id = acc_id
            break

    if not account_id:
        return f"Error: Account '{account_name}' not found. Use email_accounts to see available."

    # Remove account
    del accounts[account_id]
    _save_accounts(user_id, accounts)

    logger.info("email.disconnected", {"account": account_name, "user_id": user_id})
    return f"Account '{account_name}' disconnected and removed."


@tool
def email_accounts(user_id: str = "default") -> str:
    """List connected email accounts.

    Args:
        user_id: User identifier (default: default)

    Returns:
        List of connected accounts
    """
    accounts = _load_accounts(user_id)

    if not accounts:
        return "No email accounts connected. Use email_connect to add one."

    output = "Connected email accounts:\n"
    for acc in accounts.values():
        output += f"- {acc['name']}: {acc['email']} ({acc['provider']})\n"
        output += f"  Status: {acc['status']}, Folders: {acc.get('folders', [])}\n"

    return output
