"""Executive Assistant CLI - A terminal agent similar to Deep Agents CLI."""

import asyncio
import sys

from dotenv import load_dotenv

load_dotenv()

from langchain_core.messages import AIMessage, HumanMessage
from langfuse import propagate_attributes
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from src.agents.factory import get_agent_factory
from src.llm import create_model_from_config
from src.logging import get_logger

console = Console()


class ExecutiveAssistantCLI:
    """CLI for Executive Assistant - similar to Deep Agents CLI."""

    SLASH_COMMANDS = {
        "/help": "Show available commands",
        "/model": "Switch model (use /model provider:model)",
        "/clear": "Clear conversation history",
        "/quit": "Exit the CLI",
        "/exit": "Exit the CLI",
    }

    def __init__(self):
        self.model = None
        self.agent = None
        self.messages = []

    def setup(self):
        """Initialize the agent."""
        console.print("[bold cyan]Initializing Executive Assistant...[/bold cyan]")

        self.model = create_model_from_config()
        model_name = getattr(self.model, "model", "unknown")
        provider = getattr(self.model, "_provider", "ollama")  # Default to ollama
        console.print(f"[green]✓[/green] Provider: {provider}")
        console.print(f"[green]✓[/green] Model: {model_name}")

        factory = get_agent_factory()
        self.agent = factory.create(
            model=self.model,
            tools=[],
            system_prompt="You are a helpful executive assistant. Be concise and helpful.",
        )
        console.print("[green]✓[/green] Agent ready")

    async def handle_slash_command(self, command: str) -> bool:
        """Handle slash commands."""
        cmd = command.strip().split()[0].lower()

        if cmd == "/help":
            self.show_help()
            return True
        elif cmd == "/model":
            await self.handle_model_command(command)
            return True
        elif cmd == "/clear":
            self.messages = []
            console.print("[yellow]Conversation cleared[/yellow]")
            return True
        elif cmd in ("/quit", "/exit"):
            console.print("[yellow]Goodbye![/yellow]")
            sys.exit(0)
        return False

    async def handle_model_command(self, command: str):
        """Handle /model command."""
        parts = command.strip().split()
        if len(parts) < 2:
            console.print("[yellow]Usage: /model provider:model[/yellow]")
            return

        new_model = parts[1]
        try:
            console.print(f"[yellow]Switching to {new_model}...[/yellow]")
            self.model = create_model_from_config(new_model)
            factory = get_agent_factory()
            self.agent = factory.create(
                model=self.model,
                tools=[],
                system_prompt="You are a helpful executive assistant.",
            )
            console.print(f"[green]✓[/green] Switched to {new_model}")
        except Exception as e:
            console.print(f"[red]Failed: {e}[/red]")

    def show_help(self):
        """Show help message."""
        console.print(
            Panel(
                "[bold]Executive Assistant CLI[/bold]\n\n"
                + "\n".join(
                    f"[cyan]{cmd}[/cyan] - {desc}" for cmd, desc in self.SLASH_COMMANDS.items()
                ),
                title="Commands",
                border_style="cyan",
            )
        )

    async def run(self):
        """Run the CLI."""
        self.setup()

        console.print(
            Panel(
                "[bold cyan]Executive Assistant[/bold cyan]\n"
                "Type /help for commands, /quit to exit",
                border_style="cyan",
                expand=False,
            )
        )

        while True:
            try:
                user_input = input("> ").strip()

                if not user_input:
                    continue

                if user_input.startswith("/"):
                    if await self.handle_slash_command(user_input):
                        continue

                self.messages.append(HumanMessage(content=user_input))

                console.print("[dim]Thinking...[/dim]")

                logger = get_logger()
                handler = logger.langfuse_handler

                # Build config with Langfuse handler if available
                config = {}
                if handler:
                    config["callbacks"] = [handler]

                with logger.timer(
                    "agent",
                    {"message": user_input, "message_count": len(self.messages)},
                    channel="cli",
                ):
                    with propagate_attributes(user_id="default"):
                        result = await self.agent.ainvoke(
                            {"messages": self.messages}, config=config if config else None
                        )

                response = result["messages"][-1].content
                self.messages.append(AIMessage(content=response))

                # Log response
                logger.info(
                    "agent.response",
                    {"response": response},
                    channel="cli",
                )

                console.print()
                console.print(Markdown(response))

            except KeyboardInterrupt:
                console.print("\n[yellow]Use /quit to exit[/yellow]")
            except EOFError:
                console.print("\n[yellow]Goodbye![/yellow]")
                break
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")


async def run():
    """Run the CLI."""
    cli = ExecutiveAssistantCLI()
    await cli.run()


def main():
    """Entry point for CLI."""
    asyncio.run(run())


if __name__ == "__main__":
    main()
