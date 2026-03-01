"""Encrypted credential storage."""

import base64
import json
import os
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from src.app_logging import get_logger
from src.tools.vault.models import Credential, VaultConfig

logger = get_logger()

DEFAULT_ITERATIONS = 100000


def _get_vault_path(user_id: str) -> Path:
    """Get vault file path for user."""
    base_dir = Path(f"data/users/{user_id}")
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir / "vault.enc"


def _derive_key(password: str, salt: bytes, iterations: int = DEFAULT_ITERATIONS) -> bytes:
    """Derive encryption key from password using PBKDF2."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=iterations,
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))


class Vault:
    """Encrypted credential vault."""

    def __init__(self, user_id: str, master_password: str | None = None):
        self.user_id = user_id
        self.vault_path = _get_vault_path(user_id)
        self._fernet: Fernet | None = None
        self._credentials: dict[str, Credential] = {}

        if master_password:
            self.unlock(master_password)

    def _load_vault(self) -> VaultConfig | None:
        """Load vault config from file."""
        if not self.vault_path.exists():
            return None

        try:
            with open(self.vault_path) as f:
                data = json.load(f)
            return VaultConfig(**data)
        except (json.JSONDecodeError, KeyError):
            return None

    def _save_vault(self, config: VaultConfig) -> None:
        """Save vault config to file."""
        with open(self.vault_path, "w") as f:
            json.dump(config.model_dump(), f, indent=2)

    def unlock(self, master_password: str) -> bool:
        """Unlock vault with master password."""
        config = self._load_vault()

        if config is None:
            # New vault - create with password
            salt = os.urandom(16)
            key = _derive_key(master_password, salt)
            self._fernet = Fernet(key)
            self._credentials = {}
            self._save_vault(
                VaultConfig(
                    salt=base64.b64encode(salt).decode(),
                    iterations=DEFAULT_ITERATIONS,
                    encrypted_data=self._encrypt({}),
                )
            )
            logger.info("vault.created", user_id=self.user_id)
            return True

        # Existing vault - try to decrypt
        try:
            salt = base64.b64decode(config.salt)
            key = _derive_key(master_password, salt, config.iterations)
            fernet = Fernet(key)  # Create fernet but don't set it yet
            decrypted = fernet.decrypt(config.encrypted_data.encode())
            # Only set fernet and credentials if decryption succeeds
            self._fernet = fernet
            self._credentials = {}
            for k, v in json.loads(decrypted).items():
                self._credentials[k] = Credential(**v) if isinstance(v, dict) else v
            logger.info("vault.unlocked", user_id=self.user_id)
            return True
        except Exception:
            logger.warning("vault.unlock_failed", user_id=self.user_id)
            return False

    def _encrypt(self, data: dict[str, Any]) -> str:
        """Encrypt data."""
        if not self._fernet:
            raise ValueError("Vault is locked")
        return self._fernet.encrypt(json.dumps(data).encode()).decode()

    def _decrypt(self, encrypted: str) -> dict[str, Any]:
        """Decrypt data."""
        if not self._fernet:
            raise ValueError("Vault is locked")
        return json.loads(self._fernet.decrypt(encrypted.encode()))

    def is_unlocked(self) -> bool:
        """Check if vault is unlocked."""
        return self._fernet is not None

    def lock(self) -> None:
        """Lock vault."""
        self._fernet = None
        self._credentials = {}
        logger.info("vault.locked", user_id=self.user_id)

    def add_credential(self, credential: Credential) -> bool:
        """Add or update a credential."""
        if not self.is_unlocked():
            return False
        self._credentials[credential.name] = credential
        self._save()
        return True

    def get_credential(self, name: str) -> Credential | None:
        """Get credential by name."""
        return self._credentials.get(name)

    def list_credentials(self) -> list[str]:
        """List credential names only."""
        return list(self._credentials.keys())

    def delete_credential(self, name: str) -> bool:
        """Delete a credential."""
        if name in self._credentials:
            del self._credentials[name]
            self._save()
            return True
        return False

    def _save(self) -> None:
        """Save vault to file."""
        if not self._fernet:
            raise ValueError("Vault is locked")
        config = self._load_vault()
        if config is None:
            raise ValueError("Vault not initialized")
        # Convert Credential objects to dicts for JSON serialization
        credentials_data = {}
        for k, v in self._credentials.items():
            if hasattr(v, "model_dump"):
                credentials_data[k] = v.model_dump()
            else:
                credentials_data[k] = v
        config.encrypted_data = self._encrypt(credentials_data)
        self._save_vault(config)


# Session storage for unlocked vaults
_vaults: dict[str, Vault] = {}


def get_vault(user_id: str) -> Vault:
    """Get vault for user."""
    if user_id not in _vaults:
        _vaults[user_id] = Vault(user_id)
    return _vaults[user_id]


def unlock_vault(user_id: str, master_password: str) -> bool:
    """Unlock vault for user."""
    vault = get_vault(user_id)
    return vault.unlock(master_password)


def lock_vault(user_id: str) -> None:
    """Lock vault for user."""
    vault = get_vault(user_id)
    vault.lock()
