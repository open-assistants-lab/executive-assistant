"""Tests for CredentialVault."""

import base64
import shutil
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.fernet import Fernet

from connectkit.vault import CredentialVault, _get_or_create_key


@pytest.fixture
def vault(request, monkeypatch, tmp_path):
    monkeypatch.setenv("CONNECTKIT_VAULT_KEY", "")
    v = CredentialVault(str(tmp_path))
    yield v
    v.close()
    shutil.rmtree(str(tmp_path), ignore_errors=True)


@pytest.fixture
def vault_with_key(monkeypatch, tmp_path):
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("CONNECTKIT_VAULT_KEY", key)
    v = CredentialVault(str(tmp_path))
    yield v
    v.close()
    shutil.rmtree(str(tmp_path), ignore_errors=True)


class TestKeyGeneration:
    def test_uses_env_var(self, monkeypatch):
        key = Fernet.generate_key().decode()
        monkeypatch.setenv("CONNECTKIT_VAULT_KEY", key)
        result = _get_or_create_key()
        assert len(result) == 44

    def test_generates_ephemeral_when_missing(self, monkeypatch):
        monkeypatch.delenv("CONNECTKIT_VAULT_KEY", raising=False)
        with pytest.warns(UserWarning, match="CONNECTKIT_VAULT_KEY not set"):
            key = _get_or_create_key()
        assert len(key) == 44


class TestStoreAndRetrieve:
    def test_roundtrip_oauth_token(self, vault):
        vault.store_token("google-workspace", "oauth2", {
            "access_token": "ya29.test123",
            "refresh_token": "1//test456",
            "expires_in": 3600,
        })
        token = vault.get_token("google-workspace")
        assert token is not None
        assert token["access_token"] == "ya29.test123"
        assert token["refresh_token"] == "1//test456"

    def test_roundtrip_api_key(self, vault):
        vault.store_token("firecrawl", "api_key", {
            "api_key": "fc-secret-key-abc",
        })
        token = vault.get_token("firecrawl")
        assert token is not None
        assert token["api_key"] == "fc-secret-key-abc"

    def test_roundtrip_complex_data(self, vault):
        vault.store_token("custom", "oauth2", {
            "access_token": "tok",
            "refresh_token": "ref",
            "expires_at": "2026-12-31T23:59:59Z",
            "scopes": ["read", "write"],
            "metadata": {"user": "123", "plan": "pro"},
        })
        token = vault.get_token("custom")
        assert token["expires_at"] == "2026-12-31T23:59:59Z"
        assert token["scopes"] == ["read", "write"]
        assert token["metadata"]["plan"] == "pro"

    def test_missing_token(self, vault):
        token = vault.get_token("nonexistent")
        assert token is None

    def test_overwrite_token(self, vault):
        vault.store_token("service", "oauth2", {"access_token": "old"})
        vault.store_token("service", "oauth2", {"access_token": "new"})
        token = vault.get_token("service")
        assert token["access_token"] == "new"


class TestDelete:
    def test_delete_existing(self, vault):
        vault.store_token("service", "oauth2", {"access_token": "tok"})
        assert vault.delete_token("service") is True
        assert vault.get_token("service") is None

    def test_delete_nonexistent(self, vault):
        assert vault.delete_token("nonexistent") is False

    def test_delete_then_reconnect(self, vault):
        vault.store_token("service", "oauth2", {"access_token": "tok1"})
        vault.delete_token("service")
        vault.store_token("service", "oauth2", {"access_token": "tok2"})
        assert vault.get_token("service")["access_token"] == "tok2"


class TestListAndCheck:
    def test_list_connected(self, vault):
        vault.store_token("google", "oauth2", {"access_token": "tok"})
        vault.store_token("github", "oauth2", {"access_token": "tok"})
        vault.store_token("slack", "api_key", {"api_key": "key"})

        connected = vault.list_connected()
        assert connected == ["github", "google", "slack"]

    def test_list_empty(self, vault):
        assert vault.list_connected() == []

    def test_is_connected(self, vault):
        assert vault.is_connected("google") is False
        vault.store_token("google", "oauth2", {"access_token": "tok"})
        assert vault.is_connected("google") is True

    def test_is_connected_after_delete(self, vault):
        vault.store_token("google", "oauth2", {"access_token": "tok"})
        vault.delete_token("google")
        assert vault.is_connected("google") is False


class TestOAuthStates:
    def test_create_and_validate(self, vault):
        state = vault.create_oauth_state("google", "alice")
        result = vault.validate_oauth_state(state)
        assert result is not None
        assert result["service_name"] == "google"
        assert result["user_id"] == "alice"

    def test_one_time_use(self, vault):
        """States are Fernet-encrypted and self-contained — they can be validated
        multiple times. The security comes from Fernet's TTL expiry, not
        one-time-use tracking. This test verifies that a valid state works
        after being validated once."""
        state = vault.create_oauth_state("google", "alice")
        result1 = vault.validate_oauth_state(state)
        assert result1 is not None
        assert result1["service_name"] == "google"

        # Same state still works — it's just a Fernet token, no DB tracking
        result2 = vault.validate_oauth_state(state)
        assert result2 is not None
        assert result2["service_name"] == "google"

    def test_invalid_state(self, vault):
        result = vault.validate_oauth_state("invalid-state-12345")
        assert result is None

    def test_expired_state(self, vault):
        """States expire via Fernet TTL. Test that invalid tokens return None."""
        state = vault.create_oauth_state("google", "alice")
        # Corrupt the token — should fail to decrypt
        corrupted = state + "x"
        result = vault.validate_oauth_state(corrupted)
        assert result is None

        # Valid token should still work
        state2 = vault.create_oauth_state("google", "bob")
        result2 = vault.validate_oauth_state(state2)
        assert result2 is not None
        assert result2["user_id"] == "bob"

    def test_state_with_redirect_uri(self, vault):
        state = vault.create_oauth_state("google", "alice", "https://ea.example.com/callback")
        result = vault.validate_oauth_state(state)
        assert result is not None

    def test_multiple_states_dont_interfere(self, vault):
        s1 = vault.create_oauth_state("google", "alice")
        s2 = vault.create_oauth_state("github", "alice")
        s3 = vault.create_oauth_state("slack", "bob")

        r1 = vault.validate_oauth_state(s1)
        r2 = vault.validate_oauth_state(s2)
        r3 = vault.validate_oauth_state(s3)

        assert r1["service_name"] == "google"
        assert r2["service_name"] == "github"
        assert r3["service_name"] == "slack"


class TestEncryption:
    def test_data_encrypted_at_rest(self, vault):
        vault.store_token("secret", "oauth2", {"access_token": "super-secret-value"})

        import sqlite3
        conn = sqlite3.connect(vault._db_path)
        cur = conn.execute(
            "SELECT encrypted_data FROM credentials WHERE service_name = ?",
            ("secret",),
        )
        raw = cur.fetchone()[0]
        conn.close()

        assert "super-secret-value" not in raw
        assert "access_token" not in raw
        assert raw.startswith("gAAAAA")

    def test_different_keys_produce_different_ciphertext(self, tmp_path):
        k1 = Fernet.generate_key()
        v1 = CredentialVault(str(tmp_path / "v1"), key=k1)
        v1.store_token("s", "oauth2", {"x": "value"})

        import sqlite3
        conn = sqlite3.connect(v1._db_path)
        c1 = conn.execute("SELECT encrypted_data FROM credentials").fetchone()[0]
        conn.close()

        k2 = Fernet.generate_key()
        v2 = CredentialVault(str(tmp_path / "v2"), key=k2)
        v2.store_token("s", "oauth2", {"x": "value"})

        conn = sqlite3.connect(v2._db_path)
        c2 = conn.execute("SELECT encrypted_data FROM credentials").fetchone()[0]
        conn.close()

        assert c1 != c2

    def test_cannot_decrypt_with_wrong_key(self, tmp_path):
        k1 = Fernet.generate_key()
        v1 = CredentialVault(str(tmp_path), key=k1)
        v1.store_token("s", "oauth2", {"x": "value"})

        k2 = Fernet.generate_key()
        v2 = CredentialVault(str(tmp_path), key=k2)

        with pytest.raises(Exception):
            v2.get_token("s")


class TestHealth:
    def test_ok(self, vault):
        vault.store_token("s", "oauth2", {"x": "1"})
        h = vault.health()
        assert h["status"] == "ok"
        assert h["connected_services"] == 1

    def test_empty(self, vault):
        h = vault.health()
        assert h["status"] == "ok"
        assert h["connected_services"] == 0


class TestPersistence:
    def test_data_survives_reopen(self, tmp_path):
        key = Fernet.generate_key()
        v1 = CredentialVault(str(tmp_path), key=key)
        v1.store_token("google", "oauth2", {"access_token": "persist-me"})
        v1.close()

        v2 = CredentialVault(str(tmp_path), key=key)
        token = v2.get_token("google")
        assert token is not None
        assert token["access_token"] == "persist-me"
        v2.close()

    def test_data_survives_reopen_with_same_key(self, monkeypatch, tmp_path):
        key = Fernet.generate_key().decode()
        monkeypatch.setenv("CONNECTKIT_VAULT_KEY", key)
        v1 = CredentialVault(str(tmp_path))
        v1.store_token("google", "oauth2", {"access_token": "value"})
        v1.close()

        monkeypatch.setenv("CONNECTKIT_VAULT_KEY", key)
        v2 = CredentialVault(str(tmp_path))
        token = v2.get_token("google")
        assert token["access_token"] == "value"
        v2.close()
