"""Universal OAuth 2.0 endpoints — one router for every connector.

Flow:
    1. GET /auth/login?service=google-workspace&user_id=alice
       -> Load spec, build authorize URL, redirect to provider
    2. Provider redirects to GET /auth/callback?code=...&state=...
       -> Exchange code for tokens, store in vault, return success

Supports PKCE (RFC 7636) for public clients (no client_secret).
"""

import base64
import hashlib
import json
import secrets
import shutil
import subprocess
from collections.abc import Callable
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from starlette.responses import RedirectResponse

from connectkit.spec import AuthType, ConnectorSpec
from connectkit.vault import CredentialVault

ConfigProvider = Callable[[str], dict[str, str]]
VaultFactory = Callable[[str], CredentialVault]


def _generate_code_verifier() -> str:
    token = secrets.token_bytes(32)
    return base64.urlsafe_b64encode(token).rstrip(b"=").decode()


def _derive_code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def create_oauth_router(
    specs: list[ConnectorSpec],
    vault_factory: VaultFactory,
    config: ConfigProvider,
    base_url: str = "",
    on_connect: Callable[[str], Any] | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/auth", tags=["auth"])

    oauth_services = {
        s.name: s
        for s in specs
        if s.auth.type == AuthType.OAUTH2 and s.auth.oauth2 is not None
    }

    @router.get("/login")
    async def oauth_login(
        request: Request,
        service: str = Query(..., description="Connector name (e.g. google-workspace)"),
        user_id: str = Query(..., description="User ID (e.g. alice@corp.com)"),
        client_secret: str | None = Query(None, description="Client secret (required by some providers even with PKCE)"),
    ):
        spec = oauth_services.get(service)
        if not spec:
            raise HTTPException(400, f"Unknown or non-OAuth service: {service}")

        oauth = spec.auth.oauth2
        assert oauth is not None

        if base_url:
            redirect_uri = f"{base_url.rstrip('/')}/auth/callback"
        else:
            redirect_uri = str(request.base_url) + "auth/callback"

        cfg = config(spec.name)
        client_id = cfg.get("client_id", "")

        vault = vault_factory(user_id)

        code_verifier: str | None = None
        code_challenge: str | None = None
        extra: dict | None = None
        if oauth.pkce:
            code_verifier = _generate_code_verifier()
            code_challenge = _derive_code_challenge(code_verifier)
            extra = {
                "code_verifier": code_verifier,
                "redirect_uri": redirect_uri,
            }
            # Some providers (Google) require client_secret even with PKCE
            if client_secret:
                extra["client_secret"] = client_secret

        state = vault.create_oauth_state(service, user_id, extra=extra)

        params: dict[str, str] = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(oauth.scopes),
            "state": state,
        }
        if oauth.pkce and code_challenge:
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = "S256"
        params.update(oauth.extra_params)

        url = f"{oauth.authorize_url}?{urlencode(params)}"
        return RedirectResponse(url, status_code=302)

    @router.get("/callback")
    async def oauth_callback(
        code: str | None = Query(None, description="Authorization code from provider"),
        state: str | None = Query(None, description="OAuth state parameter"),
        service: str = Query("", description="Connector name override"),
        error: str | None = Query(None, description="OAuth error from provider"),
        error_description: str | None = Query(None),
    ):
        if error:
            raise HTTPException(
                400, f"OAuth provider returned error: {error}"
                + (f" — {error_description}" if error_description else "")
            )

        if not code or not state:
            raise HTTPException(400, "Missing code or state parameter")

        vault = vault_factory("")
        state_data = vault.validate_oauth_state(state)
        if not state_data:
            raise HTTPException(400, "Invalid or expired OAuth state")

        service_name = state_data["service_name"]
        user_id = state_data["user_id"]

        spec = oauth_services.get(service_name)
        if not spec:
            raise HTTPException(400, f"Unknown service: {service_name}")

        oauth = spec.auth.oauth2
        assert oauth is not None

        cfg = config(service_name)
        client_id = cfg.get("client_id", "")

        extra = state_data.get("extra") or {}
        redirect_uri = extra.get("redirect_uri", "/auth/callback")

        token_body: dict[str, str] = {
            "client_id": client_id,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        }

        # Always include client_secret if available (Google requires it even with PKCE)
        # Check: vault config → OAuth state extra (from login query param) → empty
        client_secret = cfg.get("client_secret") or extra.get("client_secret") or ""
        if client_secret:
            token_body["client_secret"] = client_secret

        if oauth.pkce:
            code_verifier = extra.get("code_verifier")
            if not code_verifier:
                raise HTTPException(400, "PKCE state missing code_verifier")
            token_body["code_verifier"] = code_verifier

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                oauth.token_url,
                data=token_body,
                headers={"Accept": "application/json"},
            )

            if resp.status_code >= 400:
                detail = resp.text[:500]
                raise HTTPException(
                    502, f"Token exchange failed (HTTP {resp.status_code}): {detail}"
                )

            try:
                token_data = resp.json()
            except Exception:
                raise HTTPException(502, f"Token exchange returned non-JSON: {resp.text[:500]}")

            if "access_token" not in token_data:
                raise HTTPException(
                    502, f"Token response missing access_token: {json.dumps(token_data)[:500]}"
                )

        from datetime import UTC, datetime

        token_data["_obtained_at"] = datetime.now(UTC).isoformat()
        token_data["_scopes"] = oauth.scopes

        user_vault = vault_factory(user_id)
        user_vault.store_token(service_name, "oauth2", token_data)

        # Auto-install CLI if connector uses one and it's not found
        for source in spec.get_tool_sources():
            if hasattr(source, "command") and not shutil.which(source.command):
                install_cmd = getattr(source, "install", "")
                if install_cmd:
                    logger = __import__("logging").getLogger("connectkit.oauth")
                    logger.info(
                        "auto_install_cli",
                        {"service": service_name, "command": source.command, "install": install_cmd},
                    )
                    try:
                        subprocess.run(
                            install_cmd,
                            shell=True,
                            capture_output=True,
                            text=True,
                            timeout=120,
                        )
                    except Exception as e:
                        logger.warning(
                            "auto_install_cli_failed",
                            {"service": service_name, "error": str(e)},
                        )

        if on_connect:
            on_connect(user_id)

        return {
            "status": "connected",
            "service": service_name,
            "scopes": oauth.scopes,
        }

    @router.get("/status")
    async def auth_status(user_id: str = Query(...)):
        vault = vault_factory(user_id)
        connected = vault.list_connected()
        return {
            "connected": [
                {"service": s, "has_token": True} for s in connected
            ]
        }

    return router
