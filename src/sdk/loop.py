"""Agent loop — the core ReAct while-loop that replaces LangChain's agent.

The loop is:
    1. Call LLM with conversation history + tools
    2. If response has no tool_calls → done, return final message
    3. Execute each tool call, append results to messages
    4. Go back to step 1

Middleware hooks run at defined points:
    before_agent → before_model → [LLM call] → after_model → [tool exec] → (repeat) → after_agent

Features:
    - Structured block streaming (text_start/delta/end, tool_input_start/delta/end, reasoning_*)
    - Guardrails (input, output, tool-level)
    - Handoffs (multi-agent delegation)
    - Structured tracing (spans for LLM calls, tool exec, guardrails, handoffs)
    - Auto-approval via ToolAnnotations (replaces interrupt_on)
    - Cost tracking via RunConfig
    - Backward-compatible: also emits ai_token, tool_start, tool_end, reasoning
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from src.sdk.guardrails import (
    GuardrailResult,
    GuardrailTripwire,
    InputGuardrail,
    OutputGuardrail,
    ToolGuardrail,
)
from src.sdk.handoffs import Handoff
from src.sdk.messages import Message, StreamChunk, ToolCall
from src.sdk.middleware import Middleware
from src.sdk.providers.base import LLMProvider, ModelCost
from src.sdk.state import AgentState
from src.sdk.tools import ToolDefinition, ToolRegistry
from src.sdk.tracing import SpanType, TraceProvider
from src.sdk.validation import repair_tool_call

logger = logging.getLogger(__name__)

DEFAULT_MAX_ITERATIONS = 25
DEFAULT_MAX_LLM_CALLS = 50
DEFAULT_MAX_TOKENS_TOTAL = 1_000_000
DEFAULT_COST_LIMIT_USD = 10.0


@dataclass
class RunConfig:
    """Configuration for a single agent run."""

    max_llm_calls: int = DEFAULT_MAX_LLM_CALLS
    max_iterations: int = DEFAULT_MAX_ITERATIONS
    max_tokens_total: int = DEFAULT_MAX_TOKENS_TOTAL
    cost_limit_usd: float = DEFAULT_COST_LIMIT_USD


class CostTracker:
    """Tracks token usage and estimated cost per invocation."""

    def __init__(self) -> None:
        self.total_input_tokens: int = 0
        self.total_output_tokens: int = 0
        self.total_reasoning_tokens: int = 0
        self.total_cost_usd: float = 0.0
        self.llm_calls: int = 0

    def add_usage(
        self,
        input_tokens: int = 0,
        output_tokens: int = 0,
        reasoning_tokens: int = 0,
        cost: ModelCost | None = None,
    ) -> None:
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_reasoning_tokens += reasoning_tokens
        self.llm_calls += 1
        if cost:
            self.total_cost_usd += (input_tokens / 1_000_000) * cost.input + (
                output_tokens / 1_000_000
            ) * cost.output
            if cost.reasoning and reasoning_tokens:
                self.total_cost_usd += (reasoning_tokens / 1_000_000) * cost.reasoning

    def exceeds_limits(self, config: RunConfig) -> str | None:
        if self.llm_calls >= config.max_llm_calls:
            return f"max_llm_calls ({config.max_llm_calls}) reached"
        if self.total_cost_usd >= config.cost_limit_usd:
            return f"cost_limit_usd (${config.cost_limit_usd}) exceeded"
        if (
            self.total_input_tokens + self.total_output_tokens + self.total_reasoning_tokens
        ) >= config.max_tokens_total:
            return f"max_tokens_total ({config.max_tokens_total}) exceeded"
        return None


class Interrupt(Exception):  # noqa: N818
    """Raised when a tool call requires human approval."""

    def __init__(self, tool_call: ToolCall, allowed_actions: list[str] | None = None):
        self.tool_call = tool_call
        self.allowed_actions = allowed_actions or ["approve", "reject", "edit"]
        super().__init__(f"Interrupt: tool call '{tool_call.name}' requires approval")


class AgentLoop:
    """ReAct agent loop that replaces LangChain's create_agent().

    Usage:
        loop = AgentLoop(
            provider=ollama_provider,
            tools=[time_get, files_list],
            system_prompt="You are a helpful assistant.",
            middlewares=[MemoryMiddleware(user_id="alice")],
        )
        result = await loop.run(messages)
        # or
        async for chunk in loop.run_stream(messages):
            handle(chunk)
    """

    def __init__(
        self,
        provider: LLMProvider,
        tools: list[ToolDefinition] | None = None,
        system_prompt: str | None = None,
        middlewares: list[Middleware] | None = None,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
        interrupt_on: set[str] | None = None,
        input_guardrails: list[InputGuardrail] | None = None,
        output_guardrails: list[OutputGuardrail] | None = None,
        tool_guardrails: list[ToolGuardrail] | None = None,
        handoffs: list[Handoff] | None = None,
        trace_provider: TraceProvider | None = None,
        run_config: RunConfig | None = None,
    ) -> None:
        self.provider = provider
        self.system_prompt = system_prompt
        self.middlewares = middlewares or []
        self.max_iterations = max_iterations
        self.interrupt_on = interrupt_on or set()
        self.input_guardrails = input_guardrails or []
        self.output_guardrails = output_guardrails or []
        self.tool_guardrails = tool_guardrails or []
        self.handoffs = handoffs or []
        self.trace_provider = trace_provider
        self.run_config = run_config or RunConfig(max_iterations=max_iterations)

        self._registry = ToolRegistry()
        if tools:
            for t in tools:
                self._registry.register(t)

        self._handoff_tool_names: set[str] = set()
        for h in self.handoffs:
            self._handoff_tool_names.add(h.tool_name)

    def _apply_updates(self, state: AgentState, updates: dict[str, Any] | None) -> None:
        if updates:
            state.update(updates)

    def _should_interrupt(self, tc: ToolCall) -> bool:
        if tc.name in self.interrupt_on:
            return True
        tool_def = self._registry.get(tc.name)
        if tool_def and tool_def.annotations.destructive and not tool_def.annotations.read_only:
            return True
        return False

    async def _execute_tool(self, tc: ToolCall) -> str:
        tool_def = self._registry.get(tc.name)
        if tool_def is None:
            return json.dumps({"error": f"Unknown tool: {tc.name}"})

        try:
            if tool_def._coroutine:
                result = await tool_def.ainvoke(tc.arguments)
            else:
                result = tool_def.invoke(tc.arguments)
            logger.info(
                f"sdk.tool_executed tool={tc.name} source={tool_def.function.__module__ if tool_def.function else 'unknown'}"
            )
            return str(result)
        except Exception as e:
            logger.error(f"tool_execution_error tool={tc.name}: {e}")
            return json.dumps({"error": str(e)})

    async def _run_hooks(self, hook_name: str, state: AgentState) -> None:
        for mw in self.middlewares:
            method = getattr(mw, hook_name, None)
            if method is None:
                continue
            try:
                updates = await method(state)
                self._apply_updates(state, updates)
            except Exception:
                logger.warning(f"{hook_name} error in {mw.name}", exc_info=True)

    def _prepare_messages(self, state: AgentState) -> list[Message]:
        messages = list(state.messages)
        if self.system_prompt:
            if not messages or messages[0].role != "system":
                messages.insert(0, Message.system(self.system_prompt))
        return messages

    async def _check_input_guardrails(self, state: AgentState) -> GuardrailResult | None:
        user_msgs = state.user_messages()
        if not user_msgs:
            return None
        last_input = user_msgs[-1].content
        if isinstance(last_input, list):
            last_input = str(last_input)

        for guardrail in self.input_guardrails:
            try:
                if self.trace_provider:
                    async with self.trace_provider.start_span(
                        SpanType.GUARDRAIL, guardrail.name
                    ) as span:
                        result = await guardrail.check(last_input, state)
                        span.set_meta("triggered", result.tripwire_triggered)
                else:
                    result = await guardrail.check(last_input, state)
                if result.tripwire_triggered:
                    raise GuardrailTripwire(result, guardrail.name)
            except GuardrailTripwire:
                raise
            except Exception as e:
                logger.warning(f"input_guardrail_error name={guardrail.name}: {e}")
        return None

    async def _check_output_guardrails(self, output: str, state: AgentState) -> None:
        for guardrail in self.output_guardrails:
            try:
                if self.trace_provider:
                    async with self.trace_provider.start_span(
                        SpanType.GUARDRAIL, guardrail.name
                    ) as span:
                        result = await guardrail.check(output, state)
                        span.set_meta("triggered", result.tripwire_triggered)
                else:
                    result = await guardrail.check(output, state)
                if result.tripwire_triggered:
                    raise GuardrailTripwire(result, guardrail.name)
            except GuardrailTripwire:
                raise
            except Exception as e:
                logger.warning(f"output_guardrail_error name={guardrail.name}: {e}")

    async def _check_tool_guardrails(
        self, tc: ToolCall, phase: str, data: dict | str
    ) -> GuardrailResult | None:
        for guardrail in self.tool_guardrails:
            try:
                if phase == "input" and guardrail.check_input:
                    result = await guardrail.check_input(tc.name, data)
                    if result and result.tripwire_triggered:
                        raise GuardrailTripwire(result, guardrail.name)
                elif phase == "output" and guardrail.check_output:
                    result = await guardrail.check_output(tc.name, str(data))
                    if result and result.tripwire_triggered:
                        raise GuardrailTripwire(result, guardrail.name)
            except GuardrailTripwire:
                raise
            except Exception as e:
                logger.warning(f"tool_guardrail_error name={guardrail.name}: {e}")
        return None

    async def run(self, messages: list[Message]) -> list[Message]:
        """Run the agent loop to completion. Returns final message list."""
        state = AgentState(messages=list(messages))
        cost_tracker = CostTracker()

        await self._run_hooks("abefore_agent", state)

        try:
            await self._check_input_guardrails(state)
        except GuardrailTripwire as e:
            state.add_message(Message.assistant(content=f"Input blocked: {e.result.message}"))
            await self._run_hooks("aafter_agent", state)
            return state.messages

        for iteration in range(self.run_config.max_iterations):
            limit_reason = cost_tracker.exceeds_limits(self.run_config)
            if limit_reason:
                state.add_message(Message.assistant(content=f"Run limit reached: {limit_reason}"))
                break

            await self._run_hooks("abefore_model", state)

            prepared = self._prepare_messages(state)
            tools = self._registry.list_tools() or None

            try:
                if self.trace_provider:
                    async with self.trace_provider.start_span(
                        SpanType.LLM_CALL, f"llm_call_{iteration}"
                    ) as span:
                        response = await self.provider.chat(
                            prepared, tools=tools, model=None, provider_options=None
                        )
                        span.set_meta("has_tool_calls", bool(response.tool_calls))
                        cost_tracker.add_usage()
                else:
                    response = await self.provider.chat(
                        prepared, tools=tools, model=None, provider_options=None
                    )
                    cost_tracker.add_usage()
            except Exception as e:
                logger.error(f"llm_error iteration={iteration}: {e}")
                state.add_message(Message.assistant(content=f"Error: {e}"))
                break

            state.add_message(response)

            await self._run_hooks("aafter_model", state)

            if not response.tool_calls:
                output_text = response.content if isinstance(response.content, str) else ""
                try:
                    await self._check_output_guardrails(output_text, state)
                except GuardrailTripwire as e:
                    state.add_message(
                        Message.assistant(content=f"Output blocked: {e.result.message}")
                    )
                break

            for tc in response.tool_calls:
                if self._should_interrupt(tc):
                    raise Interrupt(tc)

                try:
                    await self._check_tool_guardrails(tc, "input", tc.arguments)
                except GuardrailTripwire as e:
                    state.add_message(
                        Message.tool_result(
                            tool_call_id=tc.id,
                            content=json.dumps(
                                {"error": f"Tool input blocked: {e.result.message}"}
                            ),
                            name=tc.name,
                        )
                    )
                    continue

                for mw in self.middlewares:
                    tc.arguments = mw.wrap_tool_call(tc.name, tc.arguments)

                if self.trace_provider:
                    async with self.trace_provider.start_span(
                        SpanType.TOOL_EXECUTION, tc.name
                    ) as span:
                        result_content = await self._execute_tool(tc)
                        span.set_meta("result_length", len(result_content))
                else:
                    result_content = await self._execute_tool(tc)

                try:
                    await self._check_tool_guardrails(tc, "output", result_content)
                except GuardrailTripwire as e:
                    result_content = json.dumps(
                        {"error": f"Tool output blocked: {e.result.message}"}
                    )

                state.add_message(
                    Message.tool_result(
                        tool_call_id=tc.id,
                        content=result_content,
                        name=tc.name,
                    )
                )

        await self._run_hooks("aafter_agent", state)
        return state.messages

    async def run_stream(self, messages: list[Message]) -> AsyncIterator[StreamChunk]:
        """Run the agent loop, yielding StreamChunk events in real-time.

        Emits block-structured events:
            text_start / text_delta / text_end
            tool_input_start / tool_input_delta / tool_input_end
            reasoning_start / reasoning_delta / reasoning_end
            tool_result (after tool execution)
            interrupt / done / error

        Also emits backward-compatible aliases:
            ai_token (alongside text_delta)
            tool_start (alongside tool_input_start)
            tool_end (alongside tool_result)
            reasoning (alongside reasoning_delta)
        """
        state = AgentState(messages=list(messages))
        cost_tracker = CostTracker()
        all_tool_calls: list[dict[str, Any]] = []

        await self._run_hooks("abefore_agent", state)

        if self.trace_provider:
            async with self.trace_provider.start_span(SpanType.AGENT, "agent_run"):
                async for chunk in self._run_stream_inner(state, cost_tracker, all_tool_calls):
                    yield chunk

        else:
            async for chunk in self._run_stream_inner(state, cost_tracker, all_tool_calls):
                yield chunk

    async def _run_stream_inner(
        self,
        state: AgentState,
        cost_tracker: CostTracker,
        all_tool_calls: list[dict[str, Any]],
    ) -> AsyncIterator[StreamChunk]:
        guardrail_task: asyncio.Task[GuardrailResult | None] | None = None
        try:
            guardrail_task = asyncio.ensure_future(self._check_input_guardrails(state))
        except Exception:
            guardrail_task = None

        for iteration in range(self.run_config.max_iterations):
            limit_reason = cost_tracker.exceeds_limits(self.run_config)
            if limit_reason:
                yield StreamChunk.error(message=f"Run limit reached: {limit_reason}")
                break

            await self._run_hooks("abefore_model", state)

            prepared = self._prepare_messages(state)
            tools = self._registry.list_tools() or None

            stream_content_parts: list[str] = []
            stream_tool_calls: list[ToolCall] = []
            stream_tool_calls_map: dict[int, dict] = {}
            stream_reasoning_parts: list[str] = []
            in_text_block = False
            in_reasoning_block = False

            if guardrail_task is not None:
                try:
                    await guardrail_task
                except GuardrailTripwire as e:
                    yield StreamChunk.error(message=f"Input blocked: {e.result.message}")
                    break
                guardrail_task = None

            try:
                if self.trace_provider:
                    async with self.trace_provider.start_span(
                        SpanType.LLM_CALL, f"llm_call_{iteration}"
                    ) as llm_span:
                        async for chunk in self.provider.chat_stream(
                            prepared, tools=tools, model=None, provider_options=None
                        ):
                            async for event in self._process_stream_chunk(
                                chunk,
                                stream_content_parts,
                                stream_tool_calls_map,
                                stream_reasoning_parts,
                                in_text_block,
                                in_reasoning_block,
                            ):
                                yield event
                                if event.type == "text_start":
                                    in_text_block = True
                                elif event.type == "text_end":
                                    in_text_block = False
                                elif event.type == "reasoning_start":
                                    in_reasoning_block = True
                                elif event.type == "reasoning_end":
                                    in_reasoning_block = False

                        cost_tracker.add_usage()
                        llm_span.set_meta("tool_calls_count", len(stream_tool_calls_map))
                else:
                    async for chunk in self.provider.chat_stream(
                        prepared, tools=tools, model=None, provider_options=None
                    ):
                        async for event in self._process_stream_chunk(
                            chunk,
                            stream_content_parts,
                            stream_tool_calls_map,
                            stream_reasoning_parts,
                            in_text_block,
                            in_reasoning_block,
                        ):
                            yield event
                            if event.type == "text_start":
                                in_text_block = True
                            elif event.type == "text_end":
                                in_text_block = False
                            elif event.type == "reasoning_start":
                                in_reasoning_block = True
                            elif event.type == "reasoning_end":
                                in_reasoning_block = False

                    cost_tracker.add_usage()

            except Exception as e:
                logger.error(f"llm_stream_error iteration={iteration}: {e}")
                yield StreamChunk.error(message=str(e))
                break

            if in_text_block:
                yield StreamChunk.text_end()
            if in_reasoning_block:
                yield StreamChunk.reasoning_end()

            for tc_data in stream_tool_calls_map.values():
                args = tc_data.get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args) if args else {}
                    except json.JSONDecodeError:
                        args = repair_tool_call(args)
                stream_tool_calls.append(
                    ToolCall(
                        id=tc_data["id"],
                        name=tc_data["name"],
                        arguments=args,
                    )
                )

            assistant_content = "".join(stream_content_parts)
            reasoning_content = "".join(stream_reasoning_parts) or None
            assistant_msg = Message.assistant(
                content=assistant_content,
                tool_calls=stream_tool_calls,
                reasoning=reasoning_content,
            )
            state.add_message(assistant_msg)

            if not stream_tool_calls:
                output_text = assistant_content
                try:
                    await self._check_output_guardrails(output_text, state)
                except GuardrailTripwire as e:
                    yield StreamChunk.error(message=f"Output blocked: {e.result.message}")
                break

            all_tool_calls.extend([{"name": tc.name, "call_id": tc.id} for tc in stream_tool_calls])

            for tc in stream_tool_calls:
                if self._should_interrupt(tc):
                    yield StreamChunk.interrupt(tool=tc.name, call_id=tc.id, args=tc.arguments)
                    continue

                try:
                    await self._check_tool_guardrails(tc, "input", tc.arguments)
                except GuardrailTripwire as e:
                    blocked_result = json.dumps(
                        {"error": f"Tool input blocked: {e.result.message}"}
                    )
                    state.add_message(
                        Message.tool_result(
                            tool_call_id=tc.id, content=blocked_result, name=tc.name
                        )
                    )
                    yield StreamChunk.tool_result_event(
                        tool=tc.name, call_id=tc.id, result_preview=blocked_result[:500]
                    )
                    yield StreamChunk.tool_end(
                        tool=tc.name, call_id=tc.id, result_preview=blocked_result[:500]
                    )
                    continue

                for mw in self.middlewares:
                    tc.arguments = mw.wrap_tool_call(tc.name, tc.arguments)

                if self.trace_provider:
                    async with self.trace_provider.start_span(
                        SpanType.TOOL_EXECUTION, tc.name
                    ) as tool_span:
                        result_content = await self._execute_tool(tc)
                        tool_span.set_meta("result_length", len(result_content))
                else:
                    result_content = await self._execute_tool(tc)

                try:
                    await self._check_tool_guardrails(tc, "output", result_content)
                except GuardrailTripwire as e:
                    result_content = json.dumps(
                        {"error": f"Tool output blocked: {e.result.message}"}
                    )

                state.add_message(
                    Message.tool_result(
                        tool_call_id=tc.id,
                        content=result_content,
                        name=tc.name,
                    )
                )
                preview = result_content[:500] if result_content else ""
                yield StreamChunk.tool_result_event(
                    tool=tc.name, call_id=tc.id, result_preview=preview
                )
                yield StreamChunk.tool_end(tool=tc.name, call_id=tc.id, result_preview=preview)

        await self._run_hooks("aafter_agent", state)

        final_content = ""
        if state.messages:
            last = state.messages[-1]
            if last.role == "assistant":
                final_content = last.content if isinstance(last.content, str) else ""

        yield StreamChunk.done(content=final_content, tool_calls=all_tool_calls)

    async def _process_stream_chunk(
        self,
        chunk: StreamChunk,
        content_parts: list[str],
        tool_calls_map: dict[int, dict],
        reasoning_parts: list[str],
        in_text_block: bool,
        in_reasoning_block: bool,
    ) -> AsyncIterator[StreamChunk]:
        """Process a provider-emitted chunk, emitting block-structured events + backward-compat aliases."""
        canonical = chunk.canonical_type

        if canonical == "text_delta":
            if not in_text_block:
                yield StreamChunk.text_start()
            yield StreamChunk.text_delta(content=chunk.content)
            yield StreamChunk.ai_token(content=chunk.content)
            content_parts.append(chunk.content)

        elif canonical == "tool_input_start":
            if in_text_block:
                yield StreamChunk.text_end()
            if chunk.call_id:
                tool_calls_map[len(tool_calls_map)] = {
                    "id": chunk.call_id,
                    "name": chunk.tool or "",
                    "arguments": "",
                }
            yield StreamChunk.tool_input_start(
                tool=chunk.tool or "",
                call_id=chunk.call_id or "",
                args=chunk.args,
            )
            yield StreamChunk.tool_start(
                tool=chunk.tool or "",
                call_id=chunk.call_id or "",
                args=chunk.args,
            )

        elif canonical == "tool_input_delta":
            if chunk.content and chunk.call_id:
                for entry in tool_calls_map.values():
                    if entry["id"] == chunk.call_id:
                        entry["arguments"] += chunk.content
                        break
            yield StreamChunk.tool_input_delta(call_id=chunk.call_id or "", content=chunk.content)

        elif canonical == "tool_input_end":
            yield StreamChunk.tool_input_end(call_id=chunk.call_id or "", tool=chunk.tool or "")

        elif canonical == "reasoning_delta":
            if not in_reasoning_block:
                yield StreamChunk.reasoning_start()
            yield StreamChunk.reasoning_delta(content=chunk.content)
            yield StreamChunk.reasoning(content=chunk.content)
            reasoning_parts.append(chunk.content)

        elif canonical == "reasoning_start":
            yield StreamChunk.reasoning_start()

        elif canonical == "reasoning_end":
            yield StreamChunk.reasoning_end()

        elif chunk.type == "text_start":
            yield StreamChunk.text_start()

        elif chunk.type == "text_end":
            yield StreamChunk.text_end()

        elif chunk.type == "tool_end":
            pass

        elif chunk.type == "done":
            pass

        elif chunk.type == "error":
            yield StreamChunk.error(message=chunk.content)

    async def run_single(self, messages: list[Message]) -> Message:
        """Single LLM call — no tool loop. For summarization, extraction, etc."""
        prepared = list(messages)
        if self.system_prompt:
            if not prepared or prepared[0].role != "system":
                prepared.insert(0, Message.system(self.system_prompt))

        response = await self.provider.chat(prepared, tools=None, model=None)

        if not isinstance(response.content, str):
            content = str(response.content)
        else:
            content = response.content

        return Message.assistant(content=content)
