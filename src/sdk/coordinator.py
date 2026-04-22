"""Subagent coordinator — creates, invokes, supervises subagents via work_queue.

Replaces SubagentManager with work_queue-backed orchestration.
Each invoke() creates a fresh AgentLoop with ProgressMiddleware + InstructionMiddleware,
runs it with timeout and cost limits, and stores structured results in work_queue.
"""

from __future__ import annotations

import asyncio
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
    DEFAULT_DISALLOWED_TOOLS,
    DEFAULT_MAX_OUTPUT_CHARS,
    AgentDef,
    SubagentResult,
    TaskCancelledError,
    TaskStatus,
)
from src.sdk.work_queue import WorkQueueDB, get_work_queue
from src.skills import get_skill_registry
from src.storage.paths import get_paths

logger = get_logger()


def _build_tools_for_subagent(agent_def: AgentDef) -> list[Any]:
    from src.sdk.native_tools import get_native_tools

    all_native = get_native_tools()
    tool_map = {t.name: t for t in all_native}

    allowed = set(agent_def.tools) if agent_def.tools else set(tool_map.keys())
    disallowed = set(agent_def.disallowed_tools)
    final = allowed - disallowed

    return [tool_map[n] for n in final if n in tool_map]


def _build_system_prompt(agent_def: AgentDef, user_id: str) -> str:
    parts: list[str] = []

    if agent_def.system_prompt:
        parts.append(agent_def.system_prompt)
    else:
        parts.append(f"You are {agent_def.name}, a specialized subagent.")
        if agent_def.description:
            parts.append(agent_def.description)

    skill_registry = get_skill_registry(user_id=user_id)
    for skill_name in agent_def.skills:
        skill = skill_registry.get_skill(skill_name)
        if skill:
            parts.append(f"\n\n## Skill: {skill_name}\n{skill['content']}")

    return "\n\n".join(parts)


def _extract_output(messages: list[Message], max_chars: int = DEFAULT_MAX_OUTPUT_CHARS) -> tuple[str, bool]:
    output = ""
    for msg in reversed(messages):
        if msg.role == "assistant" and msg.content:
            content = msg.content
            if isinstance(content, str) and content.strip():
                output = content.strip()
                break
            elif isinstance(content, list):
                text_parts = [
                    b.get("text", "")
                    for b in content
                    if isinstance(b, dict) and b.get("type") == "text"
                ]
                combined = "".join(text_parts).strip()
                if combined:
                    output = combined
                    break

    if not output:
        output = "Subagent completed with no text output."

    truncated = len(output) > max_chars
    if truncated:
        output = output[:max_chars] + f"\n... [truncated, {len(output)} chars total]"

    return output, truncated


class SubagentCoordinator:
    """Creates, invokes, and supervises subagents via work_queue."""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.settings = get_settings()
        self.base_path = get_paths(user_id).subagents_dir()
        self.base_path.mkdir(parents=True, exist_ok=True)
        self._db: WorkQueueDB | None = None

    async def _get_db(self) -> WorkQueueDB:
        if self._db is None:
            self._db = await get_work_queue(self.user_id)
        return self._db

    async def create(self, agent_def: AgentDef) -> AgentDef:
        agent_path = self.base_path / agent_def.name
        agent_path.mkdir(parents=True, exist_ok=True)

        config_path = agent_path / "config.yaml"
        config_path.write_text(yaml.dump(agent_def.model_dump(exclude_none=True), default_flow_style=False))

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
            await db.set_completed(task_id, result)
        except TaskCancelledError:
            await db.set_cancelled(task_id)
        except TimeoutError:
            await db.set_failed(task_id, f"timeout after {agent_def.timeout_seconds}s")
        except Exception as e:
            await db.set_failed(task_id, f"{type(e).__name__}: {e}")

        return task_id

    async def _run_loop(
        self,
        task_id: str,
        agent_def: AgentDef,
        task: str,
        db: WorkQueueDB,
    ) -> SubagentResult:
        from src.sdk.loop import AgentLoop, RunConfig
        from src.sdk.providers.factory import create_model_from_config

        model_str = agent_def.model or self.settings.agent.model
        provider = create_model_from_config(model_str)

        tools = _build_tools_for_subagent(agent_def)
        system_prompt = _build_system_prompt(agent_def, self.user_id)

        run_config = RunConfig(
            max_llm_calls=agent_def.max_llm_calls,
            cost_limit_usd=agent_def.cost_limit_usd,
        )

        progress_mw = ProgressMiddleware(task_id, db)
        instruction_mw = InstructionMiddleware(task_id, db)

        loop = AgentLoop(
            provider=provider,
            tools=tools,
            system_prompt=system_prompt,
            middlewares=[progress_mw, instruction_mw],
            run_config=run_config,
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

    async def check_progress(self, parent_id: str | None = None) -> list[dict[str, Any]]:
        db = await self._get_db()
        return await db.check_progress(parent_id=parent_id)

    async def get_result(self, task_id: str) -> SubagentResult | None:
        db = await self._get_db()
        return await db.get_result(task_id)

    async def list_defs(self) -> list[AgentDef]:
        defs: list[AgentDef] = []
        if not self.base_path.exists():
            return defs
        for d in self.base_path.iterdir():
            if d.is_dir() and (d / "config.yaml").exists():
                agent_def = self.load_def(d.name)
                if agent_def:
                    defs.append(agent_def)
        return defs

    async def delete(self, name: str) -> bool:
        agent_path = self.base_path / name
        if not agent_path.exists():
            return False

        active = await self._get_db()
        tasks = await active.check_progress()
        for t in tasks:
            if t.get("agent_name") == name and t.get("status") in (
                TaskStatus.PENDING.value,
                TaskStatus.RUNNING.value,
            ):
                await active.request_cancel(t["id"])

        shutil.rmtree(agent_path, ignore_errors=True)

        logger.info(
            "subagent.deleted",
            {"name": name},
            user_id=self.user_id,
        )
        return True

    def load_def(self, name: str) -> AgentDef | None:
        config_path = self.base_path / name / "config.yaml"
        if not config_path.exists():
            return None
        try:
            data = yaml.safe_load(config_path.read_text()) or {}
            data.setdefault("disallowed_tools", list(DEFAULT_DISALLOWED_TOOLS))
            return AgentDef(**data)
        except Exception as e:
            logger.warning(
                "subagent.load_failed",
                {"name": name, "error": str(e)},
                user_id=self.user_id,
            )
            return None


_coordinators: dict[str, SubagentCoordinator] = {}


def get_coordinator(user_id: str) -> SubagentCoordinator:
    if user_id not in _coordinators:
        _coordinators[user_id] = SubagentCoordinator(user_id)
    return _coordinators[user_id]
