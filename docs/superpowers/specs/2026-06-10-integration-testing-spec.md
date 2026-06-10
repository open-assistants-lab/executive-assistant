# Integration Testing Architecture — Mock LLM + Real Pipeline

Date: 2026-06-10

## Problem

861 component tests pass, but there are zero tests that verify the full AgentLoop
pipeline (messages → LLM → tool execution → response) against controlled inputs.
Features that work in isolation may fail in the agent flow due to middleware interference,
tool registration issues, or incorrect message formatting.

Real LLM tests are expensive, slow, and non-deterministic — unsuitable for CI.

## Solution

Mock the LLM provider with a `FakeProvider` that returns predetermined responses,
but keep the **entire AgentLoop pipeline real**. This gives deterministic, fast tests
that verify the agent's decision-making logic without LLM cost or latency.

## Architecture

```
FakeProvider (returns predetermined JSON responses)
    ↓
AgentLoop (real — tool registry, middleware, hooks, streaming)
    ↓
Tool execution (real — filesystem, search, etc. with isolated temp dirs)
    ↓
Assertions on stream events, tool calls, message history, side effects
```

### FakeProvider

```python
class FakeProvider(LLMProvider):
    """Returns predetermined responses. No LLM call made."""

    def __init__(self, responses: list[dict] | None = None):
        self._responses = list(responses) if responses else []
        self._default = {"content": "OK"}
        self._history: list[Message] = []

    def _next(self) -> dict:
        if self._responses:
            return self._responses.pop(0)
        return self._default

    async def chat(self, messages, **kwargs) -> Message:
        resp = self._next()
        self._history.extend(messages)
        if "tool_calls" in resp:
            return Message.assistant(
                content=resp.get("content", ""),
                tool_calls=[ToolCall(**tc) for tc in resp["tool_calls"]]
            )
        return Message.assistant(content=resp.get("content", ""))

    async def stream_chat(self, messages, **kwargs):
        resp = self._next()
        self._history.extend(messages)
        # Reasoning events (optional)
        if resp.get("reasoning"):
            yield StreamChunk.reasoning_start()
            yield StreamChunk.reasoning_delta(content=resp["reasoning"])
            yield StreamChunk.reasoning_end()
        # Tool call events — each call_id must be unique
        for tc in resp.get("tool_calls", []):
            cid = tc.get("id", f"call_{id(tc)}")
            yield StreamChunk.tool_input_start(tool=tc["name"], call_id=cid)
            yield StreamChunk.tool_input_delta(call_id=cid, content=json.dumps(tc["arguments"]))
            yield StreamChunk.tool_input_end(call_id=cid, tool=tc["name"])
        if resp.get("content"):
            yield StreamChunk.text_start()
            yield StreamChunk.text_delta(content=resp["content"])
            yield StreamChunk.text_end()
        usage = resp.get("usage")
        if usage:
            yield StreamChunk.usage_event(Usage(**usage))
        yield StreamChunk.done(content=resp.get("content", ""))
```

## Test Scenarios

### Feature Tests (agent → tool execution)

| Test | Response from FakeProvider | What it verifies |
|------|---------------------------|-------------------|
| `web_search` | tool_call: `web_search(query="AI news")` | Tool called, search executed, result returned |
| `files_list` | tool_call: `files_list(path=".")` | Tool called, directory contents returned |
| `todos_add` | tool_call: `todos_add(title="buy milk")` | Tool called, todo persisted in SQLite |
| `time_get` | tool_call: `time_get()` | Tool called, current time returned |
| `shell_execute` | tool_call: `shell_execute(cmd="echo hi")` | Tool called, output captured |
| `message_search` | tool_call: `message_search(query="hello")` | Tool called, search results returned |
| `contacts_add` | tool_call: `contacts_add(name="John")` | Tool called, contact persisted |
| `workspace_info` | tool_call: `workspace_info()` | Tool called, workspace info returned |
| `email_search` | tool_call: `email_search(query="inbox")` | Tool called, email results (logged: no real email configured) |
| `subagent_create` | tool_call: `subagent_create(name="test")` | Tool called, profile created on disk |
| `memory_search` | tool_call: `memory_search(query="facts")` | Tool called, memory search returns results |
| `browser_open` | tool_call: `browser_open(url="https://example.com")` | Tool called, browser session noted (no real browser) |
| `user_prompt_get` | tool_call: `user_prompt_get()` | Tool called, prompt retrieved |
| `mcp_list` | tool_call: `mcp_list()` | Tool called, MCP status returned |
| `skills_load` | tool_call: `skills_load(name="core")` | Tool called, skill loaded (no real skill execution) |
| `web_scrape` | tool_call: `web_scrape(url="https://example.com")` | Tool called, fetch attempted (logged: no real web) |
| `files_write` | tool_call: `files_write(path="test.txt", content="hello")` | Tool called, file created in isolated temp dir |
| `files_edit` | tool_call: `files_edit(path="test.txt", old="hello", new="world")` | Tool called, file edited |
| `files_delete` | tool_call: `files_delete(path="test.txt")` | Tool called, file deleted |
| `files_mkdir` | tool_call: `files_mkdir(path="newdir")` | Tool called, directory created |
| `files_rename` | tool_call: `files_rename(from="a.txt", to="b.txt")` | Tool called, file renamed |
| `files_glob_search` | tool_call: `files_glob_search(pattern="*.txt")` | Tool called, glob results returned |
| `files_grep_search` | tool_call: `files_grep_search(pattern="hello")` | Tool called, grep results returned |
| `todos_list` | tool_call: `todos_list()` | Tool called, todos returned (new one visible) |
| `todos_update` | tool_call: `todos_update(id="1", status="completed")` | Tool called, todo updated |
| `todos_delete` | tool_call: `todos_delete(id="1")` | Tool called, todo deleted |
| `contacts_list` | tool_call: `contacts_list()` | Tool called, contacts returned |
| `contacts_search` | tool_call: `contacts_search(query="John")` | Tool called, search results |
| `contacts_update` | tool_call: `contacts_update(id="1", name="Jane")` | Tool called, contact updated |
| `contacts_delete` | tool_call: `contacts_delete(id="1")` | Tool called, contact deleted |
| `files_versions_list` | tool_call: `files_versions_list(path="test.txt")` | Tool called, versions returned |
| `files_versions_restore` | tool_call: `files_versions_restore(path="test.txt", version=1)` | Tool called, version restored |

### Multi-turn Tests

| Test | Response sequence | What it verifies |
|------|------------------|-------------------|
| Agent stops on tool result | `[tool_call(files_list) → text_response]` | After tool executes, agent returns text response (doesn't loop infinitely) |
| Agent handles unknown tool | `[tool_call(nonexistent_tool)]` | Agent loop handles error gracefully, returns error message to user |
| Empty tool call list | `[text_response]` | No-tool path works, text returned directly |
| Multiple tool calls | `[tool_call(todos_add) + tool_call(contacts_add)]` | Parallel/distinct tool calls both execute |

### Middleware Tests

Each test verifies the middleware's effect on the pipeline, not the middleware's
internal logic (which is tested separately via unit tests).

| Test | FakeProvider setup | What it verifies |
|------|-------------------|-------------------|
| MemoryMiddleware | `run()` → `run()` with same loop | After second turn, first turn's messages are in SQLite via `tmp_path/app.db` |
| SummarizationMiddleware | Pre-seed 40+ messages into `loop.state.messages` before `run()` | After summarization fires, summary message exists in `state.messages` |
| ProgressMiddleware | Sequential tool calls via `run()` | Progress reported at each poll point (subagent context) |
| InstructionMiddleware | Cancel signal set before LLM call | Agent loop stops, cancel acknowledged |
| ObservationMiddleware | Two `run()` calls, second includes user personal info | Observation extracted, stored in `tmp_path/app.db` observations table |

### Error Handling Tests

| Test | Prompt | What it verifies |
|------|--------|------------------|
| Provider error | FakeProvider raises `RuntimeError("API error")` | Error event emitted, agent doesn't crash |
| Tool execution error | FakeProvider returns tool_call for `files_list` on non-existent path | Error captured, agent reports failure |
| Invalid tool args | FakeProvider returns tool_call with missing required arg | Tool call fails with validation error |
| System prompt injection | system_prompt + `abefore_model` middleware that appends instructions | Agent receives modified instructions, visible in `loop.state.messages` |
| Sequential turns | Two back-to-back `run()` calls on same loop | State is clean, second turn doesn't inherit stale data |

## Files

```
tests/integration/
├── conftest.py              # Backend fixture, FakeProvider, AgentLoop factory
├── fake_provider.py         # FakeProvider class + response builders
├── test_features.py         # Feature smoke tests (parametrized)
├── test_multi_turn.py       # Multi-turn conversation tests
├── test_middlewares.py      # Middleware effect verification tests
└── test_errors.py           # Error handling tests
```

### conftest.py

```python
@pytest.fixture
def fake_provider():
    """Returns a FakeProvider with a safe default response."""
    return FakeProvider()

@pytest.fixture
def loop(fake_provider, tmp_path):
    """Returns an AgentLoop with FakeProvider + all real middlewares + isolated tmp dir."""
    tools = get_native_tools()
    loop = AgentLoop(
        provider=fake_provider,
        tools=tools,
        system_prompt=TEST_PROMPT,
        middlewares=[
            MemoryMiddleware(user_id="test", base_dir=tmp_path),
            ProgressMiddleware(),
            InstructionMiddleware(),
        ],
        run_config=RunConfig(max_llm_calls=10),
    )
    return loop
```

### Test structure

```python
@pytest.mark.parametrize("tool_name,response,content_check", [
    ("web_search", {"tool_calls": [{"name": "web_search", "arguments": {"query": "AI news"}}]},
     lambda c: len(c) > 10),
    ("files_list", {"tool_calls": [{"name": "files_list", "arguments": {"path": "."}}]},
     lambda c: len(c) > 0),
])
async def test_tool_execution(tool_name, response, content_check, loop, tmp_path):
    """Verifies each tool can be called and returns valid results."""
    loop.provider._responses = [response, {"content": "Done."}]
    result = await loop.run([Message.user(f"run {tool_name}")])
    # Verify tool was called — check state.messages for the assistant message with tool_calls
    tool_msgs = [m for m in loop.state.messages if m.role == "assistant" and m.tool_calls]
    assert any(tc.name == tool_name for msg in tool_msgs for tc in (msg.tool_calls or []))
    # Verify result is sensible
    assert content_check(result.content or "")
```

## CI Integration

Standard CI run: `uv run pytest tests/integration/ -v --tb=short`
- ~200 tests × ~0.1s = ~20s runtime
- No LLM calls, no network, no real filesystem writes (temp dirs + cleanup)
- Each test isolated: temp dir per test, clean state

## What This Does NOT Cover

1. **Provider-specific behavior** — Ollama streaming quirks, Gemini token counting
2. **Multi-user isolation** — each test is single-user
3. **WebSocket/HTTP transport** — tests exercise AgentLoop directly, not via network
4. **Long-running scenarios** — summarization after 200+ turns, reflection after 24h
5. **Non-deterministic behavior** — real LLM quality, model fallback, rate limiting

Items 1-2 are covered by existing SDK unit tests. Items 3-5 require a separate
integration test suite with a real backend and real LLM (nightly, not in CI).