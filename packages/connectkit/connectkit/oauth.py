"""Universal OAuth 2.0 endpoints — one router for every connector.

Flow:
    1. GET /auth/login?service=google-workspace&user_id=alice
       -> Load spec, build authorize URL, redirect to Google
    2. Google redirects to GET /auth/callback?code=...&state=...
       -> Exchange code for tokens, store in vault, return success

The connector spec (ConnectorSpec) drives everything:
    - authorize_url, token_url, scopes, extra_params from the spec
    - client_id, client_secret from deployment config (env vars or config dict)
    - tokens stored in CredentialVault per user
"""

import json
from typing import Callable
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Query
from starlette.responses import RedirectResponse

from connectkit.spec import AuthType, ConnectorSpec
from connectkit.vault import CredentialVault

ConfigProvider = Callable[[str], dict[str, str]]
VaultFactory = Callable[[str], CredentialVault]


def create_oauth_router(
    specs: list[ConnectorSpec],
    vault_factory: VaultFactory,
    config: ConfigProvider,
    base_url: str = "",
) -> APIRouter:
    router = APIRouter(prefix="/auth", tags=["auth"])

    oauth_services = {
        s.name: s
        for s in specs
        if s.auth.type == AuthType.OAUTH2 and s.auth.oauth2 is not None
    }

    def _redirect_uri(base: str, service: str) -> str:
        if base:
            return f"{base.rstrip('/')}/auth/callback?service={service}"
        return f"/auth/callback?service={service}"

    def _build_authorize_url(spec: ConnectorSpec, state: str) -> str:
        oauth = spec.auth.oauth2
        assert oauth is not None
        cfg = config(spec.name)
        params = {
            "client_id": cfg["client_id"],
            "redirect_uri": _redirect_uri(base_url, spec.name),
            "response_type": "code",
            "scope": " ".join(oauth.scopes),
            "state": state,
            **oauth.extra_params,
        }
        return f"{oauth.authorize_url}?{urlencode(params)}"

    @router.get("/login")
    async def oauth_login(
        service: str = Query(..., description="Connector name (e.g. google-workspace)"),
        user_id: str = Query(..., description="User ID (e.g. alice@corp.com)"),
    ):
        spec = oauth_services.get(service)
        if not spec:
            raise HTTPException(400, f"Unknown or non-OAuth service: {service}")

        vault = vault_factory(user_id)
        state = vault.create_oauth_state(service, user_id)
        url = _build_authorize_url(spec, state)
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

        # The state token is Fernet-encrypted and self-contained — it includes
        # service_name + user_id. Any vault with the same key can decrypt it.
        # We use a temp vault instance just for decryption.
        vault = vault_factory("")
        state_data = vault.validate_oauth_state(state)
        if not state_data:
            raise HTTPException(400, "Invalid or expired OAuth state")

        service_name = state_data["service_name"]
        user_id = state_data["user_id"]

        spec = oauth_services.get(service_name)
        if not spec:
            raise HTTPException(400, f"Unknown service: {service_name}")

        cfg = config(service_name)
        oauth = spec.auth.oauth2
        assert oauth is not None

        redirect_uri = _redirect_uri(base_url, service_name)

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                oauth.token_url,
                data={
                    "client_id": cfg["client_id"],
                    "client_secret": cfg["client_secret"],
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                },
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
