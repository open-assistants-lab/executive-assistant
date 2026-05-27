"""Observation middleware — background Observer and scheduled Reflector.

Observer fires when 8K cumulative unobserved tokens accumulate.
Reflector fires every 24 hours.
No auto-injection — agent calls memory tools explicitly.
"""

from __future__ import annotations

import asyncio
import threading
import time
from datetime import UTC, datetime
from typing import Any

from src.app_logging import get_logger
from src.sdk.middleware import Middleware

logger = get_logger()

OBSERVER_THRESHOLD_TOKENS = 8000
MIN_OBSERVER_INTERVAL_TURNS = 3
REFLECTOR_INTERVAL_SECONDS = 24 * 3600


class ObservationMiddleware(Middleware):
    """Background Observer + scheduled Reflector. No auto-injection."""

    def __init__(self, user_id: str = "default_user",
                 workspace_id: str = "personal",
                 base_dir: str | None = None):
        self.user_id = user_id
        self.workspace_id = workspace_id
        self._base_dir = base_dir
        self._unobserved_since = datetime.now(UTC)
        self._turns_since_observer = 0
        self._observer_running = False
        self._observer_lock = threading.Lock()
        self._reflector_last_run = time.time()
        self._memory_store = None
        self._message_store = None

    @property
    def _store(self) -> Any:
        if self._memory_store is None:
            from src.storage.memory import get_memory_store
            self._memory_store = get_memory_store(self.user_id, self.workspace_id)
        return self._memory_store

    @property
    def _conversation(self) -> Any:
        if self._message_store is None:
            from src.storage.messages import get_message_store
            self._message_store = get_message_store(self.user_id, self.workspace_id)
        return self._message_store

    def after_agent(self, state: Any) -> dict[str, Any] | None:
        self._turns_since_observer += 1

        unobserved_tokens = self._count_unobserved_tokens()
        if (unobserved_tokens >= OBSERVER_THRESHOLD_TOKENS and
                self._turns_since_observer >= MIN_OBSERVER_INTERVAL_TURNS):
            self._dispatch_fire_observer()
            self._turns_since_observer = 0

        now = time.time()
        if now - self._reflector_last_run >= REFLECTOR_INTERVAL_SECONDS:
            self._dispatch_fire_reflector()
            self._reflector_last_run = now

        return None

    def _count_unobserved_tokens(self) -> int:
        try:
            messages = self._conversation.get_recent_messages(count=500, offset=0)
            if not messages:
                return 0
            text = " ".join(m.content or "" for m in messages)
            return max(len(text) // 4, 0)
        except Exception:
            return 0

    def _dispatch_fire_observer(self) -> None:
        with self._observer_lock:
            if self._observer_running:
                return
            self._observer_running = True
        try:
            asyncio.create_task(self._fire_observer())
        except RuntimeError:
            t = threading.Thread(target=self._fire_observer_sync, daemon=True)
            t.start()

    def _dispatch_fire_reflector(self) -> None:
        try:
            asyncio.create_task(self._fire_reflector())
        except RuntimeError:
            t = threading.Thread(target=self._fire_reflector_sync, daemon=True)
            t.start()

    async def _fire_observer(self) -> None:
        try:
            from src.sdk.providers.factory import create_model_from_config
            from src.sdk.tools_core.observation import run_observer

            provider = create_model_from_config()
            messages = self._conversation.get_recent_messages(count=500, offset=0)
            if not messages:
                self._observer_running = False
                return

            raw_messages = [
                {"role": m.role, "content": m.content}
                for m in messages if m.content.strip()
            ]
            previous = self._store.get_recent_observations(days=30, limit=50)

            result = await run_observer(raw_messages, provider,
                                        previous_observations=previous)
            observations = result.get("observations", [])
            if observations:
                self._store.insert_observations(observations)
                logger.info("observer.completed",
                            {"count": len(observations)},
                            user_id=self.user_id)
        except Exception as e:
            logger.error("observer.error", {"error": str(e)}, user_id=self.user_id)
        finally:
            self._observer_running = False

    async def _fire_reflector(self) -> None:
        try:
            from src.sdk.providers.factory import create_model_from_config
            from src.sdk.tools_core.observation import run_reflector

            provider = create_model_from_config()
            observations = self._store.get_all_observations()
            if len(observations) < 10:
                logger.info("reflector.skipped",
                            {"reason": "too_few_observations",
                             "count": len(observations)},
                            user_id=self.user_id)
                return

            previous_reflections = self._store.get_reflections(limit=10)

            self._store.apply_decay()

            result = await run_reflector(observations, provider,
                                         previous_reflections=previous_reflections)
            reflections = result.get("reflections", [])
            if reflections:
                self._store.insert_reflections(reflections)
                logger.info("reflector.completed",
                            {"count": len(reflections)},
                            user_id=self.user_id)
        except Exception as e:
            logger.error("reflector.error", {"error": str(e)}, user_id=self.user_id)

    def _fire_observer_sync(self) -> None:
        asyncio.run(self._fire_observer())

    def _fire_reflector_sync(self) -> None:
        asyncio.run(self._fire_reflector())
