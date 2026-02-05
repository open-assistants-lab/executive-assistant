"""Google OAuth2 manager for Gmail, Calendar, and Contacts integration.

Implements OAuth2 flow with token refresh and encrypted storage.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

from executive_assistant.config.settings import settings

logger = logging.getLogger(__name__)


class GoogleOAuthManager:
    """Manage Google OAuth2 flow with token refresh.

    Supports:
    - Gmail API (read, send, modify)
    - Calendar API (full access)
    - Contacts (People API)
    """

    # All scopes needed for full integration
    SCOPES = [
        "https://www.googleapis.com/auth/gmail.readonly",  # Read emails
        "https://www.googleapis.com/auth/gmail.send",  # Send emails
        "https://www.googleapis.com/auth/gmail.modify",  # Manage labels
        "https://www.googleapis.com/auth/calendar",  # Full calendar access
        "https://www.googleapis.com/auth/contacts",  # Full contacts access
    ]

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
    ):
        """Initialize OAuth manager.

        Args:
            client_id: Google OAuth client ID
            client_secret: Google OAuth client secret
            redirect_uri: OAuth redirect URI (must match Google Cloud Console)
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri

    def create_authorization_url(self, state: str) -> str:
        """Create OAuth authorization URL.

        Args:
            state: Opaque state parameter (typically thread_id) for CSRF protection

        Returns:
            Authorization URL to redirect user to
        """
        # Create flow configuration
        flow_config = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "scopes": self.SCOPES,
        }

        # Create flow from config
        flow = Flow.from_client_config(flow_config)
        flow.redirect_uri = self.redirect_uri

        # Generate authorization URL
        authorization_url, _ = flow.authorization_url(
            access_type="offline",  # Get refresh token
            include_granted_scopes="true",  # Include all scopes
            state=state,  # CSRF protection
            prompt="consent",  # Force consent to get refresh token
        )

        return authorization_url

    async def exchange_code_for_tokens(self, code: str) -> Credentials:
        """Exchange authorization code for credentials.

        Args:
            code: Authorization code from Google callback

        Returns:
            Google OAuth credentials with access and refresh tokens
        """
        # Create flow configuration
        flow_config = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "scopes": self.SCOPES,
        }

        # Create flow from config
        flow = Flow.from_client_config(flow_config)
        flow.redirect_uri = self.redirect_uri

        # Exchange code for tokens
        flow.fetch_token(code=code)

        return flow.credentials

    async def save_tokens(self, thread_id: str, credentials: Credentials) -> None:
        """Save encrypted tokens to thread-scoped storage.

        Args:
            thread_id: Thread/user ID for storage path
            credentials: Google OAuth credentials to save
        """
        # Serialize credentials
        token_data = {
            "token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": credentials.scopes,
            "expiry": credentials.expiry.isoformat() if credentials.expiry else None,
        }

        # Create auth directory for thread
        from executive_assistant.config.settings import settings

        # Sanitize thread_id for filesystem
        safe_thread_id = thread_id.replace("/", "_").replace(":", "_").replace("@", "_")
        auth_dir = Path(settings.USERS_ROOT) / safe_thread_id / "auth" / "google"
        auth_dir.mkdir(parents=True, exist_ok=True)

        # Encrypt with Fernet
        fernet = Fernet(self._get_encryption_key().encode())
        encrypted = fernet.encrypt(json.dumps(token_data).encode())

        # Save to file
        cred_file = auth_dir / "credentials.json"
        with open(cred_file, "wb") as f:
            f.write(encrypted)

        logger.info(f"Saved Google OAuth tokens for {thread_id}")

    async def load_credentials(self, thread_id: str) -> Optional[Credentials]:
        """Load and refresh credentials if expired.

        Args:
            thread_id: Thread/user ID to load credentials for

        Returns:
            Google OAuth credentials, or None if not found
        """
        from executive_assistant.config.settings import settings

        # Sanitize thread_id for filesystem
        safe_thread_id = thread_id.replace("/", "_").replace(":", "_").replace("@", "_")
        auth_dir = Path(settings.USERS_ROOT) / safe_thread_id / "auth" / "google"
        cred_file = auth_dir / "credentials.json"

        if not cred_file.exists():
            logger.warning(f"No Google credentials found for {thread_id}")
            return None

        try:
            # Decrypt
            fernet = Fernet(self._get_encryption_key().encode())
            with open(cred_file, "rb") as f:
                decrypted = fernet.decrypt(f.read())

            token_data = json.loads(decrypted)

            # Create credentials object
            credentials = Credentials(
                token=token_data["token"],
                refresh_token=token_data["refresh_token"],
                token_uri=token_data["token_uri"],
                client_id=token_data["client_id"],
                client_secret=token_data["client_secret"],
                scopes=token_data["scopes"],
                expiry=datetime.fromisoformat(token_data["expiry"]) if token_data.get("expiry") else None,
            )

            # Auto-refresh if expired
            if credentials.expired:
                logger.info(f"Refreshing expired Google credentials for {thread_id}")
                credentials.refresh(Request())
                await self.save_tokens(thread_id, credentials)

            return credentials

        except Exception as e:
            logger.error(f"Error loading Google credentials for {thread_id}: {e}")
            return None

    async def is_connected(self, thread_id: str) -> bool:
        """Check if user has connected Google account.

        Args:
            thread_id: Thread/user ID to check

        Returns:
            True if credentials exist and are valid
        """
        credentials = await self.load_credentials(thread_id)
        return credentials is not None

    @staticmethod
    def _get_encryption_key() -> str:
        """Get or generate encryption key for token storage.

        Returns:
            Fernet-compatible encryption key
        """
        # Use EMAIL_ENCRYPTION_KEY from settings, or generate one
        key = getattr(settings, "EMAIL_ENCRYPTION_KEY", None)

        if not key:
            # Generate a new key (not recommended for production)
            import os

            key = Fernet.generate_key().decode()
            logger.warning(
                "EMAIL_ENCRYPTION_KEY not set. Using generated key. "
                "Add EMAIL_ENCRYPTION_KEY to your .env file for production."
            )

        # Ensure key is Fernet-compatible (32 bytes, base64-encoded)
        if isinstance(key, str):
            # If it's not a valid Fernet key, generate one
            try:
                Fernet(key.encode())
            except Exception:
                key = Fernet.generate_key().decode()

        return key


def get_google_oauth_manager() -> GoogleOAuthManager:
    """Get configured Google OAuth manager instance.

    Returns:
        GoogleOAuthManager with settings from environment

    Raises:
        ValueError: If required settings are missing
    """
    client_id = getattr(settings, "GOOGLE_CLIENT_ID", None)
    client_secret = getattr(settings, "GOOGLE_CLIENT_SECRET", None)
    redirect_uri = getattr(settings, "GOOGLE_REDIRECT_URI", None)

    if not client_id:
        raise ValueError("GOOGLE_CLIENT_ID not set in settings")

    if not client_secret:
        raise ValueError("GOOGLE_CLIENT_SECRET not set in settings")

    if not redirect_uri:
        raise ValueError("GOOGLE_REDIRECT_URI not set in settings")

    return GoogleOAuthManager(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
    )
