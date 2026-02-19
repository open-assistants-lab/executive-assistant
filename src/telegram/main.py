"""Telegram bot for Executive Assistant."""

import os
import asyncio
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

from telegram import Update

from src.agents.factory import get_agent_factory
from src.llm import create_model_from_config
from src.logging import get_logger
from langchain_core.messages import HumanMessage, AIMessage

# Global state
_agent = None
_model = None
_user_messages: dict[int, list] = {}


def get_agent():
    """Get or create agent."""
    global _agent, _model
    if _agent is None:
        _model = create_model_from_config()
        factory = get_agent_factory()
        _agent = factory.create(
            model=_model,
            tools=[],
            system_prompt="You are a helpful executive assistant. Be concise.",
        )
    return _agent


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    await update.message.reply_text(
        "Hello! I'm your Executive Assistant. Send me a message and I'll help you out."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    await update.message.reply_text(
        "Commands:\n/start - Start the bot\n/help - Show this help\n/clear - Clear conversation"
    )


async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /clear command."""
    user_id = update.effective_user.id
    _user_messages[user_id] = []
    await update.message.reply_text("Conversation cleared!")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages."""
    user_id = str(update.effective_user.id)
    text = update.message.text

    # Initialize user messages if needed
    if user_id not in _user_messages:
        _user_messages[user_id] = []

    # Add user message
    _user_messages[user_id].append(HumanMessage(content=text))

    # Get agent and invoke
    agent = get_agent()
    logger = get_logger()

    await update.message.chat.send_action("typing")

    try:
        with logger.timer("agent", {"message": text, "user_id": user_id}):
            result = await agent.ainvoke({"messages": _user_messages[user_id]})

        response = result["messages"][-1].content
        _user_messages[user_id].append(AIMessage(content=response))

        await update.message.reply_text(response)

    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")


def run_bot(token: str | None = None):
    """Run the Telegram bot."""
    token = token or os.environ.get("TELEGRAM_BOT_TOKEN")

    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN not set")

    # Initialize agent
    global _agent, _model
    _model = create_model_from_config()
    model_name = getattr(_model, "model", "unknown")
    provider = getattr(_model, "_provider", "ollama")
    print(f"Provider: {provider}")
    print(f"Model: {model_name}")

    factory = get_agent_factory()
    _agent = factory.create(
        model=_model,
        tools=[],
        system_prompt="You are a helpful executive assistant. Be concise.",
    )
    print("Agent ready")

    application = Application.builder().token(token).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("clear", clear))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Run
    application.run_polling(allowed_updates=Update.ALL_TYPES)


async def main():
    """Main entry point."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("TELEGRAM_BOT_TOKEN not set in environment")
        return

    await run_bot(token)


if __name__ == "__main__":
    asyncio.run(main())
