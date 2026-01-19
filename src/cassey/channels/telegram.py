"""Telegram channel implementation using python-telegram-bot."""

import asyncio
import re
from typing import Any

from telegram import Update
from telegram.error import BadRequest
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from langgraph.types import Runnable

from cassey.channels.base import BaseChannel, MessageFormat
from cassey.channels.management_commands import (
    mem_command,
    vs_command,
    db_command,
    file_command,
    meta_command,
)
from cassey.config.settings import settings
from loguru import logger


class TelegramChannel(BaseChannel):
    """
    Telegram bot channel implementation.

    This channel handles:
    - Receiving messages via Telegram bot API
    - Processing messages through the ReAct agent
    - Streaming responses back to the user

    Attributes:
        token: Telegram bot token from BotFather.
        agent: Compiled LangGraph ReAct agent.
        application: python-telegram-bot Application instance.
        _thread_locks: Per-thread asyncio locks to prevent concurrent message interleaving.
    """

    def __init__(
        self,
        token: str | None = None,
        agent: Runnable | None = None,
    ) -> None:
        token = token or settings.TELEGRAM_BOT_TOKEN
        if not token:
            raise ValueError("Telegram bot token not provided")

        super().__init__(agent)
        self.token = token
        self.application: Application | None = None
        self._thread_locks: dict[str, asyncio.Lock] = {}
        self._status_messages: dict[str, int] = {}  # conversation_id -> message_id for editing
        self._debug_chats: set[int] = set()  # chat IDs with verbose debug mode enabled

    def _get_thread_lock(self, thread_id: str) -> asyncio.Lock:
        """Get or create a lock for the given thread_id."""
        if thread_id not in self._thread_locks:
            self._thread_locks[thread_id] = asyncio.Lock()
        return self._thread_locks[thread_id]

    def _is_corruption_error(self, error_str: str) -> bool:
        """Check if an error is related to checkpoint corruption."""
        error_lower = error_str.lower()
        corruption_indicators = [
            "tool_call",
            "toolcallid",
            "tool_calls",
            "must be followed by tool messages",
            "orphaned",
        ]
        return any(indicator in error_lower for indicator in corruption_indicators)

    async def start(self) -> None:
        """Start the Telegram bot with polling."""
        # Initialize agent with this channel for status updates
        await self.initialize_agent_with_channel()

        self.application = Application.builder().token(self.token).build()

        # Register handlers
        self.application.add_handler(CommandHandler("start", self._start_command))
        self.application.add_handler(CommandHandler("help", self._help_command))
        self.application.add_handler(CommandHandler("reset", self._reset_command))
        self.application.add_handler(CommandHandler("remember", self._remember_command))
        self.application.add_handler(CommandHandler("debug", self._debug_command))
        # Management commands
        self.application.add_handler(CommandHandler("mem", mem_command))
        self.application.add_handler(CommandHandler("vs", vs_command))
        self.application.add_handler(CommandHandler("db", db_command))
        self.application.add_handler(CommandHandler("file", file_command))
        self.application.add_handler(CommandHandler("meta", meta_command))
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._message_handler)
        )
        # File upload handlers (documents, photos)
        self.application.add_handler(
            MessageHandler(filters.Document.ALL | filters.PHOTO, self._file_handler)
        )

        # Note: Checkpoint sanitization now happens automatically via SanitizingCheckpointSaver
        # No need for startup cleanup - corrupted messages are sanitized on load

        # Start polling
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling(drop_pending_updates=True)

    async def stop(self) -> None:
        """Stop the Telegram bot gracefully."""
        if self.application:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()

    @staticmethod
    def _convert_markdown_to_telegram(text: str) -> str:
        """Convert standard markdown to Telegram markdown format.

        Telegram markdown uses:
        - *bold* (not **bold**)
        - _italic_ (not *italic*)
        - `code` (same)
        - ```pre``` (same)

        Also handles HTML-style bold/italic that LLMs sometimes use.
        """
        # Use placeholder approach to handle the **bold** -> *bold* -> shouldn't become _italic_
        # problem. We process bold patterns first, protect the result, then do italic.
        # Use Unicode \x00 delimiters that won't appear in normal text.

        placeholder_count = [0]  # Use list to allow modification in nested function

        def protect_bold(content):
            placeholder_count[0] += 1
            return f'\x00BOLD{placeholder_count[0]}\x00{content}\x00END{placeholder_count[0]}\x00'

        # Step 1: Convert **bold** to protected placeholder
        text = re.sub(r'\*\*(.+?)\*\*', lambda m: protect_bold(m.group(1)), text)

        # Step 2: Convert __bold__ to protected placeholder (skip if already a placeholder)
        # Only match __text__ that doesn't contain \x00
        text = re.sub(r'__([^\x00]+?)__', lambda m: protect_bold(m.group(1)), text)

        # Step 3: NOW convert *italic* to _italic_
        # This won't match our placeholders because they use \x00 not *
        text = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'_\1_', text)

        # Step 4: Restore protected bold (convert placeholder to *bold*)
        text = re.sub(r'\x00BOLD\d+\x00(.+?)\x00END\d+\x00', r'*\1*', text)

        # Step 5: HTML tags to markdown
        text = re.sub(r'<b>(.+?)</b>', r'*\1*', text, flags=re.IGNORECASE)
        text = re.sub(r'<strong>(.+?)</strong>', r'*\1*', text, flags=re.IGNORECASE)
        text = re.sub(r'<i>(.+?)</i>', r'_\1_', text, flags=re.IGNORECASE)
        text = re.sub(r'<em>(.+?)</em>', r'_\1_', text, flags=re.IGNORECASE)
        text = re.sub(r'<code>(.+?)</code>', r'`\1`', text, flags=re.IGNORECASE)
        text = re.sub(r'<pre>(.+?)</pre>', r'```\1```', text, flags=re.IGNORECASE | re.DOTALL)

        return text

    # Telegram message length limit
    MAX_MESSAGE_LENGTH = 4096

    async def send_message(
        self,
        conversation_id: str,
        content: str,
        parse_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Send a message to a Telegram chat.

        Splits messages longer than MAX_MESSAGE_LENGTH into multiple messages.
        Converts standard markdown to Telegram markdown format.
        Falls back to plain text if markdown parsing fails.
        """
        if not self.application:
            return

        # Convert markdown to Telegram format
        content = self._convert_markdown_to_telegram(content)
        # Clean any problematic characters that could cause parse errors
        content = self._clean_markdown(content)

        # Handle long messages by splitting them
        if len(content) > self.MAX_MESSAGE_LENGTH:
            await self._send_long_message(conversation_id, content, **kwargs)
        else:
            await self._send_with_fallback(
                conversation_id, content, parse_mode or 'Markdown', **kwargs
            )

    async def _send_with_fallback(
        self,
        conversation_id: str,
        content: str,
        parse_mode: str,
        **kwargs: Any,
    ) -> None:
        """Send message with markdown, falling back to plain text on parse error."""
        try:
            await self.application.bot.send_message(
                chat_id=conversation_id,
                text=content,
                parse_mode=parse_mode,
                **kwargs,
            )
        except BadRequest as e:
            if "can't parse entities" in str(e).lower() or "can't find end" in str(e).lower():
                # Markdown parsing failed - retry without formatting
                # Strip markdown special characters for cleaner plain text
                plain_text = self._strip_markdown(content)
                await self.application.bot.send_message(
                    chat_id=conversation_id,
                    text=plain_text,
                    parse_mode=None,  # Plain text
                    **kwargs,
                )
            else:
                raise  # Re-raise if it's a different BadRequest error

    def _strip_markdown(self, text: str) -> str:
        """Strip markdown special characters for plain text fallback."""
        # Remove bold/italic markers
        text = re.sub(r'\*([^*]+)\*', r'\1', text)  # *italic*
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # **bold**
        text = re.sub(r'_([^_]+)_', r'\1', text)  # _italic_
        text = re.sub(r'__([^_]+)__', r'\1', text)  # __bold__
        # Remove code blocks
        text = re.sub(r'`([^`]+)`', r'\1', text)  # `code`
        text = re.sub(r'```(.+?)```', r'\1', text, flags=re.DOTALL)  # ```pre```
        return text

    async def _send_long_message(
        self,
        conversation_id: str,
        content: str,
        **kwargs: Any,
    ) -> None:
        """Send a long message by splitting it into chunks.

        Tries to split at newlines to avoid breaking mid-sentence.
        Falls back to plain text if markdown parsing fails.
        """
        chunks = []
        current_chunk = ""

        for line in content.split('\n'):
            # If adding this line would exceed the limit
            if len(current_chunk) + len(line) + 1 > self.MAX_MESSAGE_LENGTH:
                if current_chunk:
                    chunks.append(current_chunk.rstrip())
                # If a single line is too long, force split it
                if len(line) > self.MAX_MESSAGE_LENGTH:
                    for i in range(0, len(line), self.MAX_MESSAGE_LENGTH):
                        chunks.append(line[i:i + self.MAX_MESSAGE_LENGTH])
                    current_chunk = ""
                else:
                    current_chunk = line + "\n"
            else:
                current_chunk += line + "\n"

        # Add the last chunk
        if current_chunk:
            chunks.append(current_chunk.rstrip())

        # Send each chunk
        for i, chunk in enumerate(chunks, 1):
            if chunk:  # Only send non-empty chunks
                await self._send_with_fallback(
                    conversation_id, chunk, 'Markdown', **kwargs
                )

    async def send_status(
        self,
        conversation_id: str,
        message: str,
        update: bool = True,
    ) -> None:
        """
        Send a status update with message editing for cleaner UX.

        In verbose mode (enabled via /debug command): always sends new messages.
        In normal mode: edits previous status message to avoid clutter.

        Args:
            conversation_id: Target chat ID.
            message: Status message to send.
            update: If True, try to edit previous status message (ignored in verbose mode).
        """
        import logging
        logger = logging.getLogger(__name__)

        if not self.application:
            logger.warning(f"send_status: no application")
            return

        # Convert conversation_id to int for Telegram API
        chat_id = int(conversation_id) if isinstance(conversation_id, str) else conversation_id

        # Check if this chat has verbose debug mode enabled
        verbose_mode = chat_id in self._debug_chats

        if verbose_mode:
            # Verbose mode: always send new messages (don't edit)
            try:
                msg = await self.application.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                )
                logger.info(f"[VERBOSE] Sent status to {chat_id}: {message}")
            except Exception as e:
                logger.error(f"Failed to send status message to {chat_id}: {e}")
            return

        # Normal mode: try to edit existing message
        if update and conversation_id in self._status_messages:
            # Try to edit existing status message
            message_id = self._status_messages[conversation_id]
            try:
                result = await self.application.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=message,
                )
                logger.info(f"Edited status message {message_id} for {conversation_id}: {message}")
                return
            except BadRequest as e:
                # Message might be too old or deleted - remove and send new
                logger.warning(f"BadRequest editing status message {message_id}: {e}, sending new")
                del self._status_messages[conversation_id]
            except Exception as e:
                # Other errors - fall through to sending new message
                logger.warning(f"Error editing status message {message_id}: {e}, sending new")
                del self._status_messages[conversation_id]

        # Send new status message (normal mode)
        try:
            msg = await self.application.bot.send_message(
                chat_id=chat_id,
                text=message,
            )
            # Track for future edits
            self._status_messages[conversation_id] = msg.message_id
            logger.info(f"Sent new status message {msg.message_id} to {conversation_id}: {message}")
        except Exception as e:
            logger.error(f"Failed to send status message to {conversation_id}: {e}")

    async def handle_message(self, message: MessageFormat) -> None:
        """Handle incoming message through the agent."""
        import time
        request_start = time.time()

        thread_id = self.get_thread_id(message)
        lock = self._get_thread_lock(thread_id)

        # Use per-thread lock to prevent concurrent message interleaving
        async with lock:
            # Task to keep sending typing action while processing
            typing_task = None

            async def _keep_typing():
                """Keep sending typing action every 4 seconds (Telegram expires after ~5s)."""
                while True:
                    try:
                        await self.application.bot.send_chat_action(
                            chat_id=message.conversation_id,
                            action="typing"
                        )
                        await asyncio.sleep(4)
                    except Exception:
                        break  # Stop if bot is shutting down or chat is unavailable

            try:
                # Start typing indicator in background
                typing_task = asyncio.create_task(_keep_typing())
                await self.application.bot.send_chat_action(
                    chat_id=message.conversation_id,
                    action="typing"
                )

                # Note: Checkpoint sanitization now happens automatically in the checkpointer
                # No need for pre-check here - SanitizingCheckpointSaver handles it on load

                # Stream agent response
                messages, metadata = await self.stream_agent_response(message)

                print(f"[DEBUG] Received {len(messages)} messages from agent")
                for i, msg in enumerate(messages):
                    msg_type = type(msg).__name__
                    has_content = hasattr(msg, "content") and bool(msg.content)
                    has_tool_calls = hasattr(msg, "tool_calls") and bool(msg.tool_calls)
                    content_preview = (msg.content[:100] if hasattr(msg, "content") and msg.content else "")
                    print(f"[DEBUG]   Message {i}: type={msg_type}, has_content={has_content}, has_tool_calls={has_tool_calls}, content='{content_preview}'")

                # Send responses back (time this - it's Telegram API overhead)
                post_agent_start = time.time()
                for msg in messages:
                    if hasattr(msg, "content") and msg.content:
                        # send_message will handle markdown conversion
                        await self.send_message(message.conversation_id, msg.content)
                post_agent_elapsed = time.time() - post_agent_start
                logger.info(f"Post-agent (send to Telegram): {post_agent_elapsed:.2f}s")

                # Determine reason for empty response based on events
                event_types = metadata.get("event_types", [])
                event_keys = metadata.get("event_keys", [])

                # If no messages were returned, send a fallback with reason
                if not messages:
                    print("[DEBUG] No messages from agent - determining reason...")

                    # Check limit info from metadata
                    limit_info = metadata.get("limit_info", {})
                    has_model_limit = any("ModelCallLimit" in k for k in limit_info.keys())
                    has_tool_limit = any("ToolCallLimit" in k for k in limit_info.keys())

                    if has_model_limit:
                        # Extract limit details
                        model_limit_key = next(k for k in limit_info.keys() if "ModelCallLimit" in k)
                        limit_msg = limit_info[model_limit_key]["message"]
                        print(f"[DEBUG] Model limit hit: {limit_msg}")

                        await self.send_message(
                            message.conversation_id,
                            f"⚠️ *Model call limit reached*\n\n"
                            f"{limit_msg}\n\n"
                            f"Current config (config.yaml):\n"
                            f"• model_call_limit: {settings.MW_MODEL_CALL_LIMIT} (per message)\n\n"
                            f"Please try a simpler task or send /reset to start fresh."
                        )
                    elif has_tool_limit:
                        # Extract limit details
                        tool_limit_key = next(k for k in limit_info.keys() if "ToolCallLimit" in k)
                        limit_msg = limit_info[tool_limit_key]["message"]
                        print(f"[DEBUG] Tool limit hit: {limit_msg}")

                        await self.send_message(
                            message.conversation_id,
                            f"⚠️ *Tool call limit reached*\n\n"
                            f"{limit_msg}\n\n"
                            f"Current config (config.yaml):\n"
                            f"• tool_call_limit: {settings.MW_TOOL_CALL_LIMIT} (per message)\n\n"
                            f"Please try a simpler task or send /reset to start fresh."
                        )
                    elif metadata.get("event_count", 0) <= 5:
                        await self.send_message(
                            message.conversation_id,
                            "⚠️ *Agent stopped early*\n\n"
                            "The agent didn't generate a response. This could be due to a configuration limit or state issue.\n\n"
                            "Try sending /reset to start fresh."
                        )
                    else:
                        await self.send_message(
                            message.conversation_id,
                            "I didn't generate a response. Please try again."
                        )

                # Check if we only got tool calls but no content response
                has_content_msg = any(
                    hasattr(msg, "content") and msg.content
                    for msg in messages
                )
                if messages and not has_content_msg:
                    print(f"[DEBUG] Got {len(messages)} tool-call messages but no content response")
                    await self.send_message(
                        message.conversation_id,
                        "I executed some tools but didn't generate a final response. "
                        "This might be due to an agent issue or limit. Please try again or send /reset."
                    )

            except Exception as e:
                import traceback
                traceback.print_exc()

                error_str = str(e)

                # Only clear checkpoint on corruption errors, not all errors
                if self._is_corruption_error(error_str):
                    thread_id = self.get_thread_id(message)
                    await self._clear_checkpoint(thread_id)
                    await self.send_message(
                        message.conversation_id,
                        "🔄 *Conversation auto-reset due to state error*\n\n"
                        "The corrupted conversation history has been cleared. Please send your message again.\n\n"
                        "Your data is preserved: • Files  • VS  • DB tables"
                    )
                else:
                    # For other errors, just report them - don't reset
                    await self.send_message(
                        message.conversation_id,
                        f"Sorry, an error occurred: {e}",
                    )
            finally:
                # Stop typing indicator
                if typing_task:
                    typing_task.cancel()
                    try:
                        await typing_task
                    except asyncio.CancelledError:
                        pass

                # Clear status message ID so next user message creates a new status
                self._status_messages.pop(message.conversation_id, None)

                # Log total request latency
                total_elapsed = time.time() - request_start
                logger.info(f"Total request latency for {message.conversation_id}: {total_elapsed:.1f}s")

    def _clean_markdown(self, text: str) -> str:
        """Clean markdown for Telegram compatibility.

        Escapes special characters that could cause parse errors:
        - * _ ~ ` > # + - = | { } . !
        Only escapes when they would create invalid entities.
        """
        # Escape backslash first to avoid double-escaping
        text = text.replace('\\', '\\\\')

        # For unmatched * or _ that could cause parse errors:
        # Count total * and _ - if odd number, we have an unmatched one
        # We'll escape them in "safe" contexts (not part of valid pairs)

        # Simple approach: escape * and _ that appear in risky positions
        # This is conservative but safe
        chars_to_escape = ['*', '_']

        # Find positions of each character and escape unmatched ones
        for char in chars_to_escape:
            count = text.count(char)
            if count % 2 == 1:
                # Odd count - escape the last occurrence
                # Find all positions and escape the last one
                last_pos = text.rfind(char)
                if last_pos != -1:
                    text = text[:last_pos] + '\\' + char + text[last_pos + 1:]

        return text

    async def _start_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Handle /start command."""
        welcome_message = (
            f"👋 Hi! I'm {settings.AGENT_NAME}, an AI assistant with access to various tools.\n\n"
            "I can help you with:\n"
            "• 🌐 Searching the web\n"
            "• 📄 Reading and writing files\n"
            "• 🔢 Calculations\n"
            "• And more!\n\n"
            "Just send me a message to get started. Use /reset to clear conversation history."
        )
        await update.message.reply_text(welcome_message)

    async def _help_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Handle /help command."""
        help_message = (
            f"🤖 *{settings.AGENT_NAME} Help*\n\n"
            "*Basic Commands:*\n"
            "/start - Start the bot\n"
            "/help - Show this help message\n"
            "/reset - Clear conversation history\n"
            "/remember <content> - Quick store a memory\n"
            "/debug - Toggle verbose status (see LLM calls & tools)\n\n"
            "*Memory* (/mem):\n"
            "• `/mem` - List all memories\n"
            "• `/mem search <query>` - Search memories\n"
            "• `/mem forget <id|key>` - Forget a memory\n\n"
            "*Vector Store* (/vs):\n"
            "• `/vs` - List tables\n"
            "• `/vs store <table> <json>` - Store docs\n"
            "• `/vs search <query>` - Search VS\n\n"
            "*Database* (/db):\n"
            "• `/db` - List tables\n"
            "• `/db create <table> <json>` - Create table\n"
            "• `/db query <sql>` - Run SQL query\n\n"
            "*Files* (/file):\n"
            "• `/file` - List files\n"
            "• `/file read <path>` - Read file\n"
            "• `/file write <path> <text>` - Write file\n\n"
            "*What I can do:*\n"
            "• Search the web • Read/write files • Calculations\n"
            "• Remember facts • Use tools to help you\n\n"
            "*Tip:* Try /mem, /vs, /db, /file, or /debug alone to see all options"
        )
        await update.message.reply_text(help_message, parse_mode="Markdown")

    async def _reset_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Handle /reset command to clear conversation."""
        try:
            # Actually clear the checkpoint from database
            thread_id = f"telegram:{update.effective_chat.id}"

            # Use global checkpointer if available
            try:
                from cassey.storage.checkpoint import get_async_checkpointer

                checkpointer = await get_async_checkpointer()
                if hasattr(checkpointer, "conn") and checkpointer.conn:
                    await checkpointer.conn.execute(
                        "DELETE FROM checkpoints WHERE thread_id = $1",
                        thread_id,
                    )
            except Exception:
                pass  # Fall through to success message

            await update.message.reply_text(
                "🔄 Conversation history cleared!\n\n"
                "You can start fresh. Note that VS and file data are preserved."
            )
        except Exception as e:
            await update.message.reply_text(f"🔄 Reset attempted. If issues persist, try: {e}")

    async def _remember_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Handle /remember command to store a memory."""
        if not update.message:
            return

        try:
            # Get the text after /remember command
            args = context.args if context.args else []

            if not args:
                await update.message.reply_text(
                    "📝 *Memory Command*\n\n"
                    "Usage: /remember <content>\n\n"
                    "Examples:\n"
                    "• /remember I prefer Python over JavaScript\n"
                    "• /remember My timezone is America/New_York\n"
                    "• /remember I work 9-5 EST\n\n"
                    "The memory will be stored and can be retrieved in future conversations.",
                    parse_mode="Markdown"
                )
                return

            # Join args to get the full content
            content = " ".join(args)

            # Store the memory
            from cassey.storage.mem_storage import get_mem_storage
            from cassey.storage.file_sandbox import set_thread_id

            # Set thread_id context
            thread_id = f"telegram:{update.effective_chat.id}"
            set_thread_id(thread_id)

            try:
                storage = get_mem_storage()
                memory_id = storage.create_memory(
                    content=content,
                    memory_type="note",  # Default type for /remember
                    confidence=1.0,  # High confidence for explicit memories
                )

                await update.message.reply_text(
                    f"💾 *Memory saved!*\n\n"
                    f"Content: {content[:200]}{'...' if len(content) > 200 else ''}\n\n"
                    f"I'll remember this for future conversations.",
                    parse_mode="Markdown"
                )
            finally:
                from cassey.storage.file_sandbox import clear_thread_id
                clear_thread_id()

        except Exception as e:
            import traceback
            traceback.print_exc()
            await update.message.reply_text(f"Sorry, failed to save memory: {e}")

    async def _debug_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Handle /debug command to toggle verbose status mode."""
        if not update.message or not update.effective_chat:
            return

        chat_id = update.effective_chat.id
        args = context.args if context.args else []

        if not args:
            # No args - show current status
            is_debug = chat_id in self._debug_chats
            status = "✅ ON (verbose)" if is_debug else "❌ OFF (default)"
            await update.message.reply_text(
                f"🔍 *Debug Status*: {status}\n\n"
                f"Usage:\n"
                f"• `/debug on` - Enable verbose status (see all LLM calls and tools)\n"
                f"• `/debug off` - Disable (clean mode, status edited in place)\n"
                f"• `/debug toggle` - Toggle debug mode",
                parse_mode="Markdown"
            )
            return

        command = args[0].lower()

        if command in ("on", "enable", "1", "true"):
            self._debug_chats.add(chat_id)
            await update.message.reply_text(
                "✅ *Verbose debug enabled*\n\n"
                "All LLM calls and tool executions will be shown as separate messages.\n\n"
                "Use `/debug off` to disable.",
                parse_mode="Markdown"
            )
        elif command in ("off", "disable", "0", "false"):
            self._debug_chats.discard(chat_id)
            # Also clear any tracked status message for this chat
            self._status_messages.pop(str(chat_id), None)
            await update.message.reply_text(
                "❌ *Verbose debug disabled*\n\n"
                "Status updates will be edited in place (clean mode).",
                parse_mode="Markdown"
            )
        elif command in ("toggle", "switch"):
            if chat_id in self._debug_chats:
                self._debug_chats.discard(chat_id)
                self._status_messages.pop(str(chat_id), None)
                await update.message.reply_text("🔍 Debug mode: OFF", parse_mode="Markdown")
            else:
                self._debug_chats.add(chat_id)
                await update.message.reply_text("🔍 Debug mode: ON", parse_mode="Markdown")
        else:
            await update.message.reply_text(
                f"Unknown option: {command}\n\n"
                f"Use: `/debug on|off|toggle`",
                parse_mode="Markdown"
            )

    async def _clear_checkpoint(self, thread_id: str) -> bool:
        """
        Clear the checkpoint for a given thread_id.

        Args:
            thread_id: Thread ID to clear

        Returns:
            True if successful, False otherwise
        """
        try:
            # Direct database deletion - most reliable method
            import os
            from cassey.config.settings import settings

            conn_str = (
                f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@"
                f"{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
            )

            # Use subprocess to call psql directly
            import subprocess
            result = subprocess.run(
                [
                    "psql", conn_str, "-c",
                    f"DELETE FROM checkpoints WHERE thread_id = '{thread_id}'"
                ],
                capture_output=True,
                text=True,
                timeout=5
            )

            return result.returncode == 0

        except Exception as e:
            print(f"Failed to clear checkpoint: {e}")
            return False

    async def _message_handler(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Handle incoming text messages."""
        if not update.message or not update.message.text:
            return

        try:
            # Create MessageFormat with Telegram timestamp
            message = MessageFormat(
                content=update.message.text,
                user_id=self.format_user_id(str(update.effective_user.id)),
                conversation_id=str(update.effective_chat.id),
                message_id=str(update.message.message_id),
                metadata={
                    "username": update.effective_user.username,
                    "first_name": update.effective_user.first_name,
                    "chat_type": update.effective_chat.type,
                    "telegram_date": update.message.date.isoformat() if update.message.date else None,
                },
            )

            # Handle through agent (typing indicator is sent in handle_message)
            await self.handle_message(message)
        except Exception as e:
            import traceback
            traceback.print_exc()
            error_msg = str(e) if str(e) else f"{type(e).__name__}"
            await update.message.reply_text(f"Sorry, an error occurred: {error_msg}")

    @staticmethod
    def get_thread_id(message: MessageFormat) -> str:
        """Generate thread_id for Telegram conversations."""
        return f"telegram:{message.conversation_id}"

    async def _file_handler(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Handle incoming file uploads (documents and photos)."""
        if not update.message:
            return

        try:
            from pathlib import Path
            from cassey.storage.file_sandbox import set_thread_id
            from cassey.storage.group_storage import (
                ensure_thread_group,
                set_group_id as set_workspace_context,
            )
            from cassey.config.settings import settings

            # Get thread_id for file sandbox
            thread_id = self.get_thread_id(MessageFormat(
                content="",  # Dummy content for thread_id generation
                user_id=self.format_user_id(str(update.effective_user.id)),
                conversation_id=str(update.effective_chat.id),
                message_id=str(update.message.message_id),
            ))
            set_thread_id(thread_id)

            # Set up user_id context (individual mode, not personal groups)
            # This ensures files are stored in the user directory
            from cassey.storage.group_storage import set_user_id
            user_id = self.format_user_id(str(update.effective_user.id))
            set_user_id(user_id)

            # Use user-based path (matches agent's file tools)
            user_dir = settings.get_user_files_path(user_id)
            user_dir.mkdir(parents=True, exist_ok=True)

            attachment = None
            file_info = None

            # Handle document (PDF, Office files, etc.)
            if update.message.document:
                document = update.message.document
                file_info = await document.get_file()

                # Check file size (max 10MB)
                if document.file_size and document.file_size > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
                    await update.message.reply_text(
                        f"File too large. Maximum size is {settings.MAX_FILE_SIZE_MB}MB."
                    )
                    return

                # Check file extension
                file_name = document.file_name or f"document_{document.file_id}"
                # Sanitize filename - use only the basename to prevent path traversal
                file_name = Path(file_name).name
                file_ext = Path(file_name).suffix.lower()

                if file_ext and file_ext not in settings.ALLOWED_FILE_EXTENSIONS:
                    allowed = ", ".join(sorted(settings.ALLOWED_FILE_EXTENSIONS))
                    await update.message.reply_text(
                        f"File type '{file_ext}' not allowed. Allowed types: {allowed}"
                    )
                    return

                # Download file to user directory (individual mode, not personal groups)
                local_path = user_dir / file_name
                # Use download_to_drive() - download() is deprecated
                downloaded_path = await file_info.download_to_drive(local_path)

                attachment = {
                    "type": "document",
                    "file_name": file_name,
                    "file_path": str(local_path),
                    "file_size": document.file_size,
                    "mime_type": document.mime_type,
                }

            # Handle photo
            elif update.message.photo:
                # Get the largest photo (last in list)
                photo = update.message.photo[-1]
                file_info = await photo.get_file()

                # Check file size
                if photo.file_size and photo.file_size > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
                    await update.message.reply_text(
                        f"Photo too large. Maximum size is {settings.MAX_FILE_SIZE_MB}MB."
                    )
                    return

                # Generate file name (sanitized - no path traversal possible)
                file_name = f"photo_{photo.file_id}.jpg"
                local_path = user_dir / file_name

                # Download photo using download_to_drive()
                downloaded_path = await file_info.download_to_drive(local_path)

                attachment = {
                    "type": "photo",
                    "file_name": file_name,
                    "file_path": str(local_path),
                    "file_size": photo.file_size,
                    "mime_type": "image/jpeg",
                }

            if attachment:
                # Build message content with file info
                caption = update.message.caption or ""
                content = f"File uploaded: {attachment['file_name']}"
                if caption:
                    content += f"\nCaption: {caption}"
                content += f"\n\nYou can now ask me to analyze this file."

                # Create MessageFormat with attachment
                message = MessageFormat(
                    content=content,
                    user_id=self.format_user_id(str(update.effective_user.id)),
                    conversation_id=str(update.effective_chat.id),
                    message_id=str(update.message.message_id),
                    attachments=[attachment],
                    metadata={
                        "username": update.effective_user.username,
                        "first_name": update.effective_user.first_name,
                        "chat_type": update.effective_chat.type,
                    },
                )

                # Handle through agent (typing indicator is sent in handle_message)
                await self.handle_message(message)
            else:
                await update.message.reply_text("Could not process the uploaded file.")

        except Exception as e:
            import traceback
            traceback.print_exc()
            error_msg = str(e) if str(e) else f"{type(e).__name__}"
            await update.message.reply_text(f"Sorry, an error occurred: {error_msg}")
        finally:
            # Clean up thread_id and group_id to avoid leaking context
            from cassey.storage.file_sandbox import clear_thread_id
            from cassey.storage.group_storage import clear_group_id as clear_workspace_context
            clear_thread_id()
            clear_workspace_context()
