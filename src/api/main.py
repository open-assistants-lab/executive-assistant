from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.config.settings import get_settings
from src.llm.errors import LLMError
from src.storage.postgres import get_postgres_connection

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True  # Override any existing configuration
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Application lifespan manager."""
    settings = get_settings()

    postgres = get_postgres_connection(settings.database_url)
    await postgres.connect()

    yield

    await postgres.disconnect()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    # app.debug is admin-configured via YAML; DEBUG log level also enables debug mode.
    debug_mode = settings.app.debug or settings.log_level == "DEBUG"

    app = FastAPI(
        title="Executive Assistant API",
        description="Enterprise-ready AI assistant with memory, tools, and multi-LLM support",
        version="0.1.0",
        debug=debug_mode,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(LLMError)
    async def llm_error_handler(request: Request, exc: LLMError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={
                "error": "llm_error",
                "message": str(exc),
                "provider": exc.provider,
            },
        )

    from src.api.routes import chat, commands, health

    app.include_router(health.router, prefix="/api/v1", tags=["health"])
    app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
    app.include_router(commands.router, prefix="/api/v1", tags=["commands"])

    return app


app = create_app()


def run_server() -> None:
    """Run the API server."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "src.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.app.hot_reload,
    )


if __name__ == "__main__":
    run_server()
