"""Daily rollup scheduler - summarizes messages and manages checkpoint retention for all users."""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from src.config import get_settings
from src.logging import get_logger
from src.storage.rollup import run_daily_rollup

logger = get_logger()


class DailyRollupScheduler:
    """Scheduler that runs daily rollup for all users.

    Runs at midnight and processes all users under data/users/{user_id}/.conversation/
    """

    def __init__(self):
        self.settings = get_settings()
        self.users_dir = Path.cwd() / "data" / "users"
        self._running = False

    def get_all_users(self) -> list[str]:
        """Get list of all user IDs from data/users directory."""
        if not self.users_dir.exists():
            return []

        users = []
        for user_dir in self.users_dir.iterdir():
            if user_dir.is_dir():
                users.append(user_dir.name)

        return users

    async def run_rollup_for_user(self, user_id: str, target_date=None):
        """Run daily rollup for a specific user."""
        try:
            await run_daily_rollup(user_id, target_date)
            logger.info(
                "rollup.complete",
                {"user_id": user_id, "target_date": str(target_date)},
                channel="scheduler",
            )
        except Exception as e:
            logger.warning(
                "rollup.failed",
                {"user_id": user_id, "error": str(e)},
                channel="scheduler",
            )

    async def run(self, target_date=None):
        """Run rollup for all users."""
        users = self.get_all_users()
        logger.info(
            "rollup.start",
            {"user_count": len(users), "target_date": str(target_date)},
            channel="scheduler",
        )

        tasks = []
        for user_id in users:
            tasks.append(self.run_rollup_for_user(user_id, target_date))

        await asyncio.gather(*tasks, return_exceptions=True)

        logger.info(
            "rollup.finish",
            {"user_count": len(users)},
            channel="scheduler",
        )


async def run_scheduler():
    """Run the daily rollup scheduler."""
    scheduler = DailyRollupScheduler()
    await scheduler.run()


async def main():
    """Main entry point for scheduler."""
    print("Starting Daily Rollup Scheduler...")
    print(f"Users directory: {scheduler.users_dir}")

    await scheduler.run()


if __name__ == "__main__":
    scheduler = DailyRollupScheduler()
    asyncio.run(scheduler.run())


async def start_scheduler():
    """Start the scheduler as a background task."""

    scheduler = DailyRollupScheduler()

    def run_daily():
        asyncio.run(scheduler.run())

    while True:
        now = datetime.now()
        tomorrow = now + timedelta(days=1)
        next_run = tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)
        wait_seconds = (next_run - now).total_seconds()

        print(f"Next rollup in {wait_seconds / 3600:.1f} hours")
        await asyncio.sleep(wait_seconds)

        await scheduler.run()


# Import here to avoid circular import
