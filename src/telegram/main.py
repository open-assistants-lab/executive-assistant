"""Telegram bot for Executive Assistant."""

import asyncio
import os

from dotenv import load_dotenv

load_dotenv()

from langchain_core.messages import AIMessage, HumanMessage
from langfuse import propagate_attributes
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from src.agents.factory import get_agent_factory
from src.llm import create_model_from_config
from src.logging import get_logger
from src.storage.checkpoint import init_checkpoint_manager
from src.storage.conversation import get_conversation_store
from telegram import Update

# Global state
_agent = None
_model = None
_checkpoint_managers: dict[str, any] = {}


async def get_checkpoint_manager(user_id: str):
    """Get or create checkpoint manager for user."""
    if user_id not in _checkpoint_managers:
        _checkpoint_managers[user_id] = await init_checkpoint_manager(user_id)
    return _checkpoint_managers[user_id]


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
        "Commands:\n/start - Start the bot\n/help - Show this help\n/reset - Clear conversation"
    )


async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /clear command."""
    user_id = str(update.effective_user.id)
    # Note: messages are kept in DuckDB for history, this just clears agent memory
    await update.message.reply_text(
        "Note: Your conversation history is preserved. To delete, use /reset."
    )


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /reset command - clears conversation."""
    user_id = str(update.effective_user.id)

    # Delete checkpoint
    checkpoint_mgr = await get_checkpoint_manager(user_id)
    await checkpoint_mgr.delete_thread()

    await update.message.reply_text("Conversation reset! Starting fresh.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages."""
    user_id = str(update.effective_user.id)
    text = update.message.text

    # Get conversation store and checkpoint manager
    conversation = get_conversation_store(user_id)

    # Add user message to conversation store
    conversation.add_message("user", text)

    # Get messages from conversation store
    recent_messages = conversation.get_recent_messages(50)

    # Get or init checkpoint manager
    checkpoint_manager = await get_checkpoint_manager(user_id)

    await update.message.chat.send_action("typing")

    try:
        # Build config with checkpoint and Langfuse
        config = {"configurable": {"thread_id": user_id}}

        logger = get_logger()
        handler = logger.langfuse_handler
        if handler:
            config["callbacks"] = [handler]

        # Get agent with checkpointer
        agent = get_agent()
        from src.agents.factory import get_agent_factory

        factory = get_agent_factory(checkpointer=checkpoint_manager.checkpointer)
        agent_with_checkpoint = factory.create(
            model=_model,
            tools=[],
            system_prompt="You are a helpful executive assistant. Be concise.",
            checkpointer=checkpoint_manager.checkpointer,
        )

        with logger.timer("agent", {"message": text, "user_id": user_id}, channel="telegram"):
            with propagate_attributes(user_id=user_id):
                result = await agent_with_checkpoint.ainvoke(
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

        # Store assistant response
        conversation.add_message("assistant", response)

        logger.info(
            "agent.response",
            {"response": response},
            user_id=user_id,
            channel="telegram",
        )

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
    application.add_handler(CommandHandler("reset", reset))
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
