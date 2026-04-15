"""HTTP server for Executive Assistant."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI

from src.http.routers import (
    # DISABLED: contacts, email, todos — pending redesign
    # contacts_router,
    conversation_router,
    # email_router,
    health_router,
    memories_router,
    skills_router,
    subagents_router,
    # todos_router,
    workspace_router,
)
from src.http.routers.ws import router as ws_router

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager — SDK runtime (no LangChain agent pool needed)."""
    # DISABLED: email sync — pending redesign
    # try:
    #     from src.sdk.tools_core.email_sync import start_interval_sync, stop_interval_sync
    #     await start_interval_sync()
    # except Exception:
    #     pass

    try:
        from src.subagent.scheduler import get_scheduler

        get_scheduler()
    except Exception:
        pass

    print("HTTP server ready (SDK runtime)")
    yield

    # DISABLED: email sync — pending redesign
    # try:
    #     from src.sdk.tools_core.email_sync import stop_interval_sync
    #     await stop_interval_sync()
    # except Exception:
    #     pass


app = FastAPI(
    title="Executive Assistant",
    description="HTTP API for Executive Assistant",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(conversation_router)
app.include_router(memories_router)
# DISABLED: contacts, todos, email — pending redesign
# app.include_router(contacts_router)
# app.include_router(todos_router)
# app.include_router(email_router)
app.include_router(workspace_router)
app.include_router(skills_router)
app.include_router(subagents_router)
app.include_router(ws_router)


def run():
    """Run the HTTP server."""
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)


if __name__ == "__main__":
    run()
