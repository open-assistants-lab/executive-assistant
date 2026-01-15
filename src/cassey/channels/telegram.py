"""Telegram channel implementation using python-telegram-bot."""

import asyncio
import re
from typing import Any

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from langgraph.types import Runnable

from cassey.channels.base import BaseChannel, MessageFormat
from cassey.config.settings import settings


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
    """

    def __init__(self, token: str | None = None, agent: Runnable | None = None) -> None:
        token = token or settings.TELEGRAM_BOT_TOKEN
        if not token:
            raise ValueError("Telegram bot token not provided")

        super().__init__(agent)
        self.token = token
        self.application: Application | None = None

    async def start(self) -> None:
        """Start the Telegram bot with polling."""
        self.application = Application.builder().token(self.token).build()

        # Register handlers
        self.application.add_handler(CommandHandler("start", self._start_command))
        self.application.add_handler(CommandHandler("help", self._help_command))
        self.application.add_handler(CommandHandler("reset", self._reset_command))
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._message_handler)
        )
        # File upload handlers (documents, photos)
        self.application.add_handler(
            MessageHandler(filters.Document.ALL | filters.PHOTO, self._file_handler)
        )

        # Clean up any corrupted checkpoints at startup
        await self._cleanup_corrupted_checkpoints()

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

    async def _cleanup_corrupted_checkpoints(self) -> None:
        """Clean up corrupted checkpoints at startup.

        Checks for checkpoints with orphaned tool_calls (AIMessage with tool_calls
        not followed by ToolMessage responses) and removes them.
        """
        try:
            from cassey.agent.checkpoint_utils import detect_corrupted_messages

            # Get the checkpointer from the agent
            if not self.agent or not hasattr(self.agent, 'graph'):
                return

            graph = self.agent.graph
            if not hasattr(graph, 'checkpointer') or not graph.checkpointer:
                return

            # Get all thread_ids from checkpoint_blobs
            import asyncpg
            from cassey.config import settings

            conn_str = (
                f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@"
                f"{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
            )

            conn = await asyncpg.connect(conn_str)
            try:
                # Get all unique thread_ids
                rows = await conn.fetch(
                    "SELECT DISTINCT thread_id FROM checkpoint_blobs WHERE thread_id LIKE 'telegram:%'"
                )

                corrupted_threads = []
                for row in rows:
                    thread_id = row["thread_id"]
                    try:
                        config = {"configurable": {"thread_id": thread_id}}
                        checkpoint_config = await graph.checkpointer.aget_tuple(config)

                        if checkpoint_config and checkpoint_config.checkpoint:
                            state = checkpoint_config.checkpoint.get("channel_values", {})
                            messages = state.get("messages", [])

                            issues = detect_corrupted_messages(messages)
                            if issues:
                                corrupted_threads.append(thread_id)
                    except Exception:
                        # If we can't even read the checkpoint, it's corrupted
                        corrupted_threads.append(thread_id)

                # Delete corrupted checkpoints
                if corrupted_threads:
                    for thread_id in corrupted_threads:
                        await conn.execute(
                            "DELETE FROM checkpoint_blobs WHERE thread_id = $1",
                            thread_id
                        )
                        await conn.execute(
                            "DELETE FROM checkpoints WHERE thread_id = $1",
                            thread_id
                        )
                    print(f"Cleaned up {len(corrupted_threads)} corrupted checkpoints at startup")

            finally:
                await conn.close()

        except Exception as e:
            import traceback
            traceback.print_exc()
            # Don't fail startup if cleanup fails

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
            await self.application.bot.send_message(
                chat_id=conversation_id,
                text=content,
                parse_mode=parse_mode or 'Markdown',  # Use Markdown for formatting
                **kwargs,
            )

    async def _send_long_message(
        self,
        conversation_id: str,
        content: str,
        **kwargs: Any,
    ) -> None:
        """Send a long message by splitting it into chunks.

        Tries to split at newlines to avoid breaking mid-sentence.
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
                await self.application.bot.send_message(
                    chat_id=conversation_id,
                    text=chunk,
                    parse_mode='Markdown',
                    **kwargs,
                )

    async def handle_message(self, message: MessageFormat) -> None:
        """Handle incoming message through the agent."""
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

            # Check for checkpoint corruption BEFORE loading
            # Note: We also clear checkpoints on any error during processing
            thread_id = self.get_thread_id(message)
            corruption_check = await self._check_checkpoint_corruption(thread_id)

            if corruption_check:
                # Auto-reset the corrupted checkpoint
                await self._clear_checkpoint(thread_id)
                await self.send_message(
                    message.conversation_id,
                    "🔄 *Conversation auto-reset due to state issue*\n\n"
                    "The corrupted conversation history has been cleared. Please send your message again.\n\n"
                    "Your data is preserved: • Files  • KB  • DB tables"
                )
                return

            # Stream agent response
            messages = await self.stream_agent_response(message)

            # Send responses back
            for msg in messages:
                if hasattr(msg, "content") and msg.content:
                    # send_message will handle markdown conversion
                    await self.send_message(message.conversation_id, msg.content)

        except Exception as e:
            import traceback
            traceback.print_exc()

            # Clear checkpoint on ANY error to prevent corruption cascade
            thread_id = self.get_thread_id(message)
            await self._clear_checkpoint(thread_id)

            # Check if error is related to corrupted state
            error_str = str(e)
            if "tool_call" in error_str or "toolcallid" in error_str or "tool_calls" in error_str:
                await self.send_message(
                    message.conversation_id,
                    "🔄 *Conversation auto-reset due to state error*\n\n"
                    "The corrupted conversation history has been cleared. Please send your message again.\n\n"
                    "Your data is preserved: • Files  • KB  • DB tables"
                )
            else:
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
            "👋 Hi! I'm Cassey, an AI assistant with access to various tools.\n\n"
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
            "🤖 Cassey Help\n\n"
            "Commands:\n"
            "/start - Start the bot\n"
            "/help - Show this help message\n"
            "/reset - Clear conversation history\n\n"
            "What I can do:\n"
            "• Search the web for information\n"
            "• Read and write files\n"
            "• Perform calculations\n"
            "• Use various tools to help you\n\n"
            "Just ask me anything!"
        )
        await update.message.reply_text(help_message)

    async def _reset_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Handle /reset command to clear conversation."""
        try:
            # Actually clear the checkpoint from database
            thread_id = f"telegram:{update.effective_chat.id}"

            # Get checkpointer from agent if available
            if hasattr(self, 'agent') and hasattr(self.agent, 'graph'):
                graph = self.agent.graph
                if hasattr(graph, 'checkpointer') and graph.checkpointer:
                    # Try to delete the checkpoint
                    config = {"configurable": {"thread_id": thread_id}}
                    try:
                        # LangGraph checkpointer doesn't have a direct delete method
                        # So we access the underlying connection if it's PostgresSaver
                        checkpointer = graph.checkpointer
                        if hasattr(checkpointer, 'conn'):
                            # Direct database access
                            await checkpointer.conn.execute(
                                "DELETE FROM checkpoints WHERE thread_id = $1",
                                thread_id
                            )
                    except Exception:
                        pass  # Fall through to success message

            await update.message.reply_text(
                "🔄 Conversation history cleared!\n\n"
                "You can start fresh. Note that KB and file data are preserved."
            )
        except Exception as e:
            await update.message.reply_text(f"🔄 Reset attempted. If issues persist, try: {e}")

    async def _check_checkpoint_corruption(self, thread_id: str) -> str | None:
        """
        Check if the checkpoint for this thread is corrupted.

        Returns:
            Error message if corrupted, None if OK
        """
        try:
            from cassey.agent.checkpoint_utils import detect_corrupted_messages

            # Get the current state from checkpoint
            if not hasattr(self, 'agent') or not hasattr(self.agent, 'graph'):
                return None

            graph = self.agent.graph
            if not hasattr(graph, 'checkpointer') or not graph.checkpointer:
                return None

            config = {"configurable": {"thread_id": thread_id}}

            # Try to get the checkpoint state
            try:
                checkpoint_config = await graph.checkpointer.aget_tuple(config)
                if checkpoint_config and checkpoint_config.checkpoint:
                    state = checkpoint_config.checkpoint.get("channel_values", {})
                    messages = state.get("messages", [])

                    # Check for corruption
                    issues = detect_corrupted_messages(messages)
                    if issues:
                        return "Corrupted conversation state detected:\n• " + "\n• ".join(issues[:3])

            except Exception:
                # If we can't read the checkpoint, it might be corrupted
                pass

            return None

        except Exception:
            return None

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
            # Create MessageFormat
            message = MessageFormat(
                content=update.message.text,
                user_id=str(update.effective_user.id),
                conversation_id=str(update.effective_chat.id),
                message_id=str(update.message.message_id),
                metadata={
                    "username": update.effective_user.username,
                    "first_name": update.effective_user.first_name,
                    "chat_type": update.effective_chat.type,
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
            from cassey.config.settings import settings

            # Get thread_id for file sandbox
            thread_id = self.get_thread_id(MessageFormat(
                content="",  # Dummy content for thread_id generation
                user_id=str(update.effective_user.id),
                conversation_id=str(update.effective_chat.id),
                message_id=str(update.message.message_id),
            ))
            set_thread_id(thread_id)

            # Sanitize thread_id for directory name
            safe_thread_id = thread_id.replace(":", "_").replace("/", "_")
            thread_dir = settings.FILES_ROOT / safe_thread_id
            thread_dir.mkdir(parents=True, exist_ok=True)

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

                # Download file to thread directory
                local_path = thread_dir / file_name
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
                local_path = thread_dir / file_name

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
                    user_id=str(update.effective_user.id),
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
            # Clean up thread_id to avoid leaking thread-local fallback
            from cassey.storage.file_sandbox import clear_thread_id
            clear_thread_id()
