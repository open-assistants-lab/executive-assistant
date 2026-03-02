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

from src.agents.manager import run_agent_stream
from src.storage.conversation import get_conversation_store

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

    def __init__(self, user_id: str = "cli"):
        self.user_id = user_id
        self.messages = []
        self.conversation = get_conversation_store(user_id)

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

    async def handle_slash_command(self, command: str) -> bool:
        """Handle slash commands."""
        cmd = command.strip().split()[0].lower()

        if cmd == "/help":
            self.show_help()
            return True
        elif cmd == "/model":
            console.print("[yellow]Model switching not supported in shared agent mode[/yellow]")
            return True
        elif cmd == "/clear":
            self.messages = []
            console.print("[yellow]Conversation cleared[/yellow]")
            return True
        elif cmd in ("/quit", "/exit"):
            console.print("[yellow]Goodbye![/yellow]")
            sys.exit(0)
        return False

    def _read_input(self) -> str:
        """Read input with multi-line support.

        End a line with \\ to continue to the next line.
        """
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
        """Run the CLI."""
        from src.app_logging import get_logger

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
                recent_messages = self.conversation.get_recent_messages(50)

                langgraph_messages = [
                    HumanMessage(content=m.content)
                    if m.role == "user"
                    else AIMessage(content=m.content)
                    for m in recent_messages
                ]

                console.print("[dim]Thinking...[/dim]")

                logger = get_logger()
                all_messages = []

                with propagate_attributes(user_id=self.user_id):
                    async for chunk in run_agent_stream(
                        user_id=self.user_id,
                        messages=langgraph_messages,
                        message=user_input,
                    ):
                        chunk_type = getattr(chunk, "type", None)

                        if chunk_type == "tool":
                            content = getattr(chunk, "content", None)
                            if content:
                                console.print(f"[dim]Tool: {content[:100]}...[/dim]")

                        elif chunk_type == "ai":
                            content = getattr(chunk, "content", "")
                            if content:
                                console.print(content, end="")

                        all_messages.append(chunk)

                console.print()

                response = None
                tool_results = []

                for msg in all_messages:
                    msg_type = getattr(msg, "type", None)
                    if msg_type == "tool":
                        content = getattr(msg, "content", None)
                        if content:
                            tool_results.append(content)

                for msg in reversed(all_messages):
                    msg_type = getattr(msg, "type", None)
                    content = getattr(msg, "content", None)
                    if msg_type == "ai":
                        tool_calls = getattr(msg, "tool_calls", None)
                        if tool_calls and tool_results:
                            response = "\n".join(tool_results)
                            break
                        if tool_calls:
                            tool_names = [tc.get("name", "unknown") for tc in tool_calls]
                            response = f"Tool(s) executed: {', '.join(tool_names)}"
                            break
                        if content and content.strip():
                            response = content
                            break

                if not response:
                    response = "Task completed."

                self.conversation.add_message("assistant", response)

                logger.info(
                    "agent.response", {"response": response}, user_id=self.user_id, channel="cli"
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
    """Run the CLI."""
    cli = ExecutiveAssistantCLI()
    await cli.run()


def main():
    """Entry point for CLI."""
    asyncio.run(run())


if __name__ == "__main__":
    main()
