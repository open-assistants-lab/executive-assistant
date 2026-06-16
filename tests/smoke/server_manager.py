from __future__ import annotations

import asyncio
import logging
import os
import socket
from contextlib import asynccontextmanager
from dataclasses import dataclass

logger = logging.getLogger(__name__)


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@dataclass
class ServerConfig:
    port: int
    api_key: str | None
    model: str
    host: str = "127.0.0.1"
    startup_timeout: float = 30.0

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"


@asynccontextmanager
async def managed_server(config: ServerConfig):
    if config.port == 0:
        config.port = _find_free_port()

    env = os.environ.copy()
    if config.api_key:
        env["OLLAMA_API_KEY"] = config.api_key

    proc = await asyncio.create_subprocess_exec(
        "uvicorn",
        "src.http.main:app",
        "--host", config.host,
        "--port", str(config.port),
        "--log-level", "error",
        env=env,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )

    try:
        await _wait_for_health(config, proc)
        yield config.base_url
    finally:
        if proc.returncode is None:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=5.0)
            except TimeoutError:
                logger.warning("Server did not terminate gracefully, killing")
                proc.kill()
                await proc.wait()


async def _wait_for_health(config: ServerConfig, proc: asyncio.subprocess.Process):
    import aiohttp

    url = f"{config.base_url}/health"
    deadline = asyncio.get_event_loop().time() + config.startup_timeout

    last_error: str | None = None
    while asyncio.get_event_loop().time() < deadline:
        if proc.returncode is not None:
            raise RuntimeError(
                f"Server exited prematurely (code={proc.returncode}). "
                f"Last health-check error: {last_error}"
            )
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=2)) as resp:
                    if resp.status == 200:
                        return
                    last_error = f"HTTP {resp.status}"
        except (TimeoutError, aiohttp.ClientError) as e:
            last_error = str(e)

        await asyncio.sleep(0.5)

    raise TimeoutError(
        f"Server did not become healthy within {config.startup_timeout}s. "
        f"Last error: {last_error}"
    )
