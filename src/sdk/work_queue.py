"""Work queue database — SQLite-backed task coordination for subagents.

Uses aiosqlite for async access (matches design contract in SUBAGENT_RESEARCH.md).
Per-user database at data/private/subagents/work_queue.db.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

import aiosqlite

from src.app_logging import get_logger
from src.sdk.subagent_models import AgentDef, SubagentResult, TaskStatus
from src.storage.paths import get_paths

logger = get_logger()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS work_queue (
    id TEXT PRIMARY KEY,
    parent_id TEXT,
    user_id TEXT NOT NULL,
    agent_name TEXT NOT NULL,
    task TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    progress TEXT DEFAULT '{}',
    result TEXT,
    error TEXT,
    instructions TEXT DEFAULT '[]',
    config TEXT DEFAULT '{}',
    cancel_requested INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_wq_user_status ON work_queue(user_id, status);
CREATE INDEX IF NOT EXISTS idx_wq_parent ON work_queue(parent_id);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _task_id() -> str:
    return uuid.uuid4().hex[:16]


class WorkQueueDB:
    """Async SQLite work queue for subagent coordination."""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self._db: aiosqlite.Connection | None = None
        self._db_path = str(get_paths(user_id).work_queue_db())

    async def _get_db(self) -> aiosqlite.Connection:
        if self._db is None:
            self._db = await aiosqlite.connect(self._db_path)
            self._db.row_factory = aiosqlite.Row
            await self._db.executescript(_SCHEMA)
            await self._db.execute("PRAGMA journal_mode=WAL")
            await self._db.commit()
        return self._db

    async def close(self) -> None:
        if self._db is not None:
            await self._db.close()
            self._db = None

    async def insert_task(
        self,
        agent_name: str,
        task: str,
        config: AgentDef,
        parent_id: str | None = None,
    ) -> str:
        db = await self._get_db()
        task_id = _task_id()
        now = _now()
        await db.execute(
            """INSERT INTO work_queue
            (id, parent_id, user_id, agent_name, task, status, progress, config, instructions, cancel_requested, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                task_id,
                parent_id,
                self.user_id,
                agent_name,
                task,
                TaskStatus.PENDING.value,
                "{}",
                config.model_dump_json(),
                "[]",
                0,
                now,
                now,
            ),
        )
        await db.commit()
        return task_id

    async def set_status(self, task_id: str, status: TaskStatus) -> bool:
        db = await self._get_db()
        now = _now()
        cursor = await db.execute(
            "UPDATE work_queue SET status = ?, updated_at = ? WHERE id = ?",
            (status.value, now, task_id),
        )
        await db.commit()
        return cursor.rowcount > 0

    async def set_running(self, task_id: str) -> bool:
        return await self.set_status(task_id, TaskStatus.RUNNING)

    async def set_completed(self, task_id: str, result: SubagentResult) -> bool:
        db = await self._get_db()
        now = _now()
        cursor = await db.execute(
            "UPDATE work_queue SET status = ?, result = ?, updated_at = ? WHERE id = ?",
            (TaskStatus.COMPLETED.value, result.model_dump_json(), now, task_id),
        )
        await db.commit()
        return cursor.rowcount > 0

    async def set_failed(self, task_id: str, error: str) -> bool:
        db = await self._get_db()
        now = _now()
        result = SubagentResult(
            name="", task="", success=False, output="", error=error
        )
        cursor = await db.execute(
            "UPDATE work_queue SET status = ?, result = ?, error = ?, updated_at = ? WHERE id = ?",
            (TaskStatus.FAILED.value, result.model_dump_json(), error, now, task_id),
        )
        await db.commit()
        return cursor.rowcount > 0

    async def set_cancelled(self, task_id: str) -> bool:
        db = await self._get_db()
        now = _now()
        result = SubagentResult(
            name="", task="", success=False, output="", error="cancelled by supervisor"
        )
        cursor = await db.execute(
            "UPDATE work_queue SET status = ?, result = ?, cancel_requested = 1, updated_at = ? WHERE id = ?",
            (TaskStatus.CANCELLED.value, result.model_dump_json(), now, task_id),
        )
        await db.commit()
        return cursor.rowcount > 0

    async def get_task(self, task_id: str) -> dict[str, Any] | None:
        db = await self._get_db()
        cursor = await db.execute("SELECT * FROM work_queue WHERE id = ?", (task_id,))
        row = await cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    async def update_progress(self, task_id: str, progress: dict[str, Any]) -> bool:
        db = await self._get_db()
        now = _now()
        cursor = await db.execute(
            "UPDATE work_queue SET progress = ?, updated_at = ? WHERE id = ?",
            (json.dumps(progress, ensure_ascii=True), now, task_id),
        )
        await db.commit()
        return cursor.rowcount > 0

    async def add_instruction(self, task_id: str, message: str) -> bool:
        db = await self._get_db()
        now = _now()
        row = await self.get_task(task_id)
        if row is None:
            return False
        instructions = json.loads(row.get("instructions") or "[]")
        instructions.append({"added_at": now, "message": message})
        cursor = await db.execute(
            "UPDATE work_queue SET instructions = ?, updated_at = ? WHERE id = ?",
            (json.dumps(instructions, ensure_ascii=True), now, task_id),
        )
        await db.commit()
        return cursor.rowcount > 0

    async def request_cancel(self, task_id: str) -> bool:
        db = await self._get_db()
        now = _now()
        cursor = await db.execute(
            "UPDATE work_queue SET cancel_requested = 1, updated_at = ? WHERE id = ?",
            (now, task_id),
        )
        await db.commit()
        return cursor.rowcount > 0

    async def is_cancel_requested(self, task_id: str) -> bool:
        row = await self.get_task(task_id)
        if row is None:
            return False
        return bool(row.get("cancel_requested"))

    async def check_progress(
        self,
        parent_id: str | None = None,
        status: TaskStatus | None = None,
    ) -> list[dict[str, Any]]:
        db = await self._get_db()
        if parent_id is not None and status is not None:
            cursor = await db.execute(
                "SELECT id, agent_name, task, status, progress, error, created_at, updated_at FROM work_queue WHERE parent_id = ? AND status = ? ORDER BY created_at",
                (parent_id, status.value),
            )
        elif parent_id is not None:
            cursor = await db.execute(
                "SELECT id, agent_name, task, status, progress, error, created_at, updated_at FROM work_queue WHERE parent_id = ? ORDER BY created_at",
                (parent_id,),
            )
        elif status is not None:
            cursor = await db.execute(
                "SELECT id, agent_name, task, status, progress, error, created_at, updated_at FROM work_queue WHERE user_id = ? AND status = ? ORDER BY created_at",
                (self.user_id, status.value),
            )
        else:
            cursor = await db.execute(
                "SELECT id, agent_name, task, status, progress, error, created_at, updated_at FROM work_queue WHERE user_id = ? ORDER BY created_at",
                (self.user_id,),
            )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_active_tasks(self) -> list[dict[str, Any]]:
        return await self.check_progress(status=TaskStatus.RUNNING)

    async def get_result(self, task_id: str) -> SubagentResult | None:
        row = await self.get_task(task_id)
        if row is None:
            return None
        result_json = row.get("result")
        if not result_json:
            return None
        data = json.loads(result_json)
        return SubagentResult(**data)


_db_cache: dict[str, WorkQueueDB] = {}


async def get_work_queue(user_id: str) -> WorkQueueDB:
    if user_id not in _db_cache:
        _db_cache[user_id] = WorkQueueDB(user_id)
    return _db_cache[user_id]
