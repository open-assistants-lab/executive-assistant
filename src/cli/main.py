from typing import Annotated

import typer

from src.commands import (
    get_current_model,
    get_help_text,
    handle_clear_command,
    handle_model_command,
    set_current_model,
)
from src.config.settings import get_settings
from src.utils import create_thread_id, get_last_displayable_message
from src.utils.checkpoint import delete_thread_checkpoint


# ============================================================================
# Slash Command Handlers
# ============================================================================

def handle_slash_command(user_input: str, user_id: str, thread_id: str) -> tuple[str, str | None]:
    """Handle slash commands in interactive CLI mode.

    Args:
        user_input: User input starting with /
        user_id: User ID
        thread_id: Current thread ID

    Returns:
        Tuple of (response message, new thread ID if rotated)
    """
    parts = user_input.split(maxsplit=1)
    command = parts[0].lower()
    args = parts[1] if len(parts) > 1 else None

    if command == "/help":
        return get_help_text(), None

    elif command == "/model":
        model_string = args.strip() if args else None
        result = handle_model_command(
            model_string=model_string,
            user_id=user_id,
            get_current_model=get_current_model,
            set_model=set_current_model,
        )
        return result, None

    elif command == "/clear":
        new_thread_id = create_thread_id(user_id=user_id, channel="cli", reason="clear")
        result = handle_clear_command(user_id=user_id, thread_id=new_thread_id)
        return result, new_thread_id

    else:
        return f"Unknown command: {command}\nType /help for available commands.", None

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
    typer.echo(f"  Hot-reload: {settings.app.hot_reload}")
    typer.echo(f"  Default Model: {settings.llm.default_model}")
    typer.echo(f"  Summarization Model: {settings.llm.summarization_model}")
    typer.echo(f"  Data Path: {settings.data_path}")
    typer.echo(f"  Langfuse: {'Enabled' if settings.is_langfuse_configured else 'Disabled'}")
    typer.echo(f"  Telegram: {'Enabled' if settings.is_telegram_configured else 'Disabled'}")


@app.command()
def help_cmd() -> None:
    """Show help text with available commands."""
    typer.echo(get_help_text())


@app.command()
def model(
    model_string: Annotated[str, typer.Argument(help="Model string (e.g., openai/gpt-4o)")],
    user_id: Annotated[str, typer.Option("--user", "-u", help="User ID")] = "default",
) -> None:
    """Show or change the current model."""
    result = handle_model_command(
        model_string=model_string,
        user_id=user_id,
        get_current_model=get_current_model,
        set_model=set_current_model,
    )
    typer.echo(result)


@app.command()
def clear(
    user_id: Annotated[str, typer.Option("--user", "-u", help="User ID")] = "default",
    current_thread_id: Annotated[
        str | None,
        typer.Option("--thread", "-t", help="Thread ID to clear from checkpoint storage"),
    ] = None,
) -> None:
    """Clear conversation history (starts new thread)."""
    import asyncio

    settings = get_settings()
    if current_thread_id:
        asyncio.run(delete_thread_checkpoint(settings.database_url, current_thread_id))

    new_thread_id = create_thread_id(user_id=user_id, channel="cli", reason="clear")
    result = handle_clear_command(user_id=user_id, thread_id=new_thread_id)
    typer.echo(result)


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
    thread_id = thread or create_thread_id(user_id=user_id, channel="cli", reason="message")

    async def run() -> None:
        model_override = get_current_model(user_id)
        async with create_ea_agent(
            settings,
            user_id=user_id,
            model_override=model_override,
        ) as ea_agent:
            result = await ea_agent.ainvoke(
                {
                    "messages": [HumanMessage(content=text)],
                    "middleware_activities": [],
                },
                config={"configurable": {"thread_id": thread_id}},
                durability="async",
            )

        content = get_last_displayable_message(result)

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
    thread_id = thread or create_thread_id(user_id=user_id, channel="cli", reason="session")

    typer.echo(f"{agent_name} - Executive Assistant")
    typer.echo("Commands: 'exit' or 'quit' to exit, '/clear' to reset thread")
    typer.echo("Type '/help' for available commands")
    typer.echo("-" * 50)

    async def interactive_loop() -> None:
        current_thread = thread_id

        while True:
            try:
                user_input = input("\nYou: ").strip()
            except (EOFError, KeyboardInterrupt):
                typer.echo("\nGoodbye!")
                break

            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit"):
                typer.echo("Goodbye!")
                break

            # Handle slash commands
            if user_input.startswith("/"):
                if user_input.split(maxsplit=1)[0].lower() == "/clear":
                    await delete_thread_checkpoint(settings.database_url, current_thread)

                response_text, new_thread_id = handle_slash_command(
                    user_input, user_id, current_thread
                )
                typer.echo(response_text)
                if new_thread_id:
                    current_thread = new_thread_id
                continue

            model_override = get_current_model(user_id)
            async with create_ea_agent(
                settings,
                user_id=user_id,
                model_override=model_override,
            ) as ea_agent:
                result = await ea_agent.ainvoke(
                    {
                        "messages": [HumanMessage(content=user_input)],
                        "middleware_activities": [],
                    },
                    config={"configurable": {"thread_id": current_thread}},
                    durability="async",
                )

            content = get_last_displayable_message(result)

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
        reload=reload or settings.app.hot_reload,
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
