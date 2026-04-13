import asyncio
import json
from pathlib import Path
from typing import Any

import yaml
from langchain_core.messages import HumanMessage

from src.agents.manager import get_default_tools
from src.agents.subagent.config import SubagentConfig
from src.agents.subagent.validation import validate_subagent_config
from src.app_logging import get_logger
from src.config import get_settings
from src.llm import create_model_from_config
from src.skills import SkillRegistry

logger = get_logger()


class SubagentManager:
    """Manages subagent creation, invocation, and tracking."""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.settings = get_settings()
        self.base_path = Path(f"data/users/{user_id}/subagents")
        self.base_path.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, Any] = {}

    def create(
        self,
        name: str,
        model: str | None = None,
        description: str = "",
        skills: list[str] | None = None,
        tools: list[str] | None = None,
        system_prompt: str | None = None,
        mcp_config: dict | None = None,
    ) -> tuple[Any | None, dict[str, Any]]:
        """Create a subagent.

        Args:
            name: Subagent name
            model: Model to use (optional, defaults to main agent model)
            description: Description of subagent
            skills: List of skill names to assign
            tools: List of tool names to assign
            system_prompt: Custom system prompt (optional)
            mcp_config: MCP config dict (optional)

        Returns:
            Tuple of (subagent, validation_result_dict)
            If validation fails, subagent is None and result contains errors
        """
        # Build config dict for validation and config.yaml
        config_dict = {
            "name": name,
            "model": model,
            "description": description,
            "skills": skills or [],
            "tools": tools or [],
            "system_prompt": system_prompt,
        }

        # Validate config before creating directory
        subagent_path = self.base_path / name
        validation = validate_subagent_config(self.user_id, config_dict, subagent_path)

        if not validation.valid:
            logger.warning(
                "subagent.validation.failed",
                {"name": name, "errors": validation.errors},
                user_id=self.user_id,
            )
            # Clean up directory if it was created during validation
            if subagent_path.exists():
                import shutil

                shutil.rmtree(subagent_path, ignore_errors=True)
            return None, {
                "valid": validation.valid,
                "errors": validation.errors,
                "warnings": validation.warnings,
            }

        # Create subagent directory only after validation passes
        subagent_path.mkdir(parents=True, exist_ok=True)

        # Build config dict for config.yaml
        config_dict_clean = {k: v for k, v in config_dict.items() if v is not None}

        # Add system_prompt to config.yaml instead of separate file
        if system_prompt is None:
            system_prompt = f"""You are {name}, a specialized subagent.

{description or "You are helpful and autonomous."}

You have access to tools and skills as configured. Always use the planning-with-files skill for multi-step tasks to track your progress.
"""
        config_dict_clean["system_prompt"] = system_prompt

        # Save config.yaml
        config_path = subagent_path / "config.yaml"
        config_path.write_text(yaml.dump(config_dict_clean))

        # Save .mcp.json if provided
        if mcp_config is not None:
            (subagent_path / ".mcp.json").write_text(json.dumps(mcp_config, indent=2))

        # Load the full config
        full_config = self._load_config(name)

        # Build system prompt with skills
        system_prompt = self._build_system_prompt(full_config)

        # Get tools
        agent_tools = self._get_tools(full_config)

        # Load MCP tools if mcp.json exists
        mcp_tools = self._load_mcp_tools(subagent_path)

        # Create the agent
        from src.agents.manager import get_model

        agent_model = (
            get_model()
            if full_config.model is None
            else create_model_from_config(full_config.model)
        )

        from langchain.agents import create_agent

        all_tools = list(agent_tools) + mcp_tools if mcp_tools else agent_tools

        subagent = create_agent(
            model=agent_model,
            tools=all_tools,
            system_prompt=system_prompt,
        )

        # Store subagent in memory for invocation
        self._cache[name] = subagent

        logger.info(
            "subagent.created",
            {"name": name, "model": full_config.model, "skills": full_config.skills},
            user_id=self.user_id,
        )

        return subagent, {
            "valid": True,
            "errors": [],
            "warnings": validation.warnings,
            "message": f"Subagent '{name}' created successfully",
        }

    def invoke(self, name: str, task: str) -> dict[str, Any]:
        """Invoke a subagent to execute a task.

        Args:
            name: Subagent name
            task: Task description

        Returns:
            Result dict with output and metadata
        """
        from src.tools.filesystem import _current_user_id

        subagent = self._get(name)
        if not subagent:
            return {
                "success": False,
                "error": f"Subagent '{name}' not found. Create it first with subagent_create.",
            }

        # Set user_id context for filesystem tools
        token = _current_user_id.set(self.user_id)

        # Get langfuse handler if available
        config = {"recursion_limit": 50}
        try:
            from src.app_logging import get_logger

            app_logger = get_logger()
            if app_logger.langfuse_handler:
                config["callbacks"] = [app_logger.langfuse_handler]
        except Exception:
            pass

        try:
            result = subagent.invoke(
                {"messages": [HumanMessage(content=task)]},
                config=config,
            )
        except Exception as e:
            logger.error(
                "subagent.invoke_failed",
                {"name": name, "error": str(e)},
                user_id=self.user_id,
            )
            return {
                "success": False,
                "error": str(e),
            }
        finally:
            _current_user_id.reset(token)

        # Find the last AI message content (skip ToolMessages)
        output = ""
        for msg in reversed(result.get("messages", [])):
            msg_type = getattr(msg, "type", None)
            if msg_type == "ai":
                content = getattr(msg, "content", "")
                if content and content.strip():
                    output = content
                    break
        if not output and result.get("messages"):
            # Fallback: use last message content whatever type
            last = result["messages"][-1]
            output = getattr(last, "content", str(last))

        logger.info(
            "subagent.invoked",
            {"name": name, "task": task[:100]},
            user_id=self.user_id,
        )

        return {
            "success": True,
            "output": output,
            "name": name,
            "task": task,
        }

    def list_all(self) -> list[dict[str, Any]]:
        """List all subagents for the user.

        Returns:
            List of subagent configs
        """
        if not self.base_path.exists():
            return []

        subagents = []
        for subagent_dir in self.base_path.iterdir():
            if subagent_dir.is_dir():
                config = self._load_config(subagent_dir.name)
                subagents.append(
                    {
                        "name": config.name,
                        "model": config.model,
                        "description": config.description,
                        "skills": config.skills,
                        "tools": config.tools,
                    }
                )

        return subagents

    def get_progress(self, task_name: str) -> dict[str, Any]:
        """Get subagent progress from planning files.

        Args:
            task_name: Name of the planning task

        Returns:
            Dict with task_plan, progress, and findings content
        """

        base = Path(f"data/users/{self.user_id}/workspace/planning/{task_name}")

        result = {
            "task_plan": None,
            "progress": None,
            "findings": None,
            "exists": base.exists(),
        }

        if not base.exists():
            return result

        for key in ["task_plan", "progress", "findings"]:
            file_path = base / f"{key}.md"
            if file_path.exists():
                result[key] = file_path.read_text()

        return result

    def invoke_batch(self, tasks: list[dict[str, str]]) -> list[dict[str, Any]]:
        """Invoke multiple subagents in parallel.

        Args:
            tasks: List of dicts with 'name' and 'task' keys
                   e.g., [{"name": "agent1", "task": "do X"}, {"name": "agent2", "task": "do Y"}]

        Returns:
            List of result dicts with name, success, output/error
        """
        import concurrent.futures

        from src.tools.filesystem import _current_user_id

        # Capture the current user_id ContextVar value to propagate to worker threads
        parent_user_id = _current_user_id.get()

        results = []

        def run_single(task_dict: dict[str, str]) -> dict[str, Any]:
            # Inherit the parent's user_id ContextVar in the worker thread
            token = _current_user_id.set(parent_user_id)
            try:
                name = task_dict.get("name", "")
                task = task_dict.get("task", "")
                result = self.invoke(name, task)
                result["name"] = name
                return result
            finally:
                _current_user_id.reset(token)

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(tasks)) as executor:
            futures = [executor.submit(run_single, task) for task in tasks]
            for future in concurrent.futures.as_completed(futures):
                results.append(future.result())

        # Sort results to maintain input order
        name_to_result = {r["name"]: r for r in results}
        ordered_results = [name_to_result[t["name"]] for t in tasks]

        logger.info(
            "subagent.batch_invoked",
            {"count": len(tasks), "user_id": self.user_id},
            user_id=self.user_id,
        )

        return ordered_results

    def _load_config(self, name: str) -> SubagentConfig:
        """Load subagent config from file."""
        config_path = self.base_path / name / "config.yaml"

        if not config_path.exists():
            return SubagentConfig(name=name)

        config_dict = yaml.safe_load(config_path.read_text()) or {}
        # Remove 'name' from config_dict if present to avoid duplicate
        config_dict.pop("name", None)
        return SubagentConfig(name=name, **config_dict)

    def _build_system_prompt(self, config: SubagentConfig) -> str:
        """Build system prompt with skills injected."""
        registry = SkillRegistry(system_dir="src/skills", user_id=self.user_id)

        # Get planning-with-files skill (REQUIRED)
        planning_skill = registry.get_skill("planning-with-files")
        planning_content = planning_skill["content"] if planning_skill else ""

        # Get additional skills
        skills_content = ""
        for skill_name in config.skills:
            if skill_name != "planning-with-files":
                skill = registry.get_skill(skill_name)
                if skill:
                    skills_content += f"\n\n## {skill_name}\n{skill['content']}"

        # Get custom system prompt from config
        custom_prompt = config.system_prompt + "\n\n" if config.system_prompt else ""

        system_prompt = f"""{custom_prompt}## Planning Skill (REQUIRED)
{planning_content}

{skills_content}

## Important
You MUST use the planning skill for ANY task that requires multiple steps.
Create a plan in `planning/{{task_name}}/task_plan.md` before executing.
Update `progress.md` after each step.
The main agent will track your progress via these files.
"""

        return system_prompt

    def _get_tools(self, config: SubagentConfig) -> list:
        """Get tools for subagent."""
        all_tools = get_default_tools(self.user_id)

        if not config.tools:
            return all_tools

        # Filter to only assigned tools
        tool_map = {tool.name: tool for tool in all_tools}
        return [tool_map[name] for name in config.tools if name in tool_map]

    def _load_mcp_tools(self, subagent_path: Path) -> list:
        """Load MCP tools from subagent's .mcp.json if exists (sync wrapper)."""
        mcp_path = subagent_path / ".mcp.json"
        if not mcp_path.exists():
            return []

        try:
            mcp_config = json.loads(mcp_path.read_text())
            if not mcp_config:
                return []

            from src.tools.mcp.manager import get_mcp_manager

            mcp_manager = get_mcp_manager(self.user_id)

            # Run async get_tools in sync context
            # Use run_coroutine_threadsafe when inside a running event loop
            # (e.g., HTTP/Telegram server), otherwise use asyncio.run()
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, mcp_manager.get_tools())
                    all_tools = future.result(timeout=30)
            else:
                all_tools = asyncio.run(mcp_manager.get_tools())

            # Filter to only include servers defined in subagent's .mcp.json
            # Use prefix matching (server_name + "_") instead of substring to avoid
            # false positives like "sql" matching "mssql_query"
            allowed_servers = set(mcp_config.keys())
            filtered_tools = [
                tool
                for tool in all_tools
                if hasattr(tool, "name")
                and any(
                    tool.name == server or tool.name.startswith(server + "_")
                    for server in allowed_servers
                )
            ]

            # Also include generic MCP tools that don't have server prefix
            generic_tools = [
                tool
                for tool in all_tools
                if not any(
                    tool.name == server or tool.name.startswith(server + "_")
                    for server in allowed_servers
                )
            ]

            return filtered_tools + generic_tools

        except Exception as e:
            logger.warning(
                "subagent.mcp.load_error",
                {"path": str(mcp_path), "error": str(e), "error_type": type(e).__name__},
                user_id=self.user_id,
            )
            return []

    def invalidate_cache(self, name: str | None = None) -> None:
        """Invalidate subagent cache. If name is None, clear all cache."""
        if not hasattr(self, "_cache"):
            return
        if name is None:
            self._cache.clear()
        elif name in self._cache:
            del self._cache[name]

    def _get(self, name: str) -> Any | None:
        """Get subagent from cache, recreating if config has changed."""
        subagent_path = self.base_path / name
        if not subagent_path.exists():
            self.invalidate_cache(name)
            return None

        # Check if config has changed since last cache
        config_path = subagent_path / "config.yaml"
        cached_agent = self._cache.get(name)
        if cached_agent is not None and config_path.exists():
            config_mtime = config_path.stat().st_mtime
            cache_key = f"_mtime_{name}"
            cached_mtime = getattr(self, cache_key, 0)
            if config_mtime == cached_mtime:
                return cached_agent

        # Config changed or not cached — recreate
        config = self._load_config(name)
        system_prompt = self._build_system_prompt(config)
        agent_tools = self._get_tools(config)

        mcp_tools = self._load_mcp_tools(subagent_path)

        from langchain.agents import create_agent

        from src.agents.manager import get_model

        agent_model = (
            get_model() if config.model is None else create_model_from_config(config.model)
        )

        all_tools = list(agent_tools) + mcp_tools if mcp_tools else agent_tools

        subagent = create_agent(
            model=agent_model,
            tools=all_tools,
            system_prompt=system_prompt,
        )

        self._cache[name] = subagent
        # Track config mtime for cache invalidation
        if config_path.exists():
            setattr(self, f"_mtime_{name}", config_path.stat().st_mtime)

        return subagent


# Global cache for subagent managers
_managers: dict[str, SubagentManager] = {}


def get_subagent_manager(user_id: str) -> SubagentManager:
    """Get or create subagent manager for user."""
    if user_id not in _managers:
        _managers[user_id] = SubagentManager(user_id)
    return _managers[user_id]
