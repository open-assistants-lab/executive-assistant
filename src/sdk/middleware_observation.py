"""ObservationMiddleware — Observational Memory pipeline.

Phase 1: Observer agent watches conversations, produces observations.
Phase 2: Observer quality tuning.
Phase 3: Reflector condenses observations, pinned facts displayed in context.
Phase 4: Full pipeline, extraction deprecated.

Design: docs/OBSERVATIONAL_MEMORY_DESIGN.md
"""

from __future__ import annotations

import asyncio
import os
import threading
from datetime import UTC, datetime, timedelta
from typing import Any

from src.app_logging import get_logger
from src.sdk.messages import Message
from src.sdk.middleware import Middleware
from src.sdk.state import AgentState
from src.storage.messages import get_message_store

logger = get_logger()


class ObservationMiddleware(Middleware):
    """Middleware that manages the Observer/Reflector observation pipeline.

    before_agent: Injects working memory (recent observations + reflections)
                  into the system prompt as static context.
    after_agent:  Checks if Observer or Reflector should fire.

    Follows Middleware ABC (middleware.py:17):
    - before_agent(self, state: AgentState) -> dict[str, Any] | None
    - after_agent(self, state: AgentState) -> dict[str, Any] | None
    """

    OBSERVER_THRESHOLD_TOKENS = 8000
    REFLECTOR_THRESHOLD_TOKENS = 16000
    WORKING_MEMORY_MAX_TOKENS = 10000
    MIN_OBSERVER_INTERVAL_TURNS = 3

    def __init__(self, user_id: str, workspace_id: str = "personal", *, base_dir: str | None = None):
        self.user_id = user_id
        self.workspace_id = workspace_id
        self._unobserved_since: int | None = None
        self._turns_since_observer = 0
        self._observer_lock = threading.Lock()
        self._observer_running = False
        from src.storage.observation import ObservationStore

        self._observation_store = ObservationStore(
            user_id, workspace_id, base_dir=base_dir
        )
        self._message_store = get_message_store(user_id, workspace_id)

    def before_agent(self, state: AgentState) -> dict[str, Any] | None:
        working_memory = self._assemble_working_memory_sync()

        if not working_memory:
            return None

        system_text = self._format_working_memory_block(working_memory)
        system_msg = Message.system(system_text)
        state.messages.insert(-1, system_msg)

        logger.info(
            "observation.working_memory_injected",
            {"tokens": working_memory["total_tokens"]},
            user_id=self.user_id,
        )
        return {"messages": state.messages}

    def after_agent(self, state: AgentState) -> dict[str, Any] | None:
        self._turns_since_observer += 1

        unobserved_tokens = self._count_unobserved_tokens()
        if (
            unobserved_tokens >= self.OBSERVER_THRESHOLD_TOKENS
            and self._turns_since_observer >= self.MIN_OBSERVER_INTERVAL_TURNS
        ):
            self._dispatch_fire_observer()

        try:
            latest = self._observation_store.get_latest_reflection()
            existing_tokens = latest.get("token_count", 0) if latest else 0
        except Exception:
            existing_tokens = 0

        if existing_tokens >= self.REFLECTOR_THRESHOLD_TOKENS:
            self._dispatch_fire_reflector()

        return None

    def _assemble_working_memory_sync(self) -> dict[str, Any] | None:
        sections: list[tuple[str, str]] = []
        total_tokens = 0

        recent = self._observation_store.get_recent_observations(days=7, limit=50)
        if recent:
            obs_text = "## Recent Activity\n" + "\n".join(
                f"{obs['priority']} {obs['observation_ts'][:10] if obs.get('observation_ts') else ''} {obs['content']}"
                for obs in recent
            )
            obs_tokens = self._estimate_tokens(obs_text)
            budget = int(self.WORKING_MEMORY_MAX_TOKENS * 0.6)
            if total_tokens + obs_tokens <= budget:
                sections.append(("recent", obs_text))
                total_tokens += obs_tokens
            else:
                truncated = self._truncate_text(obs_text, budget - total_tokens)
                if truncated:
                    sections.append(("recent", truncated))
                    total_tokens = budget

        reflection = self._observation_store.get_latest_reflection()
        if reflection:
            refl_text = f"## Past Context\n{reflection['content']}"
            refl_tokens = self._estimate_tokens(refl_text)
            remaining = self.WORKING_MEMORY_MAX_TOKENS - total_tokens
            if refl_tokens <= remaining:
                sections.append(("reflection", refl_text))
                total_tokens += refl_tokens
            else:
                truncated = self._truncate_text(reflection["content"], remaining)
                if truncated:
                    sections.append(("reflection", f"## Past Context\n{truncated}"))

        if not sections:
            return None

        return {
            "sections": sections,
            "total_tokens": total_tokens,
            "block_text": "\n\n".join(text for _, text in sections),
        }

    def _format_working_memory_block(self, wm: dict[str, Any]) -> str:
        return (
            "## Working Memory\n"
            "(Read this first. Contains facts from past conversations. "
            "Use memory_search to verify exact numbers, dates, and names.)\n\n"
            + wm["block_text"]
        )

    def _dispatch_fire_observer(self) -> None:
        try:
            asyncio.create_task(self._fire_observer())
        except RuntimeError:
            threading.Thread(target=self._fire_observer_sync, daemon=True).start()

    def _dispatch_fire_reflector(self) -> None:
        try:
            asyncio.create_task(self._fire_reflector())
        except RuntimeError:
            threading.Thread(target=self._fire_reflector_sync, daemon=True).start()

    async def _fire_observer(self) -> None:
        if self._observer_running:
            return

        self._observer_running = True
        self._turns_since_observer = 0
        try:
            from src.sdk.providers.factory import create_model_from_config
            from src.sdk.tools_core.observation import run_observer

            model_str = os.environ.get(
                "OBSERVER_MODEL", os.environ.get("DEFAULT_MODEL", "ollama:llama3.2")
            )
            provider = create_model_from_config(model_str)

            messages = self._message_store.get_messages(
                start_date=datetime.now(UTC) - timedelta(days=30), limit=500
            )
            if not messages:
                return

            msg_dicts = [
                {
                    "role": str(m.role),
                    "ts": str(m.ts) if hasattr(m, "ts") else "",
                    "content": str(m.content),
                }
                for m in messages
            ]

            observations = await run_observer(msg_dicts, provider)

            if observations:
                count = self._observation_store.insert_observations(observations)
                logger.info(
                    "observer.completed",
                    {"observations": count, "messages_processed": len(messages)},
                    user_id=self.user_id,
                )
        except Exception as e:
            logger.warning(
                "observer.failed", {"error": str(e)}, user_id=self.user_id
            )
        finally:
            self._observer_running = False

    def _fire_observer_sync(self) -> None:
        asyncio.run(self._fire_observer())

    async def _fire_reflector(self) -> None:
        try:
            from src.sdk.providers.factory import create_model_from_config
            from src.sdk.tools_core.observation import run_reflector

            model_str = os.environ.get(
                "REFLECTOR_MODEL", os.environ.get("DEFAULT_MODEL", "ollama:llama3.2")
            )
            provider = create_model_from_config(model_str)

            all_observations = self._observation_store.get_all_observations()
            if not all_observations:
                return

            reflection = await run_reflector(all_observations, provider)

            if reflection:
                self._observation_store.insert_reflection(reflection)
                logger.info(
                    "reflector.completed",
                    {
                        "observations_condensed": len(all_observations),
                        "output_tokens": reflection.get("token_count", 0),
                    },
                    user_id=self.user_id,
                )
        except Exception as e:
            logger.warning(
                "reflector.failed", {"error": str(e)}, user_id=self.user_id
            )

    def _fire_reflector_sync(self) -> None:
        asyncio.run(self._fire_reflector())

    def _count_unobserved_tokens(self) -> int:
        try:
            messages = self._message_store.get_messages(
                start_date=datetime.now(UTC) - timedelta(days=30), limit=500
            )
            return sum(
                self._estimate_tokens(str(m.content)) for m in messages
            )
        except Exception:
            return 0

    def _estimate_tokens(self, text: str) -> int:
        try:
            import tiktoken

            enc = tiktoken.get_encoding("cl100k_base")
            return len(enc.encode(text))
        except Exception:
            return len(text) // 4 if text else 0

    def _truncate_text(self, text: str, max_tokens: int) -> str:
        if max_tokens <= 0:
            return ""
        tokens = self._estimate_tokens(text)
        if tokens <= max_tokens:
            return text
        ratio = max_tokens / tokens
        target_chars = int(len(text) * ratio * 0.9)
        return text[:target_chars] + "\n...(truncated)" if target_chars > 0 else ""
