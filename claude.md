# Cassey Development Notes

## Testing Workflow

**ALWAYS test locally with `uv run cassey` before building Docker.**

### Steps:
1. Keep postgres running in Docker: `docker compose up -d postgres`
2. Stop cassey container: `docker compose stop cassey`
3. Run cassey locally: `uv run cassey`
4. Test your changes
5. Only build Docker when everything works: `docker compose build --no-cache cassey`

### Environment Variables for Local Testing
```bash
# LLM Provider
DEFAULT_LLM_PROVIDER=ollama
OLLAMA_API_KEY=your-key

# Channels
CASSEY_CHANNELS=telegram,http
```

### Why?
- Faster iteration (no rebuild needed)
- Better error visibility
- Easier debugging
- Docker only for deployment
