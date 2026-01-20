# Executive Assistant Development Notes

## Testing Workflow

**ALWAYS test locally with `uv run executive_assistant` before building Docker.**

### Steps:
1. Keep postgres running in Docker: `docker compose up -d postgres`
2. Stop executive_assistant container: `docker compose stop executive_assistant`
3. Run executive_assistant locally: `uv run executive_assistant`
4. Test your changes
5. Only build Docker when everything works: `docker compose build --no-cache executive_assistant`

### Environment Variables for Local Testing
```bash
# LLM Provider
DEFAULT_LLM_PROVIDER=ollama
OLLAMA_API_KEY=your-key

# Channels
EXECUTIVE_ASSISTANT_CHANNELS=telegram,http
```

### Why?
- Faster iteration (no rebuild needed)
- Better error visibility
- Easier debugging
- Docker only for deployment
