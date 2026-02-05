# LLM Model Configuration Guide

## Production Model (Recommended)

**Model:** `qwen3-next:80b-cloud` via **Ollama Cloud**

**Provider:** Ollama Cloud (https://ollama.com)

**Why This Model?**
- ✅ **Reliable tool calling** - Generates proper `tool_calls` that LangChain executes
- ✅ **Fast responses** - 10-20 second execution time
- ✅ **Large context** - 80B parameters handle complex multi-step tasks
- ✅ **Production proven** - Tested with 102 tools across all categories

**Configuration:**
```yaml
llm:
  default_provider: ollama

  ollama:
    default_model: qwen3-next:80b-cloud
    fast_model: qwen3-next:80b-cloud
    mode: cloud
    cloud_url: "https://ollama.com"
    local_url: "http://localhost:11434"
```

**Environment:**
```bash
DEFAULT_LLM_PROVIDER=ollama
OLLAMA_MODE=cloud
OLLAMA_CLOUD_URL=https://ollama.com
OLLAMA_CLOUD_API_KEY=your_api_key_here
```

---

## Alternative Working Models (Ollama Cloud)

All models below support proper tool calling via Ollama Cloud:

| Model | Size | Speed | Use Case |
|-------|------|-------|----------|
| **qwen3-next:80b-cloud** | 80B | Fast (10-20s) | **Production (RECOMMENDED)** |
| deepseek-v3.1:671b-cloud | 671B | Medium | General tasks |
| glm-4.7:cloud | - | Fast | Chinese language |
| minimax-m2.1:cloud | - | Fast | Cost-effective |
| gpt-oss:20b-cloud | 20B | Fast | Quick tasks |

---

## Models to Avoid

### ❌ deepseek-v3.2:cloud

**Issue:** Generates tool calls in old XML format:
```xml
<function_calls>
<invoke name="list_profiles">
</invoke>
</function_calls>
```

**Problem:** LangChain doesn't recognize this format, so tools never execute.

**Status:** Do NOT use for tool calling. Works for simple chat only.

### ❌ kimi-k2.5:cloud

**Issue:** JSON Schema not supported

**Error:** `JSON Schema not supported: could not understand the instance {}.`

**Status:** Not compatible with current tool system.

---

## Model Selection Criteria

When choosing a model for Ollama Cloud, verify:

1. **Tool Calling Support** - Must generate `tool_calls` attribute (not XML)
2. **API Compatibility** - Must work with LangChain's ChatOllama integration
3. **Response Format** - Should return structured tool calls, not text
4. **Speed** - 10-30 second execution time acceptable
5. **Cost** - Consider token usage for production workloads

**Test Command:**
```bash
curl -X POST http://localhost:8000/message \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"test","content":"list profiles"}'
```

**Expected Response:**
```
data: {"content":"🛠️ 1: list_profiles","role":"status","done":false}
data: {"content":"[actual results...]","role":"assistant","done":false}
data: {"content":"✅ Done in X.Xs","role":"status","done":false}
```

**Red Flags:**
- `<function_calls>` in response (old format, won't execute)
- "JSON Schema not supported" error
- No `🛠️` tool execution indicator

---

## Performance Benchmarks

Average execution times for single tool call (qwen3-next:80b-cloud):

| Tool Category | Avg Time |
|--------------|----------|
| Memory (list/search) | 10-15s |
| TDB (create/query) | 15-25s |
| ADB (create/query) | 15-30s |
| VDB (search) | 12-20s |
| File operations | 8-15s |
| Web search | 20-40s |
| Multi-step tasks | 30-90s |

**Note:** First call includes model loading (~5-7s overhead). Subsequent calls are cached and faster.

---

## Migration Guide

### Switching from deepseek-v3.2 to qwen3-next

1. **Update config:**
   ```yaml
   ollama:
     default_model: qwen3-next:80b-cloud
     fast_model: qwen3-next:80b-cloud
   ```

2. **Restart service:**
   ```bash
   pkill -f executive_assistant
   uv run executive_assistant
   ```

3. **Verify:**
   ```bash
   curl -X POST http://localhost:8000/message \
     -H 'Content-Type: application/json' \
     -d '{"user_id":"test","content":"list profiles"}'
   ```

4. **Expected:** Should see `🛠️ 1: list_profiles` and results in 10-20s.

---

## Troubleshooting

### Tools Not Executing

**Symptom:** Model generates response but tools don't run.

**Check:**
```bash
# Look for XML format in response
curl -s -X POST http://localhost:8000/message \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"test","content":"list profiles"}' | grep "<function_calls>"
```

**If found:** Model doesn't support tool calling. Switch to qwen3-next:80b-cloud.

### Slow Responses

**Check:**
- Network latency to Ollama Cloud
- Model size (larger models = slower)
- Number of tools (more tools = slower)
- First call vs cached call

**Solutions:**
- Use qwen3-next:80b-cloud (fastest large model)
- Cache MCP clients (already implemented)
- Reduce tool count if needed

### API Key Issues

**Symptom:** `ResponseError: unauthorized (status code: 401)`

**Check:**
```bash
echo $OLLAMA_CLOUD_API_KEY
```

**Solution:**
```bash
# Set in docker/.env
OLLAMA_CLOUD_API_KEY=your_actual_key_here
```

---

## Future Considerations

### Local Ollama Models

For local deployment (no cloud API key needed):

```yaml
ollama:
  mode: local
  local_url: "http://localhost:11434"
  default_model: llama3.1
  fast_model: llama3.1
```

**Note:** Local models require more RAM (16GB+ for 70B models).

### Other Providers

Consider for specific use cases:

- **OpenAI/Anthropic** - Best tool calling, faster, more expensive
- **Gemini** - Good middle ground, Google integration
- **Zhipu (GLM)** - Excellent Chinese language support

See `docker/config.yaml` for configuration examples.

---

**Last Updated:** 2026-02-05
**Model Version:** qwen3-next:80b-cloud via Ollama Cloud
**Status:** ✅ Production Ready
