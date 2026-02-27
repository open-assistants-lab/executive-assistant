"""Vault tools for secure credential storage."""

from langchain_core.tools import tool

from src.app_logging import get_logger
from src.tools.vault.models import Credential
from src.tools.vault.store import get_vault, lock_vault, unlock_vault

logger = get_logger()


def _get_user_vault(user_id: str):
    """Get vault for user."""
    return get_vault(user_id)


@tool
def vault_unlock(master_password: str, user_id: str) -> str:
    """Unlock vault with master password.

    Required before adding or retrieving credentials.
    Vault locks automatically after session ends.

    For NEW users: This will CREATE a new vault with the password you provide.
    For EXISTING users: Enter your existing master password.

    Args:
        master_password: Your master password to unlock (or create) vault
        user_id: User ID from the conversation (REQUIRED - must be provided)

    Returns:
        Success or error message
    """
    vault = _get_user_vault(user_id)

    # Check if vault exists
    if vault._load_vault() is None:
        # New vault - create with password
        success = vault.unlock(master_password)
        if success:
            return "Vault created and unlocked! You can now add credentials with credential_add."
        return "Failed to create vault."

    # Existing vault - unlock
    success = unlock_vault(user_id, master_password)
    if success:
        return "Vault unlocked successfully. You can now add or access credentials."
    return "Failed to unlock vault. Incorrect password."


@tool
def vault_lock(user_id: str) -> str:
    """Lock vault and clear session credentials.

    Args:
        user_id: User ID from the conversation (REQUIRED)

    Returns:
        Success message
    """
    lock_vault(user_id)
    return "Vault locked."


@tool
def vault_is_unlocked(user_id: str) -> str:
    """Check if vault is unlocked or if it's a new user.

    Args:
        user_id: User ID from the conversation (REQUIRED)

    Returns:
        Vault status - if new user, prompts to create vault
    """
    if not user_id:
        return "Error: user_id is required."
    vault = _get_user_vault(user_id)

    # Check if vault exists
    if vault._load_vault() is None:
        return """🔐 **No vault found** - This is your first time!

To get started, please create a master password for your vault:

**vault_unlock** with your chosen password

This password will be used to encrypt and protect your stored credentials (like email login details). Make sure to remember it - it cannot be recovered if lost!"""

    if vault.is_unlocked():
        return "Vault is unlocked."
    return "Vault is locked. Use vault_unlock with your master password to unlock it."


@tool
def credential_add(
    name: str,
    provider: str,
    email: str,
    imap_host: str,
    smtp_host: str,
    username: str,
    password: str,
    imap_port: int = 993,
    smtp_port: int = 587,
    use_ssl: bool = True,
    use_tls: bool = True,
    user_id: str = "",
) -> str:
    """Add email account credentials to vault.

    Args:
        name: Friendly name (e.g., 'work-gmail', 'personal-outlook')
        provider: Provider type (gmail, outlook, yahoo, office365, imap)
        email: Email address
        imap_host: IMAP server (e.g., imap.gmail.com)
        smtp_host: SMTP server (e.g., smtp.gmail.com)
        username: IMAP/SMTP username (usually email address)
        password: Password or app password
        imap_port: IMAP port (default: 993)
        smtp_port: SMTP port (default: 587)
        use_ssl: Use SSL for IMAP (default: True)
        use_tls: Use TLS for SMTP (default: True)
        user_id: User ID from the conversation (REQUIRED)

    Returns:
        Success or error message
    """
    if not user_id:
        return "Error: user_id is required."
    vault = _get_user_vault(user_id)

    if not vault.is_unlocked():
        return "Error: Vault is locked. Use vault_unlock first."

    credential = Credential(
        name=name,
        provider=provider,
        email=email,
        imap_host=imap_host,
        imap_port=imap_port,
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        username=username,
        password=password,
        use_ssl=use_ssl,
        use_tls=use_tls,
    )

    if vault.add_credential(credential):
        logger.info("credential_added", {"name": name, "provider": provider, "user_id": user_id})
        return f"Credential '{name}' added successfully."
    return "Error: Failed to add credential."


@tool
def credential_list(user_id: str = "") -> str:
    """List stored credential names.

    Note: Does NOT show passwords or sensitive data.

    Args:
        user_id: User ID from the conversation (REQUIRED)

    Returns:
        List of credential names with their email addresses
    """
    if not user_id:
        return "Error: user_id is required."
    vault = _get_user_vault(user_id)

    if not vault.is_unlocked():
        return "Error: Vault is locked. Use vault_unlock first."

    credentials = vault.list_credentials()
    if not credentials:
        return "No credentials stored. Use credential_add to add one."

    output = "Stored credentials:\n"
    for name in credentials:
        cred = vault.get_credential(name)
        if cred:
            output += f"- {name}: {cred.email} ({cred.provider})\n"
    return output


@tool
def credential_get(name: str, user_id: str = "") -> str:
    """Get credential details (for tool use).

    Args:
        name: Credential name
        user_id: User ID from the conversation (REQUIRED)

    Returns:
        Credential details or error
    """
    if not user_id:
        return "Error: user_id is required."
    vault = _get_user_vault(user_id)

    if not vault.is_unlocked():
        return "Error: Vault is locked. Use vault_unlock first."

    cred = vault.get_credential(name)
    if not cred:
        return f"Credential '{name}' not found."

    return f"""Credential: {name}
Email: {cred.email}
Provider: {cred.provider}
IMAP: {cred.imap_host}:{cred.imap_port}
SMTP: {cred.smtp_host}:{cred.smtp_port}
Username: {cred.username}"""


@tool
def credential_delete(name: str, user_id: str = "") -> str:
    """Delete a stored credential.

    Args:
        name: Credential name to delete
        user_id: User ID from the conversation (REQUIRED)

    Returns:
        Success or error message
    """
    if not user_id:
        return "Error: user_id is required."
    vault = _get_user_vault(user_id)

    if not vault.is_unlocked():
        return "Error: Vault is locked. Use vault_unlock first."

    if vault.delete_credential(name):
        logger.info("credential_deleted", {"name": name, "user_id": user_id})
        return f"Credential '{name}' deleted."
    return f"Credential '{name}' not found."
