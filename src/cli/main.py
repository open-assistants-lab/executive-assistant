from typing import Annotated

import typer

from src.config.settings import get_settings

app = typer.Typer(
    name="ea",
    help="Executive Assistant - Deep agent with multi-LLM support",
)


@app.command()
def config() -> None:
    """Show current configuration."""
    settings = get_settings()
    typer.echo("Current Configuration:")
    typer.echo(f"  Agent Name: {settings.agent_name}")
    typer.echo(f"  Environment: {settings.app.env}")
    typer.echo(f"  Debug: {settings.app.debug}")
    typer.echo(f"  Default Model: {settings.llm.default_model}")
    typer.echo(f"  Summarization Model: {settings.llm.summarization_model}")
    typer.echo(f"  Data Path: {settings.data_path}")
    typer.echo(f"  Langfuse: {'Enabled' if settings.is_langfuse_configured else 'Disabled'}")
    typer.echo(f"  Telegram: {'Enabled' if settings.is_telegram_configured else 'Disabled'}")


@app.command()
def message(
    text: Annotated[str, typer.Argument(help="Message to send to your Executive Assistant")],
    user_id: Annotated[str, typer.Option("--user", "-u", help="User ID")] = "default",
    thread: Annotated[str | None, typer.Option("--thread", "-t", help="Thread ID")] = None,
) -> None:
    """Send a single message to your Executive Assistant and exit."""
    import asyncio

    from langchain_core.messages import HumanMessage

    from src.agent import create_ea_agent

    settings = get_settings()
    thread_id = thread or f"{user_id}-cli"

    async def run() -> None:
        async with create_ea_agent(settings, user_id=user_id) as ea_agent:
            result = await ea_agent.ainvoke(
                {
                    "messages": [HumanMessage(content=text)],
                    "middleware_activities": [],
                },
                config={"configurable": {"thread_id": thread_id}},
            )

        last_message = result["messages"][-1]
        content = last_message.content if hasattr(last_message, "content") else str(last_message)

        # Show middleware activities if any
        middleware_activities = result.get("middleware_activities", [])
        if middleware_activities:
            typer.echo("\n⚙️  Middleware Activities:")
            for activity in middleware_activities:
                status_icon = {"active": "⚙️", "completed": "✅", "skipped": "⏭️", "failed": "❌"}.get(
                    activity["status"], "⚙️"
                )
                typer.echo(f"  {status_icon} {activity['name']}")
                if activity.get("message"):
                    typer.echo(f"      {activity['message']}")
            typer.echo("")

        typer.echo(content)

    asyncio.run(run())


@app.command()
def cli(
    user_id: Annotated[str, typer.Option("--user", "-u", help="User ID")] = "default",
    thread: Annotated[str | None, typer.Option("--thread", "-t", help="Thread ID")] = None,
) -> None:
    """Start an interactive CLI session with your Executive Assistant."""
    import asyncio

    from langchain_core.messages import HumanMessage

    from src.agent import create_ea_agent

    settings = get_settings()
    agent_name = settings.agent_name
    thread_id = thread or f"{user_id}-interactive"

    typer.echo(f"{agent_name} - Executive Assistant")
    typer.echo("Commands: 'exit' to quit, 'clear' to reset thread")
    typer.echo("-" * 50)

    async def interactive_loop() -> None:
        current_thread = thread_id

        async with create_ea_agent(settings, user_id=user_id) as ea_agent:
            while True:
                try:
                    user_input = input("\nYou: ").strip()
                except (EOFError, KeyboardInterrupt):
                    typer.echo("\nGoodbye!")
                    break

                if not user_input:
                    continue
                if user_input.lower() == "exit":
                    typer.echo("Goodbye!")
                    break
                if user_input.lower() == "clear":
                    current_thread = f"{user_id}-{asyncio.get_event_loop().time():.0f}"
                    typer.echo(f"Started new thread: {current_thread}")
                    continue

                result = await ea_agent.ainvoke(
                    {
                        "messages": [HumanMessage(content=user_input)],
                        "middleware_activities": [],
                    },
                    config={"configurable": {"thread_id": current_thread}},
                )

                last_message = result["messages"][-1]
                content = (
                    last_message.content if hasattr(last_message, "content") else str(last_message)
                )

                # Show middleware activities if any
                middleware_activities = result.get("middleware_activities", [])
                if middleware_activities:
                    typer.echo("\n⚙️  Middleware Activities:")
                    for activity in middleware_activities:
                        status_icon = {"active": "⚙️", "completed": "✅", "skipped": "⏭️", "failed": "❌"}.get(
                            activity["status"], "⚙️"
                        )
                        typer.echo(f"  {status_icon} {activity['name']}")
                        if activity.get("message"):
                            typer.echo(f"      {activity['message']}")
                    typer.echo("")

                typer.echo(f"\n{agent_name}: {content}")

    asyncio.run(interactive_loop())


@app.command()
def models() -> None:
    """List available LLM providers."""
    from src.llm import list_providers

    providers = list_providers()
    typer.echo("Available providers:")
    for p in sorted(providers):
        typer.echo(f"  - {p}")


@app.command()
def http(
    host: Annotated[str, typer.Option("--host", "-h")] = "0.0.0.0",
    port: Annotated[int, typer.Option("--port", "-p")] = 8000,
    reload: Annotated[bool, typer.Option("--reload")] = False,
) -> None:
    """Start the HTTP API server."""
    import uvicorn

    settings = get_settings()

    uvicorn.run(
        "src.api.main:app",
        host=host or settings.api_host,
        port=port or settings.api_port,
        reload=reload or settings.app.debug,
    )


@app.command()
def telegram() -> None:
    """Start the Telegram bot."""
    from src.telegram import run_bot_sync

    run_bot_sync()


@app.command()
def acp() -> None:
    """Start the ACP server for IDE integration."""
    from src.acp import main

    main()


if __name__ == "__main__":
    app()
