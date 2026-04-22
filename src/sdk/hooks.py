"""Shell hooks — user-extensible, out-of-process tool lifecycle hooks.

Hooks are shell scripts that run at tool execution boundaries:
  - PreToolUse: before a tool is executed (can allow, deny, or modify)
  - PostToolUse: after a tool is executed (can allow or deny)

This is complementary to Middleware (Python, in-process):
  - Middleware: developer-written, runs at agent lifecycle events
  - Hooks: user-written, runs at tool execution boundaries

Hook scripts receive JSON on stdin and must output JSON on stdout.
Exit code 0 = success (parse stdout), non-zero = deny.

PreToolUse input:  {"tool": "files_delete", "args": {"path": "/x"}}
PreToolUse output: {"decision": "allow"} | {"decision": "deny", "reason": "..."} | {"decision": "modify", "args": {"path": "/safe"}}

PostToolUse input:  {"tool": "files_delete", "args": {"path": "/x"}, "result": "deleted"}
PostToolUse output: {"decision": "allow"} | {"decision": "deny", "reason": "..."}

Hook discovery paths (in order):
  1. .ea/hooks/          (project-level, checked into repo)
  2. data/hooks/         (deployment-level, user-specific)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_HOOK_DIRS = [".ea/hooks", "data/hooks"]


class HookDecision(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    MODIFY = "modify"


@dataclass
class HookResult:
    """Result from running a hook."""

    decision: HookDecision
    reason: str = ""
    modified_args: dict[str, Any] | None = None

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> HookResult:
        decision_str = data.get("decision", "allow")
        try:
            decision = HookDecision(decision_str)
        except ValueError:
            logger.warning(f"hook_invalid_decision value={decision_str}, defaulting to allow")
            decision = HookDecision.ALLOW
        return cls(
            decision=decision,
            reason=data.get("reason", ""),
            modified_args=data.get("args"),
        )

    @classmethod
    def allow(cls) -> HookResult:
        return cls(decision=HookDecision.ALLOW)

    @classmethod
    def deny(cls, reason: str = "") -> HookResult:
        return cls(decision=HookDecision.DENY, reason=reason)


@dataclass
class HookConfig:
    """Configuration for the hook system."""

    enabled: bool = True
    hook_dirs: list[str] = field(default_factory=lambda: list(DEFAULT_HOOK_DIRS))
    timeout_seconds: float = 10.0


class HookManager:
    """Discovers and executes shell hooks for tool lifecycle events."""

    def __init__(self, config: HookConfig | None = None) -> None:
        self.config = config or HookConfig()
        self._pre_tool_use_scripts: list[Path] | None = None
        self._post_tool_use_scripts: list[Path] | None = None

    def _discover_scripts(self, name: str) -> list[Path]:
        """Discover hook scripts by name (e.g., 'pre-tool-use', 'post-tool-use').

        Looks for: {name}.sh, {name} (executable without extension)
        """
        if not self.config.enabled:
            return []

        scripts: list[Path] = []
        for hook_dir_str in self.config.hook_dirs:
            hook_dir = Path(hook_dir_str)
            if not hook_dir.is_absolute():
                hook_dir = Path(os.getcwd()) / hook_dir
            if not hook_dir.exists():
                continue

            for filename in [f"{name}.sh", name]:
                script = hook_dir / filename
                if script.exists() and os.access(script, os.X_OK):
                    scripts.append(script)

        return scripts

    def get_pre_tool_use_scripts(self) -> list[Path]:
        if self._pre_tool_use_scripts is None:
            self._pre_tool_use_scripts = self._discover_scripts("pre-tool-use")
        return self._pre_tool_use_scripts

    def get_post_tool_use_scripts(self) -> list[Path]:
        if self._post_tool_use_scripts is None:
            self._post_tool_use_scripts = self._discover_scripts("post-tool-use")
        return self._post_tool_use_scripts

    def refresh(self) -> None:
        """Re-discover hook scripts (call after scripts are added/removed)."""
        self._pre_tool_use_scripts = None
        self._post_tool_use_scripts = None

    async def run_pre_tool_use(self, tool_name: str, args: dict[str, Any]) -> HookResult:
        """Run all PreToolUse hooks. Returns the first deny or final result.

        If any hook denies, execution is blocked. If a hook modifies args,
        the modified args propagate to subsequent hooks and the tool.
        The returned HookResult will have modified_args set if any hook
        changed the args, regardless of the final decision.
        """
        scripts = self.get_pre_tool_use_scripts()
        if not scripts:
            return HookResult.allow()

        current_args = dict(args)
        payload = json.dumps({"tool": tool_name, "args": current_args})
        args_modified = False

        for script in scripts:
            result = await self._run_script(script, payload)
            if result.decision == HookDecision.DENY:
                logger.info(
                    f"hook.pre_tool_use denied tool={tool_name} script={script.name} reason={result.reason}"
                )
                return result
            if result.decision == HookDecision.MODIFY and result.modified_args is not None:
                current_args = result.modified_args
                payload = json.dumps({"tool": tool_name, "args": current_args})
                args_modified = True
                logger.info(f"hook.pre_tool_use modified tool={tool_name} script={script.name}")

        if args_modified:
            return HookResult(decision=HookDecision.MODIFY, modified_args=current_args)
        return HookResult.allow()

    async def run_post_tool_use(
        self, tool_name: str, args: dict[str, Any], result_content: str
    ) -> HookResult:
        """Run all PostToolUse hooks. Returns the first deny or final allow."""
        scripts = self.get_post_tool_use_scripts()
        if not scripts:
            return HookResult.allow()

        payload = json.dumps(
            {
                "tool": tool_name,
                "args": args,
                "result": result_content,
            }
        )

        for script in scripts:
            result = await self._run_script(script, payload)
            if result.decision == HookDecision.DENY:
                logger.info(
                    f"hook.post_tool_use denied tool={tool_name} script={script.name} reason={result.reason}"
                )
                return result

        return HookResult.allow()

    async def _run_script(self, script: Path, stdin_payload: str) -> HookResult:
        """Run a single hook script with JSON on stdin, parse JSON from stdout."""
        try:
            proc = await asyncio.create_subprocess_exec(
                str(script),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=stdin_payload.encode()),
                timeout=self.config.timeout_seconds,
            )

            if proc.returncode != 0:
                stderr_text = stderr.decode(errors="replace").strip()
                logger.warning(
                    f"hook_script_error script={script.name} exit={proc.returncode} stderr={stderr_text[:200]}"
                )
                return HookResult.deny(reason=f"Hook script exited with code {proc.returncode}")

            output = stdout.decode().strip()
            if not output:
                return HookResult.allow()

            try:
                data = json.loads(output)
            except json.JSONDecodeError:
                logger.warning(f"hook_invalid_json script={script.name} output={output[:200]}")
                return HookResult.allow()

            return HookResult.from_json(data)

        except TimeoutError:
            logger.warning(
                f"hook_timeout script={script.name} timeout={self.config.timeout_seconds}s"
            )
            return HookResult.deny(
                reason=f"Hook script timed out after {self.config.timeout_seconds}s"
            )
        except Exception as e:
            logger.warning(f"hook_error script={script.name} error={e}")
            return HookResult.deny(reason=f"Hook script error: {e}")
