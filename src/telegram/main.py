"""Telegram bot for Executive Assistant - supports polling and webhook."""

import asyncio
import os

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, Request
from langchain_core.messages import AIMessage, HumanMessage
from langfuse import propagate_attributes
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from src.agents.factory import get_agent_factory
from src.config import get_settings
from src.llm import create_model_from_config
from src.app_logging import get_logger
from src.storage.checkpoint import init_checkpoint_manager
from src.storage.conversation import get_conversation_store
from telegram import Update

logger = get_logger()

TELEGRAM_MODE = os.environ.get("TELEGRAM_MODE", "polling")  # "polling" or "webhook"
TELEGRAM_WEBHOOK_URL = os.environ.get("TELEGRAM_WEBHOOK_URL", "")
TELEGRAM_SECRET = os.environ.get("TELEGRAM_SECRET", "")

_app: Application | None = None
_model = None
_checkpoint_managers: dict[str, "asyncio.Lock"] = {}


async def get_checkpoint_manager(user_id: str):
    """Get or create checkpoint manager for user with lock."""
    if user_id not in _checkpoint_managers:
        _checkpoint_managers[user_id] = asyncio.Lock()
        _checkpoint_managers[user_id] = await init_checkpoint_manager(user_id)
    return _checkpoint_managers[user_id]


def get_model():
    """Get or create model, return (provider, model_name)."""
    global _model
    if _model is None:
        settings = get_settings()
        model_str = settings.agent.model
        if ":" in model_str:
            provider, model_name = model_str.split(":", 1)
        else:
            provider = "ollama"
            model_name = model_str
        _model = create_model_from_config()
    else:
        settings = get_settings()
        model_str = settings.agent.model
        if ":" in model_str:
            provider, model_name = model_str.split(":", 1)
        else:
            provider = "ollama"
            model_name = model_str
    return provider, model_name


async def handle_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming Telegram update."""
    if not update.message:
        return

    user_id = str(update.effective_user.id)
    text = update.message.text

    conversation = get_conversation_store(user_id)
    conversation.add_message("user", text)

    recent_messages = conversation.get_recent_messages(50)

    checkpoint_manager = await get_checkpoint_manager(user_id)

    await update.message.chat.send_action("typing")

    try:
        from src.tools.progressive_disclosure import create_progressive_disclosure_tools

        config = {"configurable": {"thread_id": user_id}}

        handler = logger.langfuse_handler
        if handler:
            config["callbacks"] = [handler]

        model = get_model()
        tools = create_progressive_disclosure_tools(user_id)
        factory = get_agent_factory(checkpointer=checkpoint_manager.checkpointer)
        agent = factory.create(
            model=model,
            tools=tools,
            system_prompt="You are a helpful executive assistant. Be concise. Use the conversation history tools when user asks about past conversations.",
            checkpointer=checkpoint_manager.checkpointer,
        )

        with propagate_attributes(user_id=user_id):
            result = await agent.ainvoke(
                {
                    "messages": [
                        HumanMessage(content=m.content)
                        if m.role == "user"
                        else AIMessage(content=m.content)
                        for m in recent_messages
                    ]
                    + [HumanMessage(content=text)]
                },
                config=config,
            )

        response = result["messages"][-1].content
        conversation.add_message("assistant", response)

        await update.message.reply_text(response)

    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")


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
    global _app

    provider, model_name = get_model()
    print(f"✓ Provider: {provider}")
    print(f"✓ Model: {model_name}")

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
    global _app

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

    mode = TELEGRAM_MODE.lower()

    if mode == "webhook":
        if not TELEGRAM_WEBHOOK_URL:
            print("TELEGRAM_WEBHOOK_URL not set - falling back to polling")
            await run_polling(token)
        else:
            await run_webhook(token, TELEGRAM_WEBHOOK_URL, TELEGRAM_SECRET)
    else:
        await run_polling(token)


if __name__ == "__main__":
    asyncio.run(main())
