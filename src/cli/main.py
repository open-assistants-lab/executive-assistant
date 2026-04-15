"""Executive Assistant CLI - A terminal agent using the SDK runtime."""

import asyncio
import sys

from dotenv import load_dotenv

load_dotenv()  # noqa: E402

from rich.console import Console  # noqa: E402
from rich.markdown import Markdown  # noqa: E402
from rich.panel import Panel  # noqa: E402

from src.app_logging import get_logger  # noqa: E402
from src.sdk.messages import Message  # noqa: E402
from src.sdk.runner import (  # noqa: E402
    _messages_from_conversation,
    run_sdk_agent_stream,
)
from src.storage.messages import get_conversation_store  # noqa: E402

console = Console()
logger = get_logger()


class ExecutiveAssistantCLI:
    """CLI for Executive Assistant - SDK-powered."""

    SLASH_COMMANDS = {
        "/help": "Show available commands",
        "/model": "Switch model (use /model provider:model)",
        "/clear": "Clear conversation history",
        "/quit": "Exit the CLI",
        "/exit": "Exit the CLI",
    }

    def __init__(self, user_id: str = "cli"):
        self.user_id = user_id
        self.conversation = get_conversation_store(user_id)

    def show_help(self):
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

    async def handle_slash_command(self, command: str) -> bool:
        cmd = command.strip().split()[0].lower()

        if cmd == "/help":
            self.show_help()
            return True
        elif cmd == "/model":
            console.print("[yellow]Model switching not supported in shared agent mode[/yellow]")
            return True
        elif cmd == "/clear":
            self.conversation.clear()
            console.print("[yellow]Conversation cleared[/yellow]")
            return True
        elif cmd in ("/quit", "/exit"):
            console.print("[yellow]Goodbye![/yellow]")
            sys.exit(0)
        return False

    def _read_input(self) -> str:
        try:
            line = input("> ")
            if line.rstrip().endswith("\\"):
                lines = [line.rstrip()[:-1]]
                while True:
                    try:
                        next_line = input("| ")
                        if next_line.rstrip().endswith("\\"):
                            lines.append(next_line.rstrip()[:-1])
                        else:
                            lines.append(next_line)
                            break
                    except EOFError:
                        break
                return "\n".join(lines)
            return line.strip()
        except EOFError:
            console.print("\n[yellow]Goodbye![/yellow]")
            sys.exit(0)

    async def run(self):
        console.print(
            Panel(
                "[bold cyan]Executive Assistant[/bold cyan]\n"
                "Type /help for commands, /quit to exit\n"
                "Tip: End line with \\ for multi-line input",
                border_style="cyan",
                expand=False,
            )
        )

        while True:
            try:
                user_input = self._read_input()

                if not user_input:
                    continue

                if user_input.startswith("/"):
                    if await self.handle_slash_command(user_input):
                        continue

                self.conversation.add_message("user", user_input)
                recent_messages = self.conversation.get_messages_with_summary(50)
                sdk_messages = _messages_from_conversation(recent_messages)
                sdk_messages.append(Message.user(user_input))

                console.print("[dim]Thinking...[/dim]")

                response_parts: list[str] = []

                async for chunk in run_sdk_agent_stream(
                    user_id=self.user_id,
                    messages=sdk_messages,
                ):
                    if chunk.canonical_type == "text_delta" and chunk.content:
                        response_parts.append(chunk.content)
                        console.print(chunk.content, end="")

                console.print()

                response = "".join(response_parts) if response_parts else "Task completed."
                self.conversation.add_message("assistant", response)

                logger.info(
                    "agent.response",
                    {"response": response[:80]},
                    user_id=self.user_id,
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
                import traceback

                tb = traceback.format_exc()
                console.print(f"[red]Error: {e}[/red]")
                console.print(f"[dim]{tb[-500:]}[/dim]")


async def run():
    cli = ExecutiveAssistantCLI()
    await cli.run()


def main():
    asyncio.run(run())


if __name__ == "__main__":
    main()
