"""Telegram bot for Executive Assistant - supports polling and webhook."""

import asyncio
import os

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, Request
from langchain_core.messages import AIMessage, HumanMessage
from langfuse import propagate_attributes
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from src.agents.manager import get_checkpoint_manager, run_agent
from src.storage.conversation import get_conversation_store
from telegram import Update

# Store pending approvals: user_id -> interrupt data
_pending_approvals: dict[str, dict] = {}


async def handle_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming Telegram update."""
    if not update.message:
        return

    user_id = str(update.effective_user.id)
    text = update.message.text.strip().lower()

    # Check if this is a response to a pending approval
    if user_id in _pending_approvals and text in ("approve", "reject", "edit"):
        pending = _pending_approvals.pop(user_id)
        tool_name = pending["tool_name"]
        tool_args = pending["tool_args"]

        if text == "reject":
            await update.message.reply_text(f"❌ {tool_name} rejected.")
            return

        # Execute the tool directly
        if tool_name == "email_delete":
            from src.tools.email import email_delete

            result = email_delete.invoke(tool_args)
            await update.message.reply_text(f"✅ {result}")
            return

        if tool_name == "delete_file":
            from src.tools.filesystem import delete_file

            result = delete_file.invoke(tool_args)
            await update.message.reply_text(f"✅ {result}")
            return

        await update.message.reply_text(f"Unknown tool: {tool_name}")
        return

    # Normal message handling
    conversation = get_conversation_store(user_id)
    conversation.add_message("user", text)
    recent_messages = conversation.get_recent_messages(50)

    langgraph_messages = [
        HumanMessage(content=m.content) if m.role == "user" else AIMessage(content=m.content)
        for m in recent_messages
    ] + [HumanMessage(content=text)]

    # Start typing indicator in background
    typing_task = asyncio.create_task(_send_typing_indicator(update.message.chat.id, context))

    try:
        from src.app_logging import get_logger

        logger = get_logger()

        with propagate_attributes(user_id=user_id):
            result = await run_agent(
                user_id=user_id,
                messages=langgraph_messages,
                message=text,
            )

        # Check for human-in-the-loop interrupt
        if "__interrupt__" in result:
            interrupt_obj = result["__interrupt__"][0]
            # Interrupt is a dataclass with .value attribute
            interrupt_value = getattr(interrupt_obj, "value", None)

            if interrupt_value and isinstance(interrupt_value, dict):
                action_requests = interrupt_value.get("action_requests", [{}])[0]
                review_configs = interrupt_value.get("review_configs", [{}])[0]

                tool_name = action_requests.get("name", "unknown")
                tool_args = action_requests.get("args", {})
                allowed = review_configs.get("allowed_decisions", [])

                # Store pending approval
                _pending_approvals[user_id] = {
                    "tool_name": tool_name,
                    "tool_args": tool_args,
                }

                response = f"⚠️ **{tool_name.replace('_', ' ').title()} - Approval Required**\n\n"
                response += f"Tool: `{tool_name}`\n"
                response += f"Arguments: `{tool_args}`\n\n"
                response += f"Available actions: {', '.join(['`' + a + '`' for a in allowed])}\n\n"
                response += "Reply with one of the above actions to proceed."

                await update.message.reply_text(response)
                return

        messages = result.get("messages", [])

        response = None
        tool_results = []
        tool_names_used = []

        for msg in messages:
            msg_type = getattr(msg, "type", None)
            if msg_type == "tool":
                content = getattr(msg, "content", None)
                if content:
                    tool_results.append(content)

        for msg in reversed(messages):
            msg_type = getattr(msg, "type", None)
            content = getattr(msg, "content", None)
            if msg_type == "ai":
                tool_calls = getattr(msg, "tool_calls", None)
                if tool_calls:
                    for tc in tool_calls:
                        tool_names_used.append(tc.get("name", "unknown"))
                if tool_calls and tool_results:
                    response = "\n".join(tool_results)
                    break
                if tool_calls:
                    response = f"Tool(s) executed: {', '.join(tool_names_used)}"
                    break
                if content and content.strip():
                    response = content
                    break

        if not response:
            response = "Task completed."

        # Tool-based detection: research tools likely produce long responses
        LONG_OUTPUT_TOOLS = {
            "search_web",
            "scrape_url",
            "crawl_url",
            "map_url",
            "files_grep_search",
        }
        is_research_output = bool(LONG_OUTPUT_TOOLS.intersection(set(tool_names_used)))

        if is_research_output and len(response) > 1000:
            # Summary stays under Telegram's 4096 limit
            summary = response[:4000] + "\n\n... (full response in file)"

            # Stop typing indicator
            typing_task.cancel()

            # Send summary first (under 4096 chars)
            await update.message.reply_text(summary)

            # Send full response as file
            from telegram import InputFile
            import tempfile
            import os

            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
                f.write(response)
                temp_path = f.name

            try:
                with open(temp_path, "rb") as f:
                    await update.message.reply_document(
                        document=InputFile(f, filename="response.txt"), caption="Full response"
                    )
            finally:
                os.unlink(temp_path)

            conversation.add_message("assistant", response)
        else:
            # Stop typing indicator
            typing_task.cancel()
            conversation.add_message("assistant", response)
            await update.message.reply_text(response)

    except Exception as e:
        typing_task.cancel()
        await update.message.reply_text(f"Error: {str(e)}")


async def _send_typing_indicator(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send typing indicator periodically while agent is processing."""
    while True:
        try:
            await context.bot.send_chat_action(chat_id=chat_id, action="typing")
            await asyncio.sleep(4)  # Telegram typing status lasts ~5 seconds
        except asyncio.CancelledError:
            break
        except Exception:
            break


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    await update.message.reply_text(
        "Hello! I'm your Executive Assistant. Send me a message and I'll help you out."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    await update.message.reply_text(
        "Commands:\n/start - Start the bot\n/help - Show this help\n/reset - Clear conversation"
    )


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /reset command."""
    user_id = str(update.effective_user.id)
    checkpoint_mgr = await get_checkpoint_manager(user_id)
    await checkpoint_mgr.delete_thread()
    await update.message.reply_text("Conversation reset! Starting fresh.")


async def run_polling(token: str):
    """Run bot in polling mode."""
    _app = Application.builder().token(token).build()
    _app.add_handler(CommandHandler("start", start))
    _app.add_handler(CommandHandler("help", help_command))
    _app.add_handler(CommandHandler("reset", reset))
    _app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_update))

    await _app.initialize()
    await _app.start()
    await _app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    print("Telegram bot is running...")

    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        await _app.updater.stop()
        await _app.stop()


async def run_webhook(token: str, webhook_url: str, secret: str):
    """Run bot in webhook mode with FastAPI."""
    _app = Application.builder().token(token).build()

    _app.add_handler(CommandHandler("start", start))
    _app.add_handler(CommandHandler("help", help_command))
    _app.add_handler(CommandHandler("reset", reset))
    _app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_update))

    await _app.initialize()

    if secret:
        await _app.bot.set_webhook(
            url=f"{webhook_url}/webhook",
            secret_token=secret,
        )
    else:
        await _app.bot.set_webhook(url=f"{webhook_url}/webhook")

    print("Starting Telegram bot in WEBHOOK mode...")
    print(f"Webhook URL: {webhook_url}/webhook")

    fastapi_app = FastAPI(title="Telegram Webhook")

    @fastapi_app.post("/webhook")
    async def webhook(request: Request):
        """Handle incoming webhook."""
        if secret:
            secret_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
            if secret_token != secret:
                raise HTTPException(status_code=403, detail="Invalid secret")

        body = await request.body()
        await _app.update_persisted(update=Update.de_json(data=body, bot=_app.bot))

        return {"ok": True}

    @fastapi_app.get("/health")
    async def health():
        return {"status": "healthy"}

    import uvicorn

    webhook_host = os.environ.get("WEBHOOK_HOST", "0.0.0.0")
    webhook_port = int(os.environ.get("WEBHOOK_PORT", "8080"))

    config = uvicorn.Config(fastapi_app, host=webhook_host, port=webhook_port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    """Main entry point."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("TELEGRAM_BOT_TOKEN not set in environment")
        return

    mode = os.environ.get("TELEGRAM_MODE", "polling").lower()
    webhook_url = os.environ.get("TELEGRAM_WEBHOOK_URL", "")
    secret = os.environ.get("TELEGRAM_SECRET", "")

    if mode == "webhook":
        if not webhook_url:
            print("TELEGRAM_WEBHOOK_URL not set - falling back to polling")
            await run_polling(token)
        else:
            await run_webhook(token, webhook_url, secret)
    else:
        await run_polling(token)


if __name__ == "__main__":
    asyncio.run(main())
