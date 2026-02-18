from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from src.commands import (
    get_current_model,
    handle_clear_command,
    handle_model_command,
    set_current_model,
)
from src.config.settings import get_settings, parse_model_string
from src.llm.errors import LLMError
from src.utils import create_thread_id
from src.utils.checkpoint import delete_thread_checkpoint

if TYPE_CHECKING:
    from telegram import Update

logger = logging.getLogger(__name__)

# Configure logging to ensure logs are output
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)
    # Log level will be set from settings in run() method
    logger.setLevel(logging.INFO)
    logger.propagate = False


def looks_like_file_content(content: str) -> bool:
    """Check if content looks like file content rather than a conversational response.

    File content indicators:
    - Large blocks of text (>1000 chars)
    - Contains line numbers (e.g., "201:", "202:")
    - Contains PDF-like headers/footers
    - Mostly code/data with minimal conversational text

    Args:
        content: The content to check

    Returns:
        True if content looks like file content, False otherwise
    """
    if not content or len(content) < 500:
        return False

    # Check for line numbers pattern (common in file dumps)
    import re

    line_number_pattern = r"^\s*\d+\s*:"
    if re.search(line_number_pattern, content, re.MULTILINE):
        # Count how many lines start with line numbers
        lines_with_line_numbers = sum(
            1 for line in content.split("\n") if re.match(line_number_pattern, line.strip())
        )
        # If more than 30% of lines have line numbers, it's likely file content
        if lines_with_line_numbers / len(content.split("\n")) > 0.3:
            return True

    # Check for PDF indicators
    pdf_indicators = ["©", "All rights reserved", "Version:", "Generated:", "CONFIDENTIAL"]
    pdf_indicator_count = sum(1 for indicator in pdf_indicators if indicator in content)
    if pdf_indicator_count >= 2:
        return True

    # Large content with very little conversational markers
    conversational_markers = [
        "I",
        "you",
        "the",
        "is",
        "are",
        "will",
        "can",
        "should",
        "here",
        "your",
    ]
    if len(content) > 2000:
        # Check ratio of conversational words
        words = content.lower().split()
        conversational_count = sum(1 for word in words if word in conversational_markers)
        if conversational_count / len(words) < 0.1:  # Less than 10% conversational
            return True

    return False


class TelegramBot:
    """
    Telegram bot for interacting with the Executive Assistant deep agent.

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

        # Error handler for catching all errors
        async def error_handler(update, context):
            logger.error(f"❌ Error processing update: {context.error}")

        self.application.add_error_handler(error_handler)

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        if not update.effective_message:
            return

        user = update.effective_user
        user_name = user.first_name if user else "there"
        user_id = user.id if user else "unknown"
        new_thread_id = create_thread_id(user_id=str(user_id), channel="telegram", reason="start")
        context.user_data["thread_id"] = new_thread_id

        settings = get_settings()
        agent_name = settings.agent_name

        logger.info(f"📱 /start command - User: {user_name} (ID: {user_id})")

        await update.effective_message.reply_text(
            f"Hello {user_name}! I'm {agent_name}, your AI assistant.\n\n"
            "Commands:\n"
            "/model <provider/model> - Set model (e.g., /model openai/gpt-4o)\n"
            "/clear - Clear conversation history\n"
            "/help - Show this message\n\n"
            "Just send me a message to start chatting!"
        )

        logger.info(f"✓ Sent welcome message to {user_name} (ID: {user_id})")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command."""
        if not update.effective_message:
            return

        await update.effective_message.reply_text(
            "Executive Assistant Agent\n\n"
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

        user = update.effective_user
        user_id = user.id
        user_name = user.first_name if user else f"User_{user_id}"

        logger.info(f"⚙️ /model command from {user_name} (ID: {user_id})")

        if not context.args:
            current = get_current_model(str(user_id))
            if current is None:
                current = (self.default_provider, self.default_model)
            logger.info(f"   Current model: {current[0]}/{current[1]}")
            await update.effective_message.reply_text(
                f"Current model: {current[0]}/{current[1]}\n\n"
                "Usage: /model <provider/model>\n"
                "Example: /model anthropic/claude-sonnet-4-6\n"
                "Available providers: openai, anthropic, google, groq, ollama, etc."
            )
            return

        model_string = " ".join(context.args)
        logger.info("   Requested model: %s", model_string)

        result = handle_model_command(
            model_string=model_string,
            user_id=str(user_id),
            get_current_model=get_current_model,
            set_model=set_current_model,
        )
        await update.effective_message.reply_text(result)

    async def clear_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /clear command to clear conversation history."""
        if not update.effective_message:
            return

        user = update.effective_user
        user_id = user.id
        user_name = user.first_name if user else f"User_{user_id}"

        logger.info(f"🗑️ /clear command from {user_name} (ID: {user_id})")

        old_thread_id = context.user_data.get("thread_id")
        new_thread_id = create_thread_id(user_id=str(user_id), channel="telegram", reason="clear")
        context.user_data["thread_id"] = new_thread_id
        context.user_data["messages"] = []
        checkpoint_deleted = await delete_thread_checkpoint(
            get_settings().database_url,
            old_thread_id,
        )

        logger.info(f"✓ Conversation history cleared for {user_name} (ID: {user_id})")
        logger.info(
            "   old_thread_id=%s, new_thread_id=%s, checkpoint_deleted=%s",
            old_thread_id,
            new_thread_id,
            checkpoint_deleted,
        )
        await update.effective_message.reply_text(
            handle_clear_command(user_id=str(user_id), thread_id=new_thread_id)
        )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle incoming text messages."""
        if not update.effective_message or not update.effective_user:
            return

        user = update.effective_user
        user_id = user.id
        user_name = user.first_name if user else f"User_{user_id}"
        user_message = update.effective_message.text

        logger.info(f"📨 Message received from {user_name} (ID: {user_id})")
        logger.info(f"   Message: {user_message[:100]}{'...' if len(user_message) > 100 else ''}")

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
        from src.telegram.formatters import MessageFormatter, MessageUpdater

        provider, model = get_current_model(str(user_id)) or (
            self.default_provider,
            self.default_model,
        )

        logger.info(f"🤖 Processing with model: {provider}/{model}")

        try:
            settings = get_settings()
            thread_id = context.user_data.get("thread_id")
            if not thread_id:
                thread_id = create_thread_id(
                    user_id=str(user_id),
                    channel="telegram",
                    reason="session",
                )
                context.user_data["thread_id"] = thread_id
            verbose = getattr(settings, "display_verbose", False)

            logger.info(f"📂 Thread ID: {thread_id}, verbose={verbose}")

            async with create_ea_agent(
                settings,
                user_id=str(user_id),
                model_override=(provider, model),
            ) as agent:
                # NOTE: Typing indicator disabled to avoid long hourglass animation
                # The agent will respond directly when ready
                # await update.effective_message.chat.send_action(action="typing")

                # # Keep typing alive every few seconds
                # import asyncio
                #
                # async def keep_typing():
                #     while True:
                #         try:
                #             await asyncio.sleep(3)
                #             await update.effective_message.chat.send_action(action="typing")
                #         except Exception:
                #             break
                #
                # typing_task = asyncio.create_task(keep_typing())
                # Start typing indicator immediately
                await update.effective_message.chat.send_action(action="typing")

                # Keep typing alive every few seconds
                async def keep_typing():
                    while True:
                        try:
                            await asyncio.sleep(3)
                            await update.effective_message.chat.send_action(action="typing")
                        except Exception:
                            break

                typing_task = asyncio.create_task(keep_typing())

                # Send immediate "Thinking..." message
                status_message = await update.effective_message.reply_text("🤔 Thinking...")
                updater = MessageUpdater(status_message)

                # Track state during streaming
                tool_calls_info = []
                tool_call_times = {}  # Track start times for tool calls: {tool_id: start_time}
                todos_list = []  # Reset for each new message
                todos_display_list = []  # Enhanced todos from TodoDisplayMiddleware
                middleware_activities = []
                thinking_preview_sent = False  # Track if we sent thinking preview
                last_content = None
                last_reasoning = None  # Track LLM reasoning/thinking process
                last_seen_todos = None  # Track last seen todos to detect status changes
                final_state = {}  # Track final state for middleware results

                try:
                    async for chunk in agent.astream(
                        {
                            "messages": [HumanMessage(content=user_message)],
                            "middleware_activities": [],
                        },
                        config={"configurable": {"thread_id": thread_id}},
                        stream_mode="values",
                        durability="async",
                    ):
                        # Save final state to check for middleware results
                        final_state = chunk

                        # Track tool calls and update status message
                        if "messages" in chunk and chunk["messages"]:
                            last_msg = chunk["messages"][-1]

                            # Track tool calls and show them to user
                            if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
                                for tool_call in last_msg.tool_calls:
                                    tool_name = tool_call.get("name", "unknown")
                                    tool_args = tool_call.get("args", {})
                                    tool_id = tool_call.get("id", "")

                                    if tool_id and not any(
                                        tc["id"] == tool_id for tc in tool_calls_info
                                    ):
                                        # Format subagent calls more informatively
                                        display_name = tool_name
                                        if tool_name == "task":
                                            # This is a subagent delegation
                                            agent = tool_args.get("agent", "")
                                            task_desc = tool_args.get("task", "")
                                            if agent:
                                                # Capitalize agent name
                                                agent_display = (
                                                    agent[0].upper() + agent[1:]
                                                    if agent
                                                    else "Agent"
                                                )
                                                display_name = f"{agent_display}"
                                                if task_desc:
                                                    # Truncate long task descriptions
                                                    task_short = (
                                                        task_desc[:50] + "..."
                                                        if len(task_desc) > 50
                                                        else task_desc
                                                    )
                                                    display_name += f": {task_short}"

                                        tool_calls_info.append(
                                            {
                                                "id": tool_id,
                                                "name": tool_name,
                                                "display_name": display_name,  # Use display_name for showing
                                                "args": tool_args,
                                            }
                                        )
                                        # Track start time for duration calculation
                                        tool_call_times[tool_id] = time.time()

                                        logger.info(f"Tool call: {display_name}, verbose={verbose}")

                                        # Send tool call as separate message (in verbose mode)
                                        if verbose:
                                            logger.info(f"Sending tool call message: {tool_name}")
                                            tool_text = MessageFormatter.format_tool_call(
                                                tool_name, tool_args, tool_id
                                            )
                                            try:
                                                await update.effective_message.chat.send_message(
                                                    tool_text
                                                )
                                            except Exception:
                                                pass
                                            # Don't update status message in verbose mode - use separate messages
                                        else:
                                            # Update status message with tool call
                                            await updater.update_processing_status(
                                                tool_calls_info,
                                                todos_list,
                                                [],
                                            )

                        # Track todos and update status
                        # First check for enhanced todos from TodoDisplayMiddleware
                        if "todos_display" in chunk and chunk["todos_display"]:
                            enhanced_todos = chunk["todos_display"]
                            if enhanced_todos:
                                todos_display_list = enhanced_todos
                                logger.info(
                                    f"📋 Enhanced plan available: {len(enhanced_todos)} items"
                                )
                                for todo in enhanced_todos[:3]:
                                    logger.info(
                                        f"   {todo.get('index', '?')}. [{todo.get('display_status', '?')}] {todo.get('content', '')[:40]}"
                                    )

                        # Also track original todos for backward compatibility
                        if "todos" in chunk and chunk["todos"]:
                            todos = chunk["todos"]
                            # Check if todos actually changed (content or status)
                            current_todos_str = json.dumps(todos, sort_keys=True, default=str)
                            if current_todos_str != last_seen_todos:
                                # Todos changed - update display
                                last_seen_todos = current_todos_str
                                todos_list = todos
                                logger.info(f"📋 Plan updated: {len(todos)} items")
                                for i, todo in enumerate(todos[:5], 1):
                                    if isinstance(todo, dict):
                                        status = todo.get("status", "unknown")
                                        content = todo.get("content", str(todo))[:50]
                                        logger.info(f"   {i}. [{status}] {content}")
                                    else:
                                        logger.info(f"   {i}. {str(todo)[:50]}")
                                if len(todos) > 5:
                                    logger.info(f"   ... and {len(todos) - 5} more")

                                # Update status message with current todos and tool calls
                                await updater.update_processing_status(
                                    tool_calls_info,
                                    todos_list,
                                    [],  # No middleware activities sent to user
                                )

                        # Track middleware activities for logging (not sent to user)
                        if "middleware_activities" in chunk and chunk["middleware_activities"]:
                            for activity in chunk["middleware_activities"]:
                                # Just log middleware activities, don't send to user
                                logger.info(
                                    f"⚙️ Middleware: {activity['name']} ({activity['status']})"
                                )
                                if activity.get("message"):
                                    logger.info(f"   Message: {activity['message']}")

                        # Save last content and reasoning
                        if "messages" in chunk and chunk["messages"]:
                            last_msg = chunk["messages"][-1]

                            # Show thinking preview BEFORE tool calls (in verbose mode)
                            if (
                                verbose
                                and not thinking_preview_sent
                                and hasattr(last_msg, "content")
                                and last_msg.content
                                and hasattr(last_msg, "tool_calls")
                                and last_msg.tool_calls  # Has tool calls = thinking before action
                            ):
                                # This is the LLM's response before tool execution
                                # Extract the thinking part (before tool calls)
                                content = last_msg.content if hasattr(last_msg, "content") else ""

                                # Check if there's explicit reasoning
                                reasoning = None
                                if hasattr(last_msg, "additional_kwargs"):
                                    reasoning = last_msg.additional_kwargs.get("reasoning_content")

                                # If no explicit reasoning, use content as thinking
                                if not reasoning and content:
                                    reasoning = content

                                if reasoning and isinstance(reasoning, str):
                                    # Send thinking preview as separate message BEFORE tool calls
                                    thinking_text = (
                                        reasoning[:200] + "..."
                                        if len(reasoning) > 200
                                        else reasoning
                                    )
                                    try:
                                        await update.effective_message.chat.send_message(
                                            f"🤔 {thinking_text}"
                                        )
                                        thinking_preview_sent = True
                                        # Don't clear last_content - it will be the final response
                                    except Exception:
                                        pass

                            if hasattr(last_msg, "content") and last_msg.content:
                                # Skip intermediate tool results
                                is_tool_result = (
                                    chunk.get("messages", [])[-2].type == "tool"
                                    if len(chunk.get("messages", [])) > 1
                                    else False
                                )
                                # Skip internal summarization messages (they're for context, not user display)
                                is_summary_message = (
                                    last_msg.additional_kwargs.get("lc_source") == "summarization"
                                    if hasattr(last_msg, "additional_kwargs")
                                    else False
                                )
                                if not is_tool_result and not is_summary_message:
                                    last_content = last_msg.content

                                    # Extract reasoning/thinking content if available
                                    # Some models (Ollama, DeepSeek, XAI, Groq) provide this
                                    if hasattr(last_msg, "additional_kwargs"):
                                        reasoning = last_msg.additional_kwargs.get(
                                            "reasoning_content"
                                        )
                                        if reasoning and isinstance(reasoning, str):
                                            last_reasoning = reasoning

                finally:
                    # Stop typing indicator
                    typing_task.cancel()
                    try:
                        await typing_task
                    except asyncio.CancelledError:
                        pass

                # Check final state for enhanced todos from TodoDisplayMiddleware
                if final_state.get("todos_display"):
                    todos_display_list = final_state["todos_display"]
                    logger.info(
                        f"✓ Using enhanced todos from TodoDisplayMiddleware: {len(todos_display_list)} items"
                    )

                # Send final response as a new message

                # Build thinking preview if verbose mode is enabled
                thinking_preview = None
                if verbose and last_reasoning:
                    thinking_preview = (
                        last_reasoning[:200] + "..."
                        if len(last_reasoning) > 200
                        else last_reasoning
                    )

                # Update tool calls with results if verbose mode
                if verbose and tool_calls_info and final_state.get("messages"):
                    from src.telegram.formatters import MessageFormatter

                    for msg in final_state["messages"]:
                        if hasattr(msg, "type") and msg.type == "tool":
                            tool_call_id = (
                                msg.tool_call_id if hasattr(msg, "tool_call_id") else None
                            )
                            # Find matching tool call and update with result
                            for tc in tool_calls_info:
                                if tc.get("id") == tool_call_id:
                                    # Calculate duration if we have start time
                                    start_time = tool_call_times.get(tool_call_id)
                                    duration_ms = 0
                                    if start_time:
                                        duration_ms = (time.time() - start_time) * 1000
                                        tc["duration_ms"] = round(duration_ms, 2)
                                    # Add result preview (truncated)
                                    result_preview = str(msg.content)[:100] if msg.content else ""
                                    if len(str(msg.content)) > 100:
                                        result_preview += "..."
                                    tc["result_preview"] = result_preview
                                    tc["completed"] = True

                                    # Track file path if this is a write_file call
                                    if tc.get("name") == "write_file":
                                        file_path = tc.get("args", {}).get("file_path", "")
                                        if file_path:
                                            tc["file_path"] = file_path

                                    # Send tool result as separate message
                                    tool_result_text = MessageFormatter.format_tool_result(
                                        tc.get("name", "tool"), result_preview, duration_ms
                                    )
                                    try:
                                        await update.effective_message.chat.send_message(
                                            tool_result_text
                                        )
                                    except Exception:
                                        pass
                                    break

                if last_content:
                    # Check if content looks like file content and replace with message
                    if looks_like_file_content(last_content):
                        logger.info(f"📄 Detected file content in response, replacing with summary")

                        # Try to find file path from write_file tool call
                        file_path = ""
                        for tc in tool_calls_info:
                            if tc.get("name") == "write_file" and tc.get("file_path"):
                                file_path = tc["file_path"]
                                break

                        # Try to extract a brief summary from the beginning
                        lines = last_content.split("\n")
                        summary_lines = []
                        for line in lines[:10]:
                            if line.strip() and not line.strip().startswith(
                                ("201", "202", "203", "©", "Version:", "Generated:")
                            ):
                                summary_lines.append(line.strip())
                            if len(summary_lines) >= 3:
                                break

                        if summary_lines:
                            path_text = f"\n📁 Path: `{file_path}`" if file_path else ""
                            last_content = (
                                "📄 **File Created**\n\n"
                                + "\n".join(summary_lines[:3])
                                + path_text
                                + "\n\n(The full file content has been saved to the filesystem.)"
                            )
                        else:
                            path_text = f"\n📁 Path: `{file_path}`" if file_path else ""
                            last_content = f"📄 **File Created**{path_text}\n\n(The file content has been saved to the filesystem.)"

                    # In verbose mode, always delete status message - we use separate messages
                    # Otherwise, only delete if no todos/tools
                    if verbose:
                        should_delete_status = True
                    else:
                        should_delete_status = (
                            not todos_display_list and not todos_list and not tool_calls_info
                        )

                    if should_delete_status:
                        try:
                            await status_message.delete()
                            logger.info("✓ Deleted status message")
                        except Exception as e:
                            logger.warning(f"Could not delete status message: {e}")
                    else:
                        # Keep the status message - it shows the final plan/tool status
                        logger.info("✓ Keeping status message with plan/tool progress")

                    # Send final response as a new message
                    formatter = MessageFormatter()

                    # Prefer enhanced todos from TodoDisplayMiddleware, fall back to regular todos
                    todos_to_show = (
                        todos_display_list
                        if todos_display_list
                        else (todos_list if todos_list else None)
                    )
                    response_text = formatter.format_final_response(
                        tool_calls_info,
                        last_content,
                        todos_to_show,
                        middleware_activities if middleware_activities else None,
                        reasoning=last_reasoning if not thinking_preview_sent else None,
                    )

                    response_preview = (
                        response_text[:100] + "..." if len(response_text) > 100 else response_text
                    )
                    logger.info(f"✓ Sending response to user (ID: {user_id})")
                    logger.info(f"   Response preview: {response_preview}")

                    await update.effective_message.reply_text(response_text)
                else:
                    logger.info(f"✓ Sent completion message to user (ID: {user_id})")
                    await update.effective_message.reply_text("✅ Done")

            logger.info(f"✅ Message handling complete for user (ID: {user_id})")

        except LLMError as e:
            logger.error(f"❌ LLM error for user {user_id}: {e}")
            logger.error(f"   Provider: {provider}, Model: {model}")
            await update.effective_message.reply_text(f"Sorry, I encountered an error: {e.message}")
        except Exception as e:
            logger.exception(f"❌ Unexpected error for user {user_id}: {e}")
            await update.effective_message.reply_text(
                "Sorry, an unexpected error occurred. Please try again."
            )

    async def start(self) -> None:
        """Start the bot."""
        logger.info("🔌 Initializing Telegram application...")
        await self.application.initialize()
        logger.info("✓ Application initialized")

        logger.info("🔄 Starting application...")
        await self.application.start()
        logger.info("✓ Application started")

        logger.info("🔄 Starting bot updater...")
        await self.application.updater.start_polling()
        logger.info("✓ Bot is now polling for messages")

    async def stop(self) -> None:
        """Stop the bot."""
        logger.info("🛑 Stopping Telegram bot...")
        if self.application.updater:
            logger.info("  Stopping updater...")
            await self.application.updater.stop()
            logger.info("  ✓ Updater stopped")

        logger.info("  Stopping application...")
        await self.application.stop()
        logger.info("  ✓ Application stopped")

        logger.info("  Shutting down...")
        await self.application.shutdown()
        logger.info("  ✓ Shutdown complete")

    async def run(self) -> None:
        """Run the bot (blocking)."""
        from src.config.settings import get_settings

        # Configure log level from YAML config (not env var)
        settings = get_settings()
        logger.setLevel(settings.log_level)
        for handler in logger.handlers:
            handler.setLevel(settings.log_level)

        logger.info("=" * 60)
        logger.info("🚀 Starting Executive Assistant Telegram Bot")
        logger.info("=" * 60)
        logger.info(f"Default model: {self.default_provider}/{self.default_model}")
        logger.info(f"Token: {self.token[:20]}...{self.token[-4:]}")
        logger.info(f"Log level: {settings.log_level}")
        logger.info("Bot is now polling for messages...")
        logger.info("=" * 60)

        await self.start()
        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("🛑 Bot shutdown requested")
            pass
        finally:
            await self.stop()
            logger.info("✓ Bot stopped gracefully")


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
