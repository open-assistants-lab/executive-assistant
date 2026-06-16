"""ConnectKit adapter — converts ToolSpec into EA SDK ToolDefinition."""

from __future__ import annotations

from typing import Any

from connectkit.meta_tools import TOOL_SPECS
from connectkit.sdk_adapter import ToolSpec

from src.sdk.tools import ToolAnnotations, ToolDefinition


def _get_gateway_url() -> str:
    try:
        from src.config import get_settings
        settings = get_settings()
        return getattr(settings, "gateway_url", "http://localhost:8000")
    except Exception:
        return "http://localhost:8000"


def _bind_gateway(tool_spec: ToolSpec) -> ToolSpec:
    """Bind gateway_url into connector_connect's async_function."""
    if tool_spec.name != "connector_connect":
        return tool_spec
    gateway_url = _get_gateway_url()
    orig = tool_spec.async_function

    async def bound_connect(**kwargs: Any) -> Any:
        kwargs["gateway_url"] = gateway_url
        return await orig(**kwargs)

    return tool_spec.model_copy(update={"async_function": bound_connect})


def _spec_to_tool_def(spec: ToolSpec) -> ToolDefinition:
    ann = spec.annotations or {}
    annotations = ToolAnnotations(
        title=ann.get("title", spec.name),
        read_only=ann.get("read_only", False),
        destructive=ann.get("destructive", False),
        idempotent=ann.get("idempotent", False),
    )

    async_fn = spec.async_function
    if not async_fn:
        fn = spec.function
        if fn:

            def _make_wrapper(f: Any) -> Any:
                import asyncio
                from functools import partial

                async def wrapper(**kwargs: Any) -> Any:
                    return await asyncio.to_thread(partial(f, **kwargs))
                return wrapper

            async_fn = _make_wrapper(fn)

    return ToolDefinition(
        name=spec.name,
        description=spec.description,
        parameters=spec.parameters,
        annotations=annotations,
        function=async_fn,
    )


def get_connector_tools() -> list[ToolDefinition]:
    return [_spec_to_tool_def(_bind_gateway(spec)) for spec in TOOL_SPECS]
