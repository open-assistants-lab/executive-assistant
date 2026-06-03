"""Subagent coordinator — creates, invokes, supervises subagents via work_queue.

Replaces SubagentManager with work_queue-backed orchestration.
Each invoke() creates a fresh AgentLoop with ProgressMiddleware + InstructionMiddleware,
runs it with timeout and cost limits, and stores structured results in work_queue.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import shutil
from typing import Any

import yaml

from src.app_logging import get_logger
from src.config import get_settings
from src.sdk.messages import Message
from src.sdk.middleware_instruction import InstructionMiddleware
from src.sdk.middleware_progress import ProgressMiddleware
from src.sdk.subagent_models import (
    AgentDef,
    SubagentResult,
    TaskStatus,
    TaskCancelledError,
)
from src.sdk.agent_validation import validate_agent_def, _is_denied_memory_tool
from src.sdk.work_queue import WorkQueueDB, get_work_queue
from src.skills import get_skill_registry
from src.storage import paths as _paths
# Alias: used by callers (e.g. tests) that patch src.sdk.coordinator.get_paths
get_paths = _paths.get_paths

logger = get_logger()

# Constants for subagent tool filtering
MANDATORY_SUBAGENT_TOOLS = {"message_search"}
OPTIONAL_SKILL_LOAD_TOOL = "skills_load"
DENIED_SKILL_MANAGEMENT_TOOLS = {"skill_create", "skill_delete", "skill_update"}


def _build_profile_md(data: dict) -> str:
    """Build PROFILE.md from an AgentProfile dict (frontmatter + body)."""
    import yaml as _yaml

    data = dict(data)  # don't mutate caller
    system_prompt = data.pop("system_prompt", "")
    yaml_str = _yaml.dump(data, default_flow_style=False, sort_keys=False)
    return f"---\n{yaml_str.strip()}\n---\n\n{system_prompt.strip()}\n"


def _build_tools_for_subagent(agent_def: AgentDef) -> list:
    """Build the filtered tool list for a subagent."""
    from src.sdk.native_tools import get_native_tools

    all_native = get_native_tools()
    tool_map = {t.name: t for t in all_native}

    allowed = set(agent_def.tools) if agent_def.tools else set(tool_map.keys())
    final = {
        name
        for name in allowed
        if not name.startswith("subagent_")
        and not _is_denied_memory_tool(name)
        and name not in DENIED_SKILL_MANAGEMENT_TOOLS
    }
    final.update(MANDATORY_SUBAGENT_TOOLS)
    if agent_def.skills:
        final.add(OPTIONAL_SKILL_LOAD_TOOL)

    return [tool_map[n] for n in sorted(final) if n in tool_map]


def _build_system_prompt(
    agent_def: AgentDef, user_id: str, workspace_id: str = "personal"
) -> str:
    """Build the system prompt for a subagent, including loaded skill content."""
    parts: list[str] = []

    if agent_def.system_prompt:
        parts.append(agent_def.system_prompt)
    else:
        parts.append(f"You are {agent_def.name}, a specialized subagent.")
        if agent_def.description:
            parts.append(agent_def.description)

    if agent_def.skills:
        try:
            from src.skills.registry import get_skill_registry

            sr = get_skill_registry(user_id=user_id, workspace_id=workspace_id)
            skill_entries = []
            for skill_name in agent_def.skills:
                skill = sr.get_skill(skill_name)
                if skill:
                    desc = skill.get("description", "")
                    skill_entries.append(f"- **{skill_name}**: {desc}")
            if skill_entries:
                parts.insert(
                    0,
                    "## Available Skills\n"
                    "Use skills_load(skill_name=...) before following a skill's instructions.\n"
                    + "\n".join(skill_entries),
                )
        except Exception:
            pass

    return "\n\n".join(parts)


def _extract_output(messages: list, max_chars: int = 2000) -> tuple[str, bool]:
    output = ""
    for msg in reversed(messages):
        if hasattr(msg, "role") and msg.role == "assistant" and msg.content:
            content = msg.content
            if isinstance(content, str) and content.strip():
                if len(output) + len(content) > max_chars:
                    output = content[:max_chars - len(output)] + "..."
                    return output, True
                output = content + "\n" + output
    return output.strip(), False


class SubagentCoordinator:
    """Creates, invokes, and supervises subagents via work_queue."""

    def __init__(self, user_id: str, workspace_id: str = "personal"):
        self.user_id = user_id
        self.workspace_id = workspace_id
        self.settings = get_settings()
        self.base_path = _paths.get_paths(user_id=self.user_id).user_subagents_dir()
        self.base_path.mkdir(parents=True, exist_ok=True)
        self._db: WorkQueueDB | None = None
        self._background_tasks: set[asyncio.Task[Any]] = set()
        self._recovery_task: asyncio.Task[Any] | None = None

    async def _recover_stale_jobs(self, max_age_seconds: int = 300) -> int:
        """Mark stale RUNNING/CANCELLING tasks as FAILED. Call on first DB access."""
        try:
            db = await self._get_db()
            count = await db.mark_stale_running_failed(max_age_seconds)
        except Exception:
            return 0
        if count > 0:
            logger.warning(
                "subagent.stale_tasks_recovered",
                {"count": count, "user_id": self.user_id, "workspace_id": self.workspace_id},
                user_id="system",
            )
        return count

    async def _get_db(self) -> WorkQueueDB:
        if self._db is None:
            self._db = await get_work_queue(self.user_id, self.workspace_id)
            if self._recovery_task is None:
                self._recovery_task = asyncio.create_task(self._recover_stale_jobs())
        return self._db

    async def create(self, agent_def: AgentDef) -> AgentDef:
        agent_path = self.base_path / agent_def.name
        agent_path.mkdir(parents=True, exist_ok=True)

        # Write AgentProfile (PROFILE.md format)
        profile_data = agent_def.to_profile()
        try:
            from src.sdk.agent_profile import validate_profile

            errors = validate_profile(profile_data)
            if errors:
                logger.warning(
                    "subagent.profile_validation",
                    {"name": agent_def.name, "errors": errors},
                    user_id=self.user_id,
                )
        except Exception:
            pass

        # Write PROFILE.md (frontmatter + body)
        (agent_path / "PROFILE.md").write_text(
            _build_profile_md(profile_data)
        )

        # Write companion files
        if agent_def.provider_options:
            (agent_path / "provider.json").write_text(
                json.dumps(agent_def.provider_options, indent=2)
            )
        if agent_def.output_schema:
            (agent_path / "output-schema.json").write_text(
                json.dumps(agent_def.output_schema, indent=2)
            )

        # Write legacy config.yaml for backward compat
        config_data = agent_def.model_dump(exclude_none=True)
        config_data.pop("disallowed_tools", None)
        config_path = agent_path / "config.yaml"
        config_path.write_text(
            yaml.dump(config_data, default_flow_style=False)
        )

        if agent_def.mcp_config:
            (agent_path / ".mcp.json").write_text(json.dumps(agent_def.mcp_config, indent=2))

        logger.info(
            "subagent.created",
            {"name": agent_def.name, "model": agent_def.model},
            user_id=self.user_id,
        )
        return agent_def

    async def update(self, name: str, **kwargs: Any) -> AgentDef | None:
        current = self.load_def(name)
        if current is None:
            return None

        update_data = {k: v for k, v in kwargs.items() if v is not None}
        updated = current.model_copy(update=update_data)

        agent_path = self.base_path / name

        # Write PROFILE.md
        profile_data = updated.to_profile()
        (agent_path / "PROFILE.md").write_text(_build_profile_md(profile_data))

        # Write companion files
        if updated.provider_options:
            (agent_path / "provider.json").write_text(
                json.dumps(updated.provider_options, indent=2)
            )
        if updated.output_schema:
            (agent_path / "output-schema.json").write_text(
                json.dumps(updated.output_schema, indent=2)
            )

        # Write legacy config.yaml for backward compat
        config_path = agent_path / "config.yaml"
        config_path.write_text(yaml.dump(updated.model_dump(exclude_none=True), default_flow_style=False))

        if "mcp_config" in update_data and update_data["mcp_config"] is not None:
            (agent_path / ".mcp.json").write_text(json.dumps(update_data["mcp_config"], indent=2))

        logger.info(
            "subagent.updated",
            {"name": name, "fields": list(update_data.keys())},
            user_id=self.user_id,
        )
        return updated

    async def invoke(
        self,
        agent_name: str,
        task: str,
        parent_id: str | None = None,
    ) -> str:
        """DEPRECATED: Use delegate() instead.

        This method skips validate_agent_def() and returns task_id instead of
        result output. Kept for backward compatibility but delegates should use
        delegate() for new code.
        """
        agent_def = self.load_def(agent_name)
        if agent_def is None:
            raise ValueError(f"Subagent '{agent_name}' not found. Create it first with subagent_create.")

        db = await self._get_db()
        task_id = await db.insert_task(agent_name, task, agent_def, parent_id)
        await db.set_running(task_id)

        try:
            result = await asyncio.wait_for(
                self._run_loop(task_id, agent_def, task, db),
                timeout=agent_def.timeout_seconds,
            )
            completed = await db.set_completed(task_id, result)
            if not completed:
                await self._set_cancelled_if_requested(task_id, db)
        except TaskCancelledError:
            await db.set_cancelled(task_id)
        except TimeoutError:
            failed = await db.set_failed(task_id, f"timeout after {agent_def.timeout_seconds}s")
            if not failed:
                await self._set_cancelled_if_requested(task_id, db)
        except Exception as e:
            failed = await db.set_failed(task_id, f"{type(e).__name__}: {e}")
            if not failed:
                await self._set_cancelled_if_requested(task_id, db)

        return task_id

    async def delegate(
        self,
        agent_name: str,
        task: str,
        parent_id: str | None = None,
        timeout_seconds: int | None = None,
    ) -> str:
        """Run a subagent synchronously and return the result string.

        Like invoke() but with agent-def validation and full middleware stack.
        Unlike start(), this blocks until the subagent completes.
        No claim_task or heartbeat needed — runs in-process.

        The effective timeout is min(timeout_seconds, agent_def.timeout_seconds).
        """
        agent_def = self.load_def(agent_name)
        if agent_def is None:
            raise ValueError(
                f"Subagent '{agent_name}' not found. "
                f"Create it first with subagent_create."
            )

        errors = validate_agent_def(agent_def, user_id=self.user_id, workspace_id=self.workspace_id)
        if errors:
            raise ValueError("Invalid subagent definition: " + "; ".join(errors))

        effective_timeout = min(
            timeout_seconds or agent_def.timeout_seconds,
            agent_def.timeout_seconds,
        )

        db = await self._get_db()
        task_id = await db.insert_task(agent_name, task, agent_def, parent_id)

        try:
            result: SubagentResult = await asyncio.wait_for(
                self._run_loop(task_id, agent_def, task, db),
                timeout=effective_timeout,
            )
            completed = await db.set_completed(task_id, result)
            if not completed:
                await self._set_cancelled_if_requested(task_id, db)
            return result.output
        except TaskCancelledError:
            await db.set_cancelled(task_id)
            return "Cancelled: subagent was cancelled during execution."
        except TimeoutError:
            failed = await db.set_failed(task_id, f"timeout after {effective_timeout}s")
            if not failed:
                await self._set_cancelled_if_requested(task_id, db)
            return f"Timeout: subagent did not complete within {effective_timeout}s."
        except Exception as e:
            failed = await db.set_failed(task_id, f"{type(e).__name__}: {e}")
            if not failed:
                await self._set_cancelled_if_requested(task_id, db)
            return f"Error: {type(e).__name__}: {e}"

    async def start(
        self,
        agent_name: str,
        task: str,
        parent_id: str | None = None,
    ) -> str:
        agent_def = self.load_def(agent_name)
        if agent_def is None:
            raise ValueError(f"Subagent '{agent_name}' not found. Create it first with subagent_create.")

        errors = validate_agent_def(agent_def, user_id=self.user_id, workspace_id=self.workspace_id)
        if errors:
            raise ValueError("Invalid subagent definition: " + "; ".join(errors))

        db = await self._get_db()
        task_id = await db.insert_task(agent_name, task, agent_def, parent_id)
        background_task = asyncio.create_task(self._run_job(task_id))
        self._background_tasks.add(background_task)
        background_task.add_done_callback(self._on_background_task_done)
        return task_id

    def _on_background_task_done(self, task: asyncio.Task[Any]) -> None:
        self._background_tasks.discard(task)
        self._consume_background_exception(task)

    @staticmethod
    def _consume_background_exception(task: asyncio.Task[Any]) -> None:
        with contextlib.suppress(asyncio.CancelledError):
            exc = task.exception()
            if exc is not None:
                logger.error(
                    "subagent.background_failed",
                    {"error": str(exc), "error_type": type(exc).__name__},
                    user_id="system",
                )

    async def _heartbeat_loop(self, task_id: str, worker_id: str, db: WorkQueueDB) -> None:
        while True:
            await asyncio.sleep(5)
            await db.heartbeat(task_id, worker_id)

    async def _run_job(self, task_id: str) -> None:
        db = await self._get_db()
        worker_id = f"{self.user_id}:{self.workspace_id}:{id(self)}"
        claimed = await db.claim_task(task_id, worker_id)
        if not claimed:
            return

        row = await db.get_task(task_id)
        if row is None:
            return

        agent_def = AgentDef(**json.loads(row.get("config") or "{}"))
        task = row["task"]
        heartbeat_task = asyncio.create_task(self._heartbeat_loop(task_id, worker_id, db))

        try:
            result = await asyncio.wait_for(
                self._run_loop(task_id, agent_def, task, db),
                timeout=agent_def.timeout_seconds,
            )
            latest = await db.get_task(task_id)
            if latest and latest["status"] == TaskStatus.CANCELLING.value:
                await db.set_cancelled(task_id)
            else:
                completed = await db.set_completed(task_id, result)
                if not completed:
                    await self._set_cancelled_if_requested(task_id, db)
        except TaskCancelledError:
            await db.set_cancelled(task_id)
        except TimeoutError:
            failed = await db.set_failed(task_id, f"timeout after {agent_def.timeout_seconds}s")
            if not failed:
                await self._set_cancelled_if_requested(task_id, db)
        except Exception as e:
            failed = await db.set_failed(task_id, f"{type(e).__name__}: {e}")
            if not failed:
                await self._set_cancelled_if_requested(task_id, db)
        finally:
            heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await heartbeat_task

    async def _set_cancelled_if_requested(self, task_id: str, db: WorkQueueDB) -> bool:
        latest = await db.get_task(task_id)
        if latest and (
            latest["cancel_requested"]
            or latest["status"] in {TaskStatus.CANCELLING.value, TaskStatus.CANCELLED.value}
        ):
            return await db.set_cancelled(task_id)
        return False

    async def _run_loop(
        self,
        task_id: str,
        agent_def: AgentDef,
        task: str,
        db: WorkQueueDB,
    ) -> SubagentResult:
        from src.sdk.loop import AgentLoop, RunConfig
        from src.sdk.middleware_summarization import SummarizationMiddleware
        from src.sdk.providers.factory import create_model_from_config

        try:
            from src.sdk.middleware_observation import ObservationMiddleware
        except ImportError:
            logger.warning(
                "subagent.missing_observation_middleware",
                {"task_id": task_id, "agent": agent_def.name},
                user_id=self.user_id,
            )
            ObservationMiddleware = None  # noqa: N806

        model_str = agent_def.model or self.settings.agent.model
        provider = create_model_from_config(model_str)

        tools = _build_tools_for_subagent(agent_def)
        system_prompt = _build_system_prompt(agent_def, self.user_id, self.workspace_id)

        run_config = RunConfig(
            max_llm_calls=agent_def.max_llm_calls,
            cost_limit_usd=agent_def.cost_limit_usd,
            provider_options=agent_def.provider_options or None,
        )

        progress_mw = ProgressMiddleware(task_id, db)
        instruction_mw = InstructionMiddleware(task_id, db)
        summarization_mw = SummarizationMiddleware()

        middlewares = [progress_mw, instruction_mw, summarization_mw]
        if ObservationMiddleware is not None:
            try:
                observation_mw = ObservationMiddleware(
                    user_id=self.user_id, workspace_id=self.workspace_id
                )
                middlewares.append(observation_mw)
            except Exception as e:
                logger.warning(
                    "subagent.observation_middleware_init_failed",
                    {"task_id": task_id, "error": str(e)},
                    user_id=self.user_id,
                )

        loop = AgentLoop(
            provider=provider,
            tools=tools,
            system_prompt=system_prompt,
            middlewares=middlewares,
            run_config=run_config,
            user_id=self.user_id,
            workspace_id=self.workspace_id,
        )

        messages = [Message.user(task)]
        result_messages = await loop.run(messages)

        total_input = 0
        total_output = 0
        total_reasoning = 0
        llm_calls = 0
        for msg in result_messages:
            if msg.usage:
                total_input += msg.usage.input_tokens
                total_output += msg.usage.output_tokens
                total_reasoning += msg.usage.reasoning_tokens
                llm_calls += 1

        try:
            from src.sdk.registry import get_model_info
            model_info = get_model_info(model_str)
            cost = model_info.cost if model_info and model_info.cost else None
        except Exception:
            cost = None

        cost_usd = 0.0
        if cost:
            cost_usd = (total_input / 1_000_000) * cost.input + (total_output / 1_000_000) * cost.output
            if cost.reasoning and total_reasoning:
                cost_usd += (total_reasoning / 1_000_000) * cost.reasoning

        output, truncated = _extract_output(result_messages)

        return SubagentResult(
            name=agent_def.name,
            task=task,
            success=True,
            output=output,
            truncated=truncated,
            cost_usd=cost_usd,
            llm_calls=llm_calls,
        )

    async def cancel(self, task_id: str) -> bool:
        db = await self._get_db()
        return await db.request_cancel(task_id)

    async def instruct(self, task_id: str, message: str) -> bool:
        db = await self._get_db()
        return await db.add_instruction(task_id, message)

    async def delete(self, name: str) -> bool:
        agent_def = self.load_def(name)
        if agent_def is None:
            return False
        db = await self._get_db()
        await db.request_cancel_active_tasks_for_agent(name)
        agent_path = self.base_path / name
        if agent_path.exists():
            shutil.rmtree(agent_path)
        return True

    async def check_progress(self, parent_id: str | None = None) -> list[dict[str, Any]]:
        db = await self._get_db()
        return await db.check_progress(parent_id=parent_id)

    async def get_result(self, task_id: str) -> SubagentResult | None:
        db = await self._get_db()
        return await db.get_result(task_id)

    async def list_defs(self) -> list[AgentDef]:
        defs: list[AgentDef] = []
        if self.base_path.exists():
            for d in self.base_path.iterdir():
                if d.is_dir() and (d / "config.yaml").exists():
                    agent_def = self.load_def(d.name)
                    if agent_def:
                        defs.append(agent_def)
        return defs

    async def list_defs_with_scope(self) -> list[tuple[AgentDef, str]]:
        """Return agent defs from user-level dir, filtered by item_scopes."""
        scoped: list[tuple[AgentDef, str]] = []

        if self.base_path.exists():
            for d in self.base_path.iterdir():
                if d.is_dir() and (d / "config.yaml").exists():
                    agent_def = self.load_def(d.name)
                    if agent_def:
                        scoped.append((agent_def, "user"))

        # 3. Filter by item_scopes (All / Selected / None)
        try:
            from connectkit.item_scopes import ItemScopeDB

            paths = _paths.get_paths(user_id=self.user_id)
            scope_db = ItemScopeDB(paths.base)
            all_scoped = scope_db.get_all_scoped(self.user_id, "subagent")
        except Exception:
            all_scoped = {}

        filtered: list[tuple[AgentDef, str]] = []
        for agent_def, file_scope in scoped:
            if agent_def.name in all_scoped:
                item = all_scoped[agent_def.name]
                if item.scope == "none":
                    continue
                if item.scope == "selected" and self.workspace_id not in item.workspace_ids:
                    continue
            filtered.append((agent_def, file_scope))

        return filtered

    def load_def(self, name: str) -> AgentDef | None:
        # Prefer PROFILE.md, fall back to config.yaml
        profile_path = self.base_path / name / "PROFILE.md"
        config_path = self.base_path / name / "config.yaml"

        if profile_path.exists():
            try:
                from agentprofile.parser import load_profile as _load_ap
                profile = _load_ap(str(profile_path))
                return AgentDef.from_profile(profile.model_dump())
            except Exception as e:
                logger.error("subagent.load_failed", {"name": name, "error": str(e), "error_type": type(e).__name__}, user_id=self.user_id)

        if config_path.exists():
            try:
                data = yaml.safe_load(config_path.read_text()) or {}
                data.pop("disallowed_tools", None)
                return AgentDef(**data)
            except Exception as e:
                logger.error("subagent.load_failed", {"name": name, "error": str(e), "error_type": type(e).__name__}, user_id=self.user_id)

        return None

    def is_valid(self, name: str) -> bool:
        """Check if a subagent config exists and is loadable.

        Returns False for: missing agent, corrupt YAML, or invalid AgentDef.
        Returns True for: valid, loadable AgentDef.
        """
        return self.load_def(name) is not None


_coordinators: dict[str, SubagentCoordinator] = {}


def get_coordinator(user_id: str, workspace_id: str = "personal") -> SubagentCoordinator:
    key = f"{user_id}:{workspace_id}"
    if key not in _coordinators:
        _coordinators[key] = SubagentCoordinator(user_id, workspace_id)
    return _coordinators[key]
