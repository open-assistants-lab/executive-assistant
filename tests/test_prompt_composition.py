"""Tests for canonical system prompt composition and budgeting."""

from executive_assistant.agent import prompts
from executive_assistant.skills.registry import Skill, get_skills_registry, reset_skills_registry


def setup_function() -> None:
    """Reset global skill registry between tests."""
    reset_skills_registry()


def test_get_system_prompt_includes_compact_skill_index(monkeypatch):
    """System prompt should include compact skills index when enabled."""
    registry = get_skills_registry()
    registry.register(
        Skill(
            name="core_patterns",
            description="Essential patterns for memory and workflows.",
            content="Long startup content that should not be fully injected by default.",
            tags=["core"],
        )
    )
    registry.register(
        Skill(
            name="analytics_with_duckdb",
            description="DuckDB analytics workflows.",
            content="On-demand analytics details.",
            tags=["analytics", "on_demand"],
        )
    )

    monkeypatch.setattr(prompts.settings, "PROMPT_TELEMETRY_ENABLED", False)
    prompt = prompts.get_system_prompt(channel="http", include_skills=True)

    assert "## Skill Index" in prompt
    assert "`core_patterns`" in prompt
    assert "Long startup content" not in prompt
    assert "**analytics**: analytics_with_duckdb" in prompt


def test_get_system_prompt_can_disable_skills(monkeypatch):
    """Skills layer should be skipped when include_skills is explicitly disabled."""
    registry = get_skills_registry()
    registry.register(
        Skill(
            name="core_patterns",
            description="Essential patterns for memory and workflows.",
            content="Long startup content.",
            tags=["core"],
        )
    )

    monkeypatch.setattr(prompts.settings, "PROMPT_TELEMETRY_ENABLED", False)
    prompt = prompts.get_system_prompt(channel="http", include_skills=False)
    assert "## Skill Index" not in prompt
    assert "`core_patterns`" not in prompt


def test_total_budget_trims_low_priority_layers_first(monkeypatch):
    """Total budget should trim emotional layer before instincts/admin."""
    monkeypatch.setattr(prompts.settings, "PROMPT_TELEMETRY_ENABLED", False)
    monkeypatch.setattr(prompts.settings, "PROMPT_LAYER_CAP_ADMIN_TOKENS", 10_000)
    monkeypatch.setattr(prompts.settings, "PROMPT_LAYER_CAP_SKILLS_TOKENS", 10_000)
    monkeypatch.setattr(prompts.settings, "PROMPT_LAYER_CAP_INSTINCT_TOKENS", 10_000)
    monkeypatch.setattr(prompts.settings, "PROMPT_LAYER_CAP_USER_PROMPT_TOKENS", 10_000)
    monkeypatch.setattr(prompts.settings, "PROMPT_LAYER_CAP_EMOTIONAL_TOKENS", 10_000)
    monkeypatch.setattr(prompts.settings, "PROMPT_MAX_SYSTEM_TOKENS", 350)

    monkeypatch.setattr(prompts, "get_default_prompt", lambda: "BASE")
    monkeypatch.setattr(prompts, "get_channel_prompt", lambda _channel: "CHAN")
    monkeypatch.setattr(prompts, "load_admin_prompt", lambda: "A" * 400)
    monkeypatch.setattr(prompts, "load_skills_context", lambda: "S" * 400)
    monkeypatch.setattr(prompts, "load_instincts_context", lambda *_args, **_kwargs: "I" * 400)
    monkeypatch.setattr(prompts, "load_user_prompt", lambda _thread_id: "")
    monkeypatch.setattr(prompts, "load_emotional_context", lambda _thread_id=None: "E" * 400)

    prompt = prompts.get_system_prompt(
        channel="http",
        thread_id="http:test-thread",
        user_message="help",
        include_skills=True,
    )

    assert "[...emotional truncated for prompt budget]" in prompt
    assert "[...instincts truncated for prompt budget]" not in prompt
