"""Per-user agent registry stored in SQLite.

Stores mini-agent DSL for flow usage.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from executive_assistant.config.settings import settings

_AGENT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


@dataclass
class AgentRecord:
    agent_id: str
    name: str
    description: str
    tools: list[str]
    system_prompt: str
    output_schema: dict[str, Any]
    created_at: str
    updated_at: str | None


class AgentRegistry:
    """SQLite-backed registry for per-user agents."""

    def __init__(self, user_id: str) -> None:
        self.user_id = user_id
        self.db_path = self._get_db_path(user_id)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    @staticmethod
    def _get_db_path(user_id: str) -> Path:
        return (settings.USERS_ROOT / user_id / "agents" / "agents.db").resolve()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agents (
                    agent_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    tools TEXT NOT NULL,
                    system_prompt TEXT NOT NULL,
                    output_schema TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT
                );
                """
            )
            # Backfill new column if upgrading from older schema
            cols = conn.execute("PRAGMA table_info(agents)").fetchall()
            col_names = {row[1] for row in cols}
            if "output_schema" not in col_names:
                conn.execute("ALTER TABLE agents ADD COLUMN output_schema TEXT")

            if "model" in col_names:
                try:
                    conn.execute("ALTER TABLE agents DROP COLUMN model")
                except sqlite3.OperationalError:
                    pass

    @staticmethod
    def _validate_agent_id(agent_id: str) -> None:
        if not _AGENT_ID_RE.match(agent_id):
            raise ValueError(
                "agent_id must be 1-64 chars: letters, numbers, underscore, dash"
            )

    @staticmethod
    def _validate_tools(tools: list[str]) -> tuple[bool, str | None]:
        if len(tools) > 10:
            return False, "Agent tool list exceeds hard limit of 10."
        if len(tools) > 5:
            return True, "Agent tool list exceeds recommended limit (<=5)."
        return True, None

    def create_agent(
        self,
        agent_id: str,
        name: str,
        description: str,
        tools: list[str],
        system_prompt: str,
        output_schema: dict[str, Any] | None = None,
    ) -> str:
        self._validate_agent_id(agent_id)
        ok, warning = self._validate_tools(tools)
        if not ok:
            return f"Error: {warning}"

        now = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT agent_id FROM agents WHERE agent_id = ?", (agent_id,)
            ).fetchone()
            if existing:
                return f"Error: Agent '{agent_id}' already exists"

            conn.execute(
                """
                INSERT INTO agents (agent_id, name, description, tools, system_prompt, output_schema, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    agent_id,
                    name,
                    description,
                    json.dumps(tools),
                    system_prompt,
                    json.dumps(output_schema or {}),
                    now,
                ),
            )

        msg = f"Agent '{agent_id}' created"
        if warning:
            msg += f" (Warning: {warning})"
        return msg

    def list_agents(self) -> list[AgentRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM agents ORDER BY created_at DESC"
            ).fetchall()
        return [self._row_to_agent(r) for r in rows]

    def get_agent(self, agent_id: str) -> AgentRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM agents WHERE agent_id = ?", (agent_id,)
            ).fetchone()
        return self._row_to_agent(row) if row else None

    def update_agent(
        self,
        agent_id: str,
        name: str | None = None,
        description: str | None = None,
        tools: list[str] | None = None,
        system_prompt: str | None = None,
        output_schema: dict[str, Any] | None = None,
    ) -> str:
        self._validate_agent_id(agent_id)
        if tools is not None:
            ok, warning = self._validate_tools(tools)
            if not ok:
                return f"Error: {warning}"
        else:
            warning = None

        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM agents WHERE agent_id = ?", (agent_id,)
            ).fetchone()
            if not row:
                return f"Error: Agent '{agent_id}' not found"

            current = self._row_to_agent(row)
            updated = {
                "name": name or current.name,
                "description": description or current.description,
                "tools": tools if tools is not None else current.tools,
                "system_prompt": system_prompt or current.system_prompt,
                "output_schema": output_schema if output_schema is not None else current.output_schema,
            }
            conn.execute(
                """
                UPDATE agents
                SET name = ?, description = ?, tools = ?, system_prompt = ?, output_schema = ?, updated_at = ?
                WHERE agent_id = ?
                """,
                (
                    updated["name"],
                    updated["description"],
                    json.dumps(updated["tools"]),
                    updated["system_prompt"],
                    json.dumps(updated["output_schema"] or {}),
                    datetime.now(UTC).isoformat(),
                    agent_id,
                ),
            )

        msg = f"Agent '{agent_id}' updated"
        if warning:
            msg += f" (Warning: {warning})"
        return msg

    def delete_agent(self, agent_id: str) -> str:
        self._validate_agent_id(agent_id)
        with self._connect() as conn:
            result = conn.execute(
                "DELETE FROM agents WHERE agent_id = ?", (agent_id,)
            )
        if result.rowcount == 0:
            return f"Error: Agent '{agent_id}' not found"
        return f"Agent '{agent_id}' deleted"

    @staticmethod
    def _row_to_agent(row: sqlite3.Row) -> AgentRecord:
        return AgentRecord(
            agent_id=row["agent_id"],
            name=row["name"],
            description=row["description"],
            tools=json.loads(row["tools"]) if row["tools"] else [],
            system_prompt=row["system_prompt"],
            output_schema=json.loads(row["output_schema"]) if row["output_schema"] else {},
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


def get_agent_registry(user_id: str) -> AgentRegistry:
    return AgentRegistry(user_id)
