"""Daily rollup job - summarizes messages and manages checkpoint retention."""

from datetime import date, timedelta

from src.config import get_settings
from src.storage.checkpoint import get_checkpoint_manager
from src.storage.conversation import get_conversation_store


class DailyRollup:
    """Daily job to summarize messages and manage checkpoint retention."""

    def __init__(self, user_id: str = "default"):
        self.user_id = user_id
        self.conversation = get_conversation_store(user_id)
        self.checkpoint_manager = get_checkpoint_manager(user_id)

    async def run(self, target_date: date | None = None):
        """Run daily rollup for a specific date.

        Args:
            target_date: Date to summarize. Defaults to yesterday.
        """
        if target_date is None:
            target_date = date.today() - timedelta(days=1)

        await self._summarize_day(target_date)
        await self._cleanup_checkpoints()

    async def _summarize_day(self, target_date: date):
        """Summarize messages for a specific day."""
        from langchain_core.messages import HumanMessage

        settings = get_settings()
        journal_config = settings.memory.journal
        model_name = journal_config.model

        from src.llm import create_model_from_config

        messages = self.conversation.get_messages(
            start_date=target_date,
            end_date=target_date,
        )

        if not messages:
            print(f"No messages for {target_date}, skipping summary.")
            return

        prompt = f"""Summarize the following conversation from {target_date}.
Focus on key topics discussed, decisions made, and important information shared.

Conversation:
"""

        for msg in messages:
            prompt += f"\n{msg.role}: {msg.content}"

        prompt += "\n\nProvide a concise summary (2-3 sentences)."

        model = create_model_from_config(model_name)
        result = await model.ainvoke([HumanMessage(content=prompt)])
        summary = result.content

        self.conversation.add_journal(
            summary=summary,
            msg_count=len(messages),
            metadata={"date": str(target_date)},
        )

        print(f"Journal entry created for {target_date}: {summary[:100]}...")

    async def _cleanup_checkpoints(self):
        """Clean up checkpoints older than retention period."""
        config = get_settings()
        retention_days = config.memory.checkpointer.retention_days

        print(f"Checking checkpoint cleanup (retention: {retention_days} days)")

        # The cleanup is handled by CheckpointManager on initialization
        # But we can also trigger it manually here if needed
        await self.checkpoint_manager._cleanup_old_checkpoints()

        print("Checkpoint cleanup complete.")


async def run_daily_rollup(user_id: str = "default", target_date: date | None = None):
    """Run daily rollup for a user."""
    rollup = DailyRollup(user_id)
    await rollup.run(target_date)
