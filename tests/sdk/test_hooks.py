"""Tests for the shell hooks system."""

import os
import stat
import tempfile

import pytest

from src.sdk.hooks import HookConfig, HookDecision, HookManager, HookResult


class TestHookResult:
    def test_allow(self):
        r = HookResult.allow()
        assert r.decision == HookDecision.ALLOW
        assert r.reason == ""
        assert r.modified_args is None

    def test_deny(self):
        r = HookResult.deny("not allowed")
        assert r.decision == HookDecision.DENY
        assert r.reason == "not allowed"

    def test_from_json_allow(self):
        r = HookResult.from_json({"decision": "allow"})
        assert r.decision == HookDecision.ALLOW

    def test_from_json_deny(self):
        r = HookResult.from_json({"decision": "deny", "reason": "blocked"})
        assert r.decision == HookDecision.DENY
        assert r.reason == "blocked"

    def test_from_json_modify(self):
        r = HookResult.from_json({"decision": "modify", "args": {"path": "/safe"}})
        assert r.decision == HookDecision.MODIFY
        assert r.modified_args == {"path": "/safe"}

    def test_from_json_invalid_decision_defaults_to_allow(self):
        r = HookResult.from_json({"decision": "unknown"})
        assert r.decision == HookDecision.ALLOW

    def test_from_json_missing_decision_defaults_to_allow(self):
        r = HookResult.from_json({})
        assert r.decision == HookDecision.ALLOW


class TestHookManagerDiscovery:
    def test_discovers_executable_hook_script(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            hook_dir = os.path.join(tmpdir, ".ea", "hooks")
            os.makedirs(hook_dir)
            script = os.path.join(hook_dir, "pre-tool-use.sh")
            with open(script, "w") as f:
                f.write("#!/bin/bash\necho '{}'\n")
            os.chmod(script, os.stat(script).st_mode | stat.S_IEXEC)

            config = HookConfig(hook_dirs=[os.path.join(tmpdir, ".ea", "hooks")])
            mgr = HookManager(config=config)
            scripts = mgr.get_pre_tool_use_scripts()
            assert len(scripts) == 1
            assert scripts[0].name == "pre-tool-use.sh"

    def test_discovers_script_without_extension(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            hook_dir = os.path.join(tmpdir, ".ea", "hooks")
            os.makedirs(hook_dir)
            script = os.path.join(hook_dir, "pre-tool-use")
            with open(script, "w") as f:
                f.write("#!/bin/bash\necho '{}'\n")
            os.chmod(script, os.stat(script).st_mode | stat.S_IEXEC)

            config = HookConfig(hook_dirs=[os.path.join(tmpdir, ".ea", "hooks")])
            mgr = HookManager(config=config)
            scripts = mgr.get_pre_tool_use_scripts()
            assert len(scripts) == 1
            assert scripts[0].name == "pre-tool-use"

    def test_ignores_non_executable_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            hook_dir = os.path.join(tmpdir, ".ea", "hooks")
            os.makedirs(hook_dir)
            script = os.path.join(hook_dir, "pre-tool-use.sh")
            with open(script, "w") as f:
                f.write("#!/bin/bash\necho '{}'\n")
            # Not executable

            config = HookConfig(hook_dirs=[os.path.join(tmpdir, ".ea", "hooks")])
            mgr = HookManager(config=config)
            scripts = mgr.get_pre_tool_use_scripts()
            assert len(scripts) == 0

    def test_disabled_returns_empty(self):
        config = HookConfig(enabled=False)
        mgr = HookManager(config=config)
        assert mgr.get_pre_tool_use_scripts() == []
        assert mgr.get_post_tool_use_scripts() == []


class TestHookManagerExecution:
    @pytest.mark.asyncio
    async def test_pre_tool_use_allows_when_no_hooks(self):
        mgr = HookManager(config=HookConfig(enabled=True, hook_dirs=["/nonexistent"]))
        result = await mgr.run_pre_tool_use("echo", {"text": "hello"})
        assert result.decision == HookDecision.ALLOW

    @pytest.mark.asyncio
    async def test_post_tool_use_allows_when_no_hooks(self):
        mgr = HookManager(config=HookConfig(enabled=True, hook_dirs=["/nonexistent"]))
        result = await mgr.run_post_tool_use("echo", {"text": "hello"}, "hello")
        assert result.decision == HookDecision.ALLOW

    @pytest.mark.asyncio
    async def test_pre_tool_use_deny_from_script(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            hook_dir = os.path.join(tmpdir, "hooks")
            os.makedirs(hook_dir)
            script = os.path.join(hook_dir, "pre-tool-use.sh")
            with open(script, "w") as f:
                f.write('#!/bin/bash\necho \'{"decision": "deny", "reason": "blocked"}\'\n')
            os.chmod(script, os.stat(script).st_mode | stat.S_IEXEC)

            config = HookConfig(hook_dirs=[hook_dir])
            mgr = HookManager(config=config)
            result = await mgr.run_pre_tool_use("shell_execute", {"command": "rm -rf /"})
            assert result.decision == HookDecision.DENY
            assert "blocked" in result.reason

    @pytest.mark.asyncio
    async def test_pre_tool_use_modify_from_script(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            hook_dir = os.path.join(tmpdir, "hooks")
            os.makedirs(hook_dir)
            script = os.path.join(hook_dir, "pre-tool-use.sh")
            with open(script, "w") as f:
                f.write('#!/bin/bash\necho \'{"decision": "modify", "args": {"path": "/safe"}}\'\n')
            os.chmod(script, os.stat(script).st_mode | stat.S_IEXEC)

            config = HookConfig(hook_dirs=[hook_dir])
            mgr = HookManager(config=config)
            result = await mgr.run_pre_tool_use("files_delete", {"path": "/tmp/x"})
            assert result.decision == HookDecision.MODIFY
            assert result.modified_args == {"path": "/safe"}

    @pytest.mark.asyncio
    async def test_pre_tool_use_allow_from_script(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            hook_dir = os.path.join(tmpdir, "hooks")
            os.makedirs(hook_dir)
            script = os.path.join(hook_dir, "pre-tool-use.sh")
            with open(script, "w") as f:
                f.write('#!/bin/bash\necho \'{"decision": "allow"}\'\n')
            os.chmod(script, os.stat(script).st_mode | stat.S_IEXEC)

            config = HookConfig(hook_dirs=[hook_dir])
            mgr = HookManager(config=config)
            result = await mgr.run_pre_tool_use("echo", {"text": "hello"})
            assert result.decision == HookDecision.ALLOW

    @pytest.mark.asyncio
    async def test_script_timeout_denies(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            hook_dir = os.path.join(tmpdir, "hooks")
            os.makedirs(hook_dir)
            script = os.path.join(hook_dir, "pre-tool-use.sh")
            with open(script, "w") as f:
                f.write('#!/bin/bash\nsleep 30\necho \'{"decision": "allow"}\'\n')
            os.chmod(script, os.stat(script).st_mode | stat.S_IEXEC)

            config = HookConfig(hook_dirs=[hook_dir], timeout_seconds=0.5)
            mgr = HookManager(config=config)
            result = await mgr.run_pre_tool_use("echo", {"text": "hello"})
            assert result.decision == HookDecision.DENY
            assert "timed out" in result.reason

    @pytest.mark.asyncio
    async def test_script_nonzero_exit_denies(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            hook_dir = os.path.join(tmpdir, "hooks")
            os.makedirs(hook_dir)
            script = os.path.join(hook_dir, "pre-tool-use.sh")
            with open(script, "w") as f:
                f.write("#!/bin/bash\nexit 1\n")
            os.chmod(script, os.stat(script).st_mode | stat.S_IEXEC)

            config = HookConfig(hook_dirs=[hook_dir])
            mgr = HookManager(config=config)
            result = await mgr.run_pre_tool_use("echo", {"text": "hello"})
            assert result.decision == HookDecision.DENY

    @pytest.mark.asyncio
    async def test_post_tool_use_deny_from_script(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            hook_dir = os.path.join(tmpdir, "hooks")
            os.makedirs(hook_dir)
            script = os.path.join(hook_dir, "post-tool-use.sh")
            with open(script, "w") as f:
                f.write(
                    '#!/bin/bash\necho \'{"decision": "deny", "reason": "sensitive output"}\'\n'
                )
            os.chmod(script, os.stat(script).st_mode | stat.S_IEXEC)

            config = HookConfig(hook_dirs=[hook_dir])
            mgr = HookManager(config=config)
            result = await mgr.run_post_tool_use(
                "files_read", {"path": "/etc/passwd"}, "root:x:0:0"
            )
            assert result.decision == HookDecision.DENY
            assert "sensitive" in result.reason

    @pytest.mark.asyncio
    async def test_refresh_rediscovery(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = HookConfig(hook_dirs=[tmpdir])
            mgr = HookManager(config=config)
            assert mgr.get_pre_tool_use_scripts() == []

            script = os.path.join(tmpdir, "pre-tool-use.sh")
            with open(script, "w") as f:
                f.write('#!/bin/bash\necho \'{"decision": "allow"}\'\n')
            os.chmod(script, os.stat(script).st_mode | stat.S_IEXEC)

            mgr.refresh()
            assert len(mgr.get_pre_tool_use_scripts()) == 1
