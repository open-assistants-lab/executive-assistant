"""CredentialVault — encrypted per-user token storage.

Schema:
    CREATE TABLE credentials (
        service_name TEXT PRIMARY KEY,
        auth_type TEXT NOT NULL,
        encrypted_data TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    CREATE TABLE oauth_states (
        state TEXT PRIMARY KEY,
        service_name TEXT NOT NULL,
        user_id TEXT NOT NULL,
        redirect_uri TEXT,
        created_at TEXT NOT NULL,
        expires_at TEXT NOT NULL
    );
"""

import json
import os
import secrets
import sqlite3
import threading
import warnings
from contextlib import contextmanager
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography.fernet import Fernet


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _get_or_create_key() -> bytes:
    import base64
    import hashlib

    key_str = os.environ.get("AGENT_CONNECT_VAULT_KEY")
    if key_str:
        raw = key_str.encode()
        if len(raw) == 44:
            return raw
        raw = hashlib.sha256(raw).digest()
        return base64.urlsafe_b64encode(raw)

    warnings.warn(
        "AGENT_CONNECT_VAULT_KEY not set. Using ephemeral key — "
        "tokens will be lost on restart. Set in production."
    )
    return Fernet.generate_key()


class CredentialVault:
    """Encrypted credential store (SQLite + Fernet)."""

    def __init__(self, base_path: str | Path, key: bytes | None = None):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self._db_path = str((self.base_path / "vault.db").resolve())
        self._lock = threading.RLock()
        self._fernet = Fernet(key if key else _get_or_create_key())
        self._init_db()

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Cursor, None, None]:
        with self._lock:
            conn = sqlite3.connect(self._db_path, timeout=30.0)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.row_factory = sqlite3.Row
            try:
                cursor = conn.cursor()
                yield cursor
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def _init_db(self) -> None:
        with self._connect() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS credentials (
                    service_name TEXT PRIMARY KEY,
                    auth_type TEXT NOT NULL,
                    encrypted_data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS oauth_states (
                    state TEXT PRIMARY KEY,
                    service_name TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    redirect_uri TEXT,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                )
            """)

    def _encrypt(self, data: dict) -> str:
        return self._fernet.encrypt(json.dumps(data).encode()).decode()

    def _decrypt(self, encrypted: str) -> dict:
        return json.loads(self._fernet.decrypt(encrypted.encode()).decode())

    def store_token(self, service_name: str, auth_type: str, token_data: dict) -> None:
        now = _now_iso()
        encrypted = self._encrypt(token_data)
        with self._connect() as cur:
            cur.execute(
                "INSERT OR REPLACE INTO credentials "
                "(service_name, auth_type, encrypted_data, created_at, updated_at) "
                "VALUES (?, ?, ?, COALESCE(("
                "SELECT created_at FROM credentials WHERE service_name = ?"
                "), ?), ?)",
                (service_name, auth_type, encrypted, service_name, now, now),
            )

    def get_token(self, service_name: str) -> dict | None:
        with self._connect() as cur:
            cur.execute(
                "SELECT encrypted_data FROM credentials WHERE service_name = ?",
                (service_name,),
            )
            row = cur.fetchone()
        if not row:
            return None
        return self._decrypt(row["encrypted_data"])

    def delete_token(self, service_name: str) -> bool:
        with self._connect() as cur:
            cur.execute(
                "DELETE FROM credentials WHERE service_name = ?",
                (service_name,),
            )
            return cur.rowcount > 0

    def list_connected(self) -> list[str]:
        with self._connect() as cur:
            cur.execute("SELECT service_name FROM credentials ORDER BY service_name")
            return [r["service_name"] for r in cur.fetchall()]

    def is_connected(self, service_name: str) -> bool:
        with self._connect() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM credentials WHERE service_name = ?",
                (service_name,),
            )
            return cur.fetchone()[0] > 0

    def create_oauth_state(
        self, service_name: str, user_id: str, redirect_uri: str = ""
    ) -> str:
        """Create a self-contained OAuth state token.

        The state is Fernet-encrypted JSON with service_name + user_id.
        Self-contained — any vault with the same key can validate it.
        Expires automatically via Fernet TTL (10 minutes).
        """
        payload = json.dumps({
            "service_name": service_name,
            "user_id": user_id,
            "nonce": secrets.token_urlsafe(16),
        })
        return self._fernet.encrypt(payload.encode()).decode()

    def validate_oauth_state(self, state_token: str) -> dict | None:
        """Validate a self-contained OAuth state token.

        Returns {service_name, user_id} or None if expired or invalid.
        """
        try:
            payload_json = self._fernet.decrypt(
                state_token.encode(), ttl=600
            )
            payload = json.loads(payload_json)
            return {
                "service_name": payload["service_name"],
                "user_id": payload["user_id"],
            }
        except Exception:
            return None

    def health(self) -> dict:
        try:
            with self._connect() as cur:
                cur.execute("SELECT COUNT(*) FROM credentials")
                count = cur.fetchone()[0]
            return {"status": "ok", "connected_services": count}
        except Exception as e:
            return {"status": "broken", "error": str(e)}

    def close(self) -> None:
        pass
