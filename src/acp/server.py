from __future__ import annotations

import asyncio
import sys

from deepagents_acp import AgentServerACP

from src.agent import create_ea_agent
from src.config.settings import get_settings


async def run_acp_server() -> None:
    """Run the ACP server for IDE integration."""
    settings = get_settings()

    async with create_ea_agent(settings) as agent:
        server = AgentServerACP(agent)
        await server.run_stdio()


def main() -> None:
    """Entry point for ACP server."""
    asyncio.run(run_acp_server())


if __name__ == "__main__":
    main()
