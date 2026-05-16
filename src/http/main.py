"""HTTP server for Executive Assistant."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.http.routers import (
    # DISABLED: contacts, todos — pending redesign
    # contacts_router,
    companion_router,
    conversation_router,
    email_router,
    health_router,
    memories_router,
    skills_router,
    subagents_router,
    # todos_router,
    workspace_router,
    workspaces_router,
)
from src.http.routers.connectors import router as connectors_router
from src.http.routers.ws import router as ws_router

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager — SDK runtime (no LangChain agent pool needed)."""
    try:
        from src.subagent.scheduler import get_scheduler

        get_scheduler()
    except Exception:
        pass

    # Start companion scheduler if enabled
    try:
        from src.app_logging import get_logger
        from src.config import get_settings
        settings = get_settings()
        if getattr(settings.companion, "enabled", False):
            from src.sdk.companion_scheduler import (
                CompanionScheduler,
                _companion_schedulers,
            )
            scheduler = CompanionScheduler("default_user")
            await scheduler.start()
            _companion_schedulers["default_user"] = scheduler
            get_logger().info("companion.started", {}, user_id="system")
    except Exception:
        pass

    print("HTTP server ready (SDK runtime)")
    yield

    # Stop companion schedulers
    try:
        from src.app_logging import get_logger
        from src.sdk.companion_scheduler import _companion_schedulers
        for scheduler in _companion_schedulers.values():
            await scheduler.stop()
        _companion_schedulers.clear()
        get_logger().info("companion.stopped", {}, user_id="system")
    except Exception:
        pass


app = FastAPI(
    title="Executive Assistant",
    description="HTTP API for Executive Assistant",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

app.include_router(health_router)
app.include_router(companion_router)
app.include_router(conversation_router)
app.include_router(email_router)
app.include_router(memories_router)
# DISABLED: contacts, todos, email — pending redesign
# app.include_router(contacts_router)
# app.include_router(todos_router)
# app.include_router(email_router)
app.include_router(workspace_router)
app.include_router(workspaces_router)
app.include_router(skills_router)
app.include_router(subagents_router)
app.include_router(ws_router)

# ConnectKit OAuth + catalog routers (safe if connectkit not installed)
try:
    from connectkit.bridge import ConnectKitBridge
    from connectkit.oauth import create_oauth_router
    from connectkit.spec import ConnectorSpec

    def _vault_factory(user_id: str):
        bridge = ConnectKitBridge(user_id)
        return bridge.vault

    def _oauth_config(service: str) -> dict[str, str]:
        bridge = ConnectKitBridge("")
        token = bridge.vault.get_token(service) or {}
        return {
            "client_id": token.get("client_id", ""),
            "client_secret": token.get("client_secret", ""),
        }

    # Load all connector specs for OAuth routing
    from connectkit.bridge import _default_spec_dir
    oauth_specs = ConnectorSpec.from_yaml_dir(_default_spec_dir())

    oauth_router = create_oauth_router(
        specs=oauth_specs,
        vault_factory=_vault_factory,
        config=_oauth_config,
        base_url="",
    )
    app.include_router(oauth_router)
except Exception:
    pass

app.include_router(connectors_router)


def run():
    """Run the HTTP server."""
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)


if __name__ == "__main__":
    run()
