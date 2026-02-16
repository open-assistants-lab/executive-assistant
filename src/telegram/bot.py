from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from src.config.settings import get_settings, parse_model_string
from src.llm import get_llm
from src.llm.errors import LLMError

if TYPE_CHECKING:
    from telegram import Update

logger = logging.getLogger(__name__)


class TelegramBot:
    """
    Telegram bot for interacting with the Ken deep agent.

    Supports:
    - /start - Start conversation
    - /help - Show help
    - /model - Set model for conversation
    - /clear - Clear conversation history
    - Text messages - Chat with agent
    """

    def __init__(
        self,
        token: str,
        default_provider: str = "openai",
        default_model: str = "gpt-4o",
    ) -> None:
        self.token = token
        self.default_provider = default_provider
        self.default_model = default_model
        self._application: Application | None = None
        self._user_models: dict[int, tuple[str, str]] = {}

    @property
    def application(self) -> Application:
        if self._application is None:
            self._application = Application.builder().token(self.token).build()
            self._setup_handlers()
        return self._application

    def _setup_handlers(self) -> None:
        """Set up command and message handlers."""
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("model", self.model_command))
        self.application.add_handler(CommandHandler("clear", self.clear_command))
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        if not update.effective_message:
            return

        user = update.effective_user
        user_name = user.first_name if user else "there"

        settings = get_settings()
        agent_name = settings.agent_name

        await update.effective_message.reply_text(
            f"Hello {user_name}! I'm {agent_name}, your AI assistant.\n\n"
            "Commands:\n"
            "/model <provider/model> - Set model (e.g., /model openai/gpt-4o)\n"
            "/clear - Clear conversation history\n"
            "/help - Show this message\n\n"
            "Just send me a message to start chatting!"
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command."""
        if not update.effective_message:
            return

        await update.effective_message.reply_text(
            "Ken - Executive Assistant Agent\n\n"
            "Commands:\n"
            "/start - Start conversation\n"
            "/model <provider/model> - Change model\n"
            "/clear - Clear history\n"
            "/help - Show this message\n\n"
            "Supported providers: openai, anthropic, google, groq, mistral, cohere, ollama"
        )

    async def model_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /model command to change the model."""
        if not update.effective_message or not update.effective_user:
            return

        user_id = update.effective_user.id

        if not context.args:
            current = self._user_models.get(user_id, (self.default_provider, self.default_model))
            await update.effective_message.reply_text(
                f"Current model: {current[0]}/{current[1]}\n\n"
                "Usage: /model <provider/model>\n"
                "Example: /model anthropic/claude-3-5-sonnet-20241022"
            )
            return

        model_string = " ".join(context.args)
        try:
            provider, model = parse_model_string(model_string)
            self._user_models[user_id] = (provider, model)
            await update.effective_message.reply_text(f"Model changed to: {provider}/{model}")
        except ValueError as e:
            await update.effective_message.reply_text(
                f"Invalid model format. Use: provider/model\nError: {e}"
            )

    async def agent_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /agent command to switch to deep agent mode."""
        if not update.effective_message or not update.effective_user:
            return

        user_id = update.effective_user.id
        self._user_agent_mode[user_id] = True
        context.user_data["messages"] = []
        await update.effective_message.reply_text(
            "Switched to deep agent mode.\n\n"
            "Features: Planning, memory persistence, web search, subagents.\n"
            "Thread ID will be: telegram-{user_id}"
        )

    async def simple_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /simple command to switch to simple LLM mode."""
        if not update.effective_message or not update.effective_user:
            return

        user_id = update.effective_user.id
        self._user_agent_mode[user_id] = False
        await update.effective_message.reply_text(
            "Switched to simple LLM mode.\n\nJust chat - no planning, tools, or persistent memory."
        )

    async def clear_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /clear command to clear conversation history."""
        if not update.effective_message:
            return

        context.user_data["messages"] = []
        await update.effective_message.reply_text("Conversation history cleared.")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle incoming text messages."""
        if not update.effective_message or not update.effective_user:
            return

        user_id = update.effective_user.id
        user_message = update.effective_message.text

        await self._handle_deep_agent(update, context, user_id, user_message)

    async def _handle_deep_agent(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        user_id: int,
        user_message: str,
    ) -> None:
        """Handle message using deep agent with intermediate updates."""
        import json

        from langchain_core.messages import HumanMessage

        from src.agent import create_ea_agent
        from src.telegram.formatters import MessageUpdater

        provider, model = self._user_models.get(
            user_id, (self.default_provider, self.default_model)
        )

        try:
            settings = get_settings()
            thread_id = f"telegram-{user_id}"

            async with create_ea_agent(settings, user_id=str(user_id)) as agent:
                # Start typing indicator immediately
                await update.effective_message.chat.send_action(action="typing")

                # Keep typing alive every few seconds
                import asyncio

                async def keep_typing():
                    while True:
                        try:
                            await asyncio.sleep(3)
                            await update.effective_message.chat.send_action(action="typing")
                        except Exception:
                            break

                typing_task = asyncio.create_task(keep_typing())

                # Track state during streaming
                tool_calls_info = []
                todos_list = []
                middleware_activities = []
                last_content = None
                seen_todos = set()  # Track todos we've already shown
                seen_middleware = set()  # Track middleware activities we've already shown
                status_message = None  # Will be created when we have progress
                updater = None

                try:
                    async for chunk in agent.astream(
                        {
                            "messages": [HumanMessage(content=user_message)],
                            "middleware_activities": [],
                        },
                        config={"configurable": {"thread_id": thread_id}},
                        stream_mode="values",
                    ):
                        # Track tool calls and update status message
                        if "messages" in chunk and chunk["messages"]:
                            last_msg = chunk["messages"][-1]

                            # Track tool calls and show them to user
                            if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
                                for tool_call in last_msg.tool_calls:
                                    tool_name = tool_call.get("name", "unknown")
                                    tool_args = tool_call.get("args", {})
                                    tool_id = tool_call.get("id", "")

                                    if tool_id and not any(tc["id"] == tool_id for tc in tool_calls_info):
                                        # Format subagent calls more informatively
                                        display_name = tool_name
                                        if tool_name == "task":
                                            # This is a subagent delegation
                                            agent = tool_args.get("agent", "")
                                            task_desc = tool_args.get("task", "")
                                            if agent:
                                                # Capitalize agent name
                                                agent_display = agent[0].upper() + agent[1:] if agent else "Agent"
                                                display_name = f"{agent_display}"
                                                if task_desc:
                                                    # Truncate long task descriptions
                                                    task_short = task_desc[:50] + "..." if len(task_desc) > 50 else task_desc
                                                    display_name += f": {task_short}"

                                        tool_calls_info.append({
                                            "id": tool_id,
                                            "name": tool_name,
                                            "display_name": display_name,  # Use display_name for showing
                                            "args": tool_args,
                                        })
                                        logger.info(f"Tool call: {display_name}")

                                        # Create status message on first progress
                                        if status_message is None:
                                            status_text = updater.formatter.format_processing_status(
                                                tool_calls_info,
                                                todos_list,
                                                middleware_activities,
                                            ) if updater else ""
                                            status_message = await update.effective_message.reply_text(
                                                status_text or "⏳"
                                            )
                                            updater = MessageUpdater(status_message)

                                        # Update status message with tool call and middleware
                                        await updater.update_processing_status(
                                            tool_calls_info,
                                            todos_list,
                                            middleware_activities,
                                        )

                        # Track todos and update status
                        if "todos" in chunk and chunk["todos"]:
                            todos = chunk["todos"]
                            # Create a hash of the todos to detect changes
                            todos_str = json.dumps(todos, sort_keys=True, default=str)
                            if todos_str not in seen_todos:
                                seen_todos.add(todos_str)
                                todos_list = todos

                                # Create status message on first progress
                                if status_message is None:
                                    from src.telegram.formatters import MessageFormatter

                                    formatter = MessageFormatter()
                                    status_text = formatter.format_processing_status(
                                        tool_calls_info,
                                        todos_list,
                                        middleware_activities,
                                    )
                                    status_message = await update.effective_message.reply_text(
                                        status_text or "⏳"
                                    )
                                    updater = MessageUpdater(status_message)

                                # Update status message with todos and middleware
                                await updater.update_processing_status(
                                    tool_calls_info,
                                    todos_list,
                                    middleware_activities,
                                )

                        # Track middleware activities
                        if "middleware_activities" in chunk and chunk["middleware_activities"]:
                            for activity in chunk["middleware_activities"]:
                                # Create a unique key for this activity
                                activity_key = json.dumps(
                                    {"name": activity["name"], "status": activity["status"]},
                                    sort_keys=True,
                                )
                                if activity_key not in seen_middleware:
                                    seen_middleware.add(activity_key)
                                    # Update existing activity if same name and status
                                    updated = False
                                    for i, existing in enumerate(middleware_activities):
                                        if existing["name"] == activity["name"]:
                                            middleware_activities[i] = activity
                                            updated = True
                                            break
                                    if not updated:
                                        middleware_activities.append(activity)

                                    logger.info(f"Middleware: {activity['name']} ({activity['status']})")

                                    # Create status message on first progress
                                    if status_message is None:
                                        from src.telegram.formatters import MessageFormatter

                                        formatter = MessageFormatter()
                                        status_text = formatter.format_processing_status(
                                            tool_calls_info,
                                            todos_list,
                                            middleware_activities,
                                        )
                                        status_message = await update.effective_message.reply_text(
                                            status_text or "⏳"
                                        )
                                        updater = MessageUpdater(status_message)

                                    # Update status message with middleware activity
                                    await updater.update_processing_status(
                                        tool_calls_info,
                                        todos_list,
                                        middleware_activities,
                                    )

                        # Save last content
                        if "messages" in chunk and chunk["messages"]:
                            last_msg = chunk["messages"][-1]
                            if hasattr(last_msg, "content") and last_msg.content:
                                # Skip intermediate tool results
                                is_tool_result = (
                                    chunk.get("messages", [])[-2].type == "tool"
                                    if len(chunk.get("messages", [])) > 1
                                    else False
                                )
                                if not is_tool_result:
                                    last_content = last_msg.content

                finally:
                    # Stop typing indicator
                    typing_task.cancel()
                    try:
                        await typing_task
                    except asyncio.CancelledError:
                        pass

                # Send final response as a new message
                if last_content:
                    # If we have a status message, leave it and send new message
                    from src.telegram.formatters import MessageFormatter

                    formatter = MessageFormatter()
                    response_text = formatter.format_final_response(
                        tool_calls_info,
                        last_content,
                        todos_list if todos_list else None,
                        middleware_activities if middleware_activities else None,
                    )
                    await update.effective_message.reply_text(response_text)
                else:
                    await update.effective_message.reply_text("✅ Done")

        except LLMError as e:
            logger.error(f"LLM error: {e}")
            await update.effective_message.reply_text(f"Sorry, I encountered an error: {e.message}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            await update.effective_message.reply_text(
                "Sorry, an unexpected error occurred. Please try again."
            )

    async def start(self) -> None:
        """Start the bot."""
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()

    async def stop(self) -> None:
        """Stop the bot."""
        if self.application.updater:
            await self.application.updater.stop()
        await self.application.stop()
        await self.application.shutdown()

    async def run(self) -> None:
        """Run the bot (blocking)."""
        await self.start()
        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            await self.stop()


_bot: TelegramBot | None = None


def get_bot() -> TelegramBot | None:
    """Get the Telegram bot singleton."""
    return _bot


def create_bot() -> TelegramBot | None:
    """Create and return the Telegram bot if configured."""
    global _bot

    settings = get_settings()

    if not settings.is_telegram_configured:
        logger.info("Telegram bot not configured. Set TELEGRAM_BOT_TOKEN to enable.")
        return None

    provider, model = parse_model_string(settings.llm.default_model)

    _bot = TelegramBot(
        token=settings.telegram_bot_token or "",
        default_provider=provider,
        default_model=model,
    )

    return _bot


async def run_bot() -> None:
    """Run the Telegram bot."""
    bot = create_bot()
    if bot:
        logger.info("Starting Telegram bot...")
        await bot.run()


def run_bot_sync() -> None:
    """Run the Telegram bot synchronously."""
    asyncio.run(run_bot())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_bot_sync()
