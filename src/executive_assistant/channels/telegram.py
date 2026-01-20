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
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Runnable

from executive_assistant.channels.base import BaseChannel, MessageFormat
from executive_assistant.channels.management_commands import (
    mem_command,
    reminder_command,
    vs_command,
    db_command,
    file_command,
    meta_command,
)
from executive_assistant.config.settings import settings
from executive_assistant.storage.helpers import sanitize_thread_id_to_user_id
from executive_assistant.storage.user_registry import UserRegistry
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
        self._queue_locks: dict[str, asyncio.Lock] = {}
        self._pending_messages: dict[str, list[MessageFormat]] = {}
        self._inflight_tasks: dict[str, asyncio.Task] = {}
        self._status_messages: dict[str, int] = {}  # conversation_id -> message_id for editing
        self._todo_messages: dict[str, int] = {}  # conversation_id -> message_id for todo edits
        self._debug_chats: set[int] = set()  # chat IDs with verbose debug mode enabled

    def _get_thread_lock(self, thread_id: str) -> asyncio.Lock:
        """Get or create a lock for the given thread_id."""
        if thread_id not in self._thread_locks:
            self._thread_locks[thread_id] = asyncio.Lock()
        return self._thread_locks[thread_id]

    def _get_queue_lock(self, thread_id: str) -> asyncio.Lock:
        """Get or create a queue lock for the given thread_id."""
        if thread_id not in self._queue_locks:
            self._queue_locks[thread_id] = asyncio.Lock()
        return self._queue_locks[thread_id]

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
        self.application.add_handler(CommandHandler("reset", self._reset_command))
        self.application.add_handler(CommandHandler("remember", self._remember_command))
        self.application.add_handler(CommandHandler("debug", self._debug_command))
        # Management commands
        self.application.add_handler(CommandHandler("mem", mem_command))
        self.application.add_handler(CommandHandler("reminder", reminder_command))
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
        print("DEBUG: TelegramChannel: About to initialize...", flush=True)
        await self.application.initialize()
        print("DEBUG: TelegramChannel: Initialized", flush=True)
        await self.application.start()
        print("DEBUG: TelegramChannel: Application started", flush=True)
        await self.application.updater.start_polling(drop_pending_updates=True)
        print("DEBUG: TelegramChannel: Polling started", flush=True)

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
                if "message is not modified" in str(e).lower():
                    logger.info(
                        f"Status message {message_id} for {conversation_id} unchanged; skipping update"
                    )
                    return
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

    async def send_todo(
        self,
        conversation_id: str,
        message: str,
        update: bool = True,
    ) -> None:
        """
        Send a todo update with message editing for cleaner UX.

        Todo updates are separate from status messages.
        """
        import logging
        logger = logging.getLogger(__name__)

        if not self.application:
            logger.warning("send_todo: no application")
            return

        chat_id = int(conversation_id) if isinstance(conversation_id, str) else conversation_id

        if update and conversation_id in self._todo_messages:
            message_id = self._todo_messages[conversation_id]
            try:
                await self.application.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=message,
                )
                logger.info(f"Edited todo message {message_id} for {conversation_id}")
                return
            except BadRequest as e:
                if "message is not modified" in str(e).lower():
                    logger.info(
                        f"Todo message {message_id} for {conversation_id} unchanged; skipping update"
                    )
                    return
                logger.warning(f"BadRequest editing todo message {message_id}: {e}, sending new")
                del self._todo_messages[conversation_id]
            except Exception as e:
                logger.warning(f"Error editing todo message {message_id}: {e}, sending new")
                del self._todo_messages[conversation_id]

        try:
            msg = await self.application.bot.send_message(
                chat_id=chat_id,
                text=message,
            )
            self._todo_messages[conversation_id] = msg.message_id
            logger.info(f"Sent new todo message {msg.message_id} to {conversation_id}")
        except Exception as e:
            logger.error(f"Failed to send todo message to {conversation_id}: {e}")

    async def handle_message(self, message: MessageFormat) -> None:
        """Handle incoming message through the agent with real-time streaming."""
        thread_id = self.get_thread_id(message)
        queue_lock = self._get_queue_lock(thread_id)
        async with queue_lock:
            self._pending_messages.setdefault(thread_id, []).append(message)
            inflight = self._inflight_tasks.get(thread_id)
            if inflight and not inflight.done():
                inflight.cancel()
                await self.send_message(
                    message.conversation_id,
                    "👍 Got it — I’ll merge this with your current request.",
                )
                self._inflight_tasks[thread_id] = asyncio.create_task(
                    self._process_pending_messages(thread_id)
                )
            elif inflight is None or inflight.done():
                self._inflight_tasks[thread_id] = asyncio.create_task(
                    self._process_pending_messages(thread_id)
                )

    async def _process_pending_messages(self, thread_id: str) -> None:
        """Process queued messages for a thread in a single merged run."""
        exec_lock = self._get_thread_lock(thread_id)
        queue_lock = self._get_queue_lock(thread_id)

        async with exec_lock:
            while True:
                async with queue_lock:
                    batch = self._pending_messages.get(thread_id, []).copy()
                    self._pending_messages[thread_id] = []

                if not batch:
                    break

                try:
                    await self._run_agent_with_messages(thread_id, batch)
                except asyncio.CancelledError:
                    # Requeue batch if we were cancelled mid-run.
                    async with queue_lock:
                        self._pending_messages[thread_id] = batch + self._pending_messages.get(thread_id, [])
                    raise
                except Exception:
                    # Errors are handled inside _run_agent_with_messages.
                    continue
        self._inflight_tasks.pop(thread_id, None)

    async def _run_agent_with_messages(
        self,
        thread_id: str,
        batch: list[MessageFormat],
    ) -> None:
        """Run the agent for a merged batch of user messages."""
        import time
        request_start = time.time()
        typing_task = None

        async def _keep_typing():
            """Keep sending typing action every 4 seconds (Telegram expires after ~5s)."""
            while True:
                try:
                    await self.application.bot.send_chat_action(
                        chat_id=batch[-1].conversation_id,
                        action="typing"
                    )
                    await asyncio.sleep(4)
                except Exception:
                    break  # Stop if bot is shutting down or chat is unavailable

        try:
            # Reset todo message per request to keep a fresh todo thread.
            self._todo_messages.pop(batch[-1].conversation_id, None)

            # Start typing indicator in background
            typing_task = asyncio.create_task(_keep_typing())
            await self.application.bot.send_chat_action(
                chat_id=batch[-1].conversation_id,
                action="typing"
            )

            # Set up context
            from executive_assistant.storage.file_sandbox import set_thread_id
            from executive_assistant.storage.group_storage import (
                ensure_thread_group,
                set_group_id as set_workspace_context,
                set_user_id as set_workspace_user_id,
                clear_group_id as clear_workspace_context,
            )
            channel = self.__class__.__name__.lower().replace("channel", "")
            config = {"configurable": {"thread_id": thread_id}}

            # Set thread_id context for file sandbox operations
            set_thread_id(thread_id)

            # Convert thread_id to user_id (identity_id) for storage and permission checks
            from executive_assistant.storage.helpers import sanitize_thread_id_to_user_id
            user_id_for_storage = sanitize_thread_id_to_user_id(thread_id)

            # Ensure group exists and set group_id context only for group chats
            chat_type = batch[-1].metadata.get("chat_type") if batch[-1].metadata else None
            is_group_chat = chat_type in {"group", "supergroup"}
            if is_group_chat:
                group_id = await ensure_thread_group(thread_id, user_id_for_storage)
                set_workspace_context(group_id)
            else:
                clear_workspace_context()
            set_workspace_user_id(user_id_for_storage)

            messages: list[HumanMessage] = []
            last_message_id = batch[-1].message_id
            for msg in batch:
                memories = self._get_relevant_memories(thread_id, msg.content)
                enhanced_content = self._inject_memories(msg.content, memories)
                messages.append(
                    HumanMessage(
                        content=enhanced_content,
                        additional_kwargs={"executive_assistant_message_id": msg.message_id},
                    )
                )

                # Log incoming message if audit is enabled
                if self.registry:
                    await self.registry.log_message(
                        conversation_id=thread_id,
                        user_id=msg.user_id,
                        channel=channel,
                        message=HumanMessage(content=enhanced_content),
                        message_id=msg.message_id,
                        metadata=msg.metadata,
                    )

            state = {
                "messages": messages,
                "run_model_call_count": 0,
                "run_tool_call_count": {},
                "thread_model_call_count": 0,
                "thread_tool_call_count": {},
                "todos": [],
            }

            # Stream agent responses and send IMMEDIATELY (no batching)
            agent_start = time.time()
            event_count = 0
            message_count = 0
            async for event in self.agent.astream(state, config):
                event_count += 1

                # Extract and send messages immediately as they arrive
                msgs = self._extract_messages_from_event(event)
                new_messages = self._get_new_ai_messages(msgs, last_message_id)
                for msg in new_messages:
                    if isinstance(msg, AIMessage) and hasattr(msg, "content") and msg.content:
                        message_count += 1
                        await self.send_message(batch[-1].conversation_id, msg.content)

                    if self.registry and (hasattr(msg, 'content') and msg.content or (hasattr(msg, 'tool_calls') and msg.tool_calls)):
                        await self.registry.log_message(
                            conversation_id=thread_id,
                            user_id=batch[-1].user_id,
                            channel=channel,
                            message=msg,
                        )

            agent_elapsed = time.time() - agent_start
            logger.info(f"Agent processing: {agent_elapsed:.2f}s, {event_count} events, {message_count} messages")

        except Exception as e:
            import traceback
            traceback.print_exc()
            error_str = str(e)

            if self._is_corruption_error(error_str):
                await self._clear_checkpoint(thread_id)
                await self.send_message(
                    batch[-1].conversation_id,
                    "🔄 *Conversation auto-reset due to state error*\n\n"
                    "The corrupted conversation history has been cleared. Please send your message again.\n\n"
                    "Your data is preserved: • Files  • VS  • DB tables"
                )
            else:
                await self.send_message(
                    batch[-1].conversation_id,
                    f"Sorry, an error occurred: {e}",
                )
        finally:
            if typing_task:
                typing_task.cancel()
                try:
                    await typing_task
                except asyncio.CancelledError:
                    pass

            # Clear status message ID so next user message creates a new status
            self._status_messages.pop(batch[-1].conversation_id, None)

            total_elapsed = time.time() - request_start
            logger.info(f"Total request latency for {batch[-1].conversation_id}: {total_elapsed:.1f}s")

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
                from executive_assistant.storage.checkpoint import get_async_checkpointer

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
            from executive_assistant.storage.mem_storage import get_mem_storage
            from executive_assistant.storage.file_sandbox import set_thread_id

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
                from executive_assistant.storage.file_sandbox import clear_thread_id
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
            from executive_assistant.config.settings import settings

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
        print(f"DEBUG: _message_handler called: update={update.update_id}, text={update.message.text if update.message else 'None'}", flush=True)
        if not update.message or not update.message.text:
            return

        try:
            # Auto-create identity for anonymous users
            thread_id = f"telegram:{update.effective_chat.id}"
            identity_id = sanitize_thread_id_to_user_id(thread_id)

            # Create identity record if it doesn't exist
            try:
                registry = UserRegistry()
                await registry.create_identity_if_not_exists(
                    thread_id=thread_id,
                    identity_id=identity_id,
                    channel="telegram"
                )
            except Exception as e:
                # Log but don't fail - user can still interact
                logger.warning(f"Failed to create identity for {thread_id}: {e}")

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
            # Auto-create identity for anonymous users
            thread_id = f"telegram:{update.effective_chat.id}"
            identity_id = sanitize_thread_id_to_user_id(thread_id)

            # Create identity record if it doesn't exist
            try:
                registry = UserRegistry()
                await registry.create_identity_if_not_exists(
                    thread_id=thread_id,
                    identity_id=identity_id,
                    channel="telegram"
                )
            except Exception as e:
                # Log but don't fail - user can still interact
                logger.warning(f"Failed to create identity for {thread_id}: {e}")

            from pathlib import Path
            from executive_assistant.storage.file_sandbox import set_thread_id
            from executive_assistant.storage.group_storage import (
                ensure_thread_group,
                set_group_id as set_workspace_context,
            )
            from executive_assistant.config.settings import settings

            # Get thread_id for file sandbox
            thread_id = self.get_thread_id(MessageFormat(
                content="",  # Dummy content for thread_id generation
                user_id=self.format_user_id(str(update.effective_user.id)),
                conversation_id=str(update.effective_chat.id),
                message_id=str(update.message.message_id),
            ))
            set_thread_id(thread_id)

            # Set up user_id context (individual mode, not personal groups)
            # Convert thread_id to user_id (identity_id) for storage operations
            from executive_assistant.storage.helpers import sanitize_thread_id_to_user_id
            user_id = sanitize_thread_id_to_user_id(thread_id)
            from executive_assistant.storage.group_storage import set_user_id
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
            from executive_assistant.storage.file_sandbox import clear_thread_id
            from executive_assistant.storage.group_storage import clear_group_id as clear_workspace_context
            clear_thread_id()
            clear_workspace_context()
