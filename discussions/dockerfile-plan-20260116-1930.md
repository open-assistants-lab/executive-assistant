# Executive Assistant Dockerfile Plan (SeekDB-compatible)

## Goals
- Run Executive Assistant in a Linux container (required for SeekDB embedded mode).
- Keep dev and prod workflows aligned.
- Persist per-thread data under `data/users/` via a bind mount/volume.
- Include OCR system deps by default.

## Constraints + Assumptions
- SeekDB embedded mode is **Linux-only** (pyseekdb + pylibseekdb).
- Python version should match current runtime (3.13.x via uv).
- Network access may be restricted in CI; prefer deterministic builds.
- OCR (PaddleOCR) is required; install system deps by default.

## Proposed Dockerfile Design
### Base
- Use `python:3.13-slim` (Linux) as the base.
- Install system build deps only if needed for Python packages.

### Dependencies
- Install `uv` for dependency sync (consistent with local usage).
- Copy `.python-version`, `pyproject.toml` + `uv.lock` first for Docker cache efficiency.
- `uv sync --frozen --no-dev` in prod image; include dev deps for dev image.

### App Layout
- `WORKDIR /app`
- Copy source + configs after deps.
- Create `data/` and `logs/` directories with correct permissions.
- Use `ENV` for standard runtime config (e.g. `EXECUTIVE_ASSISTANT_ENV=prod`).

### SeekDB Persistence
- Mount `./data:/app/data` (host volume) so `data/users/{thread_id}/kb/` persists.
- No extra SeekDB file config needed; embedded engine writes `seekdb.db` in `kb/`.

### OCR System Dependencies (Required)
Install by default:
```
RUN apt-get update && apt-get install -y \
  libgomp1 libglib2.0-0 libsm6 libxext6 libxrender-dev libgl1-mesa-glx \
  && rm -rf /var/lib/apt/lists/*
```
OCR Python deps should be present in `pyproject.toml`.

### Shell Tools (Optional, for ShellToolMiddleware)
If `MW_SHELL_ENABLED=true`, install common utilities:
```
RUN apt-get update && apt-get install -y \
  git curl jq ripgrep bash \
  && rm -rf /var/lib/apt/lists/*
```

## Dockerfile Skeleton (Planned)
```dockerfile
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_SYSTEM_PYTHON=1 \
    # ONNX performance for SeekDB embeddings
    OMP_NUM_THREADS=4 \
    MKL_NUM_THREADS=4

WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv

# System dependencies (OCR + shell tools)
RUN apt-get update && apt-get install -y \
  libgomp1 libglib2.0-0 libsm6 libxext6 libxrender-dev libgl1-mesa-glx \
  git curl jq ripgrep bash \
  && rm -rf /var/lib/apt/lists/*

# Copy dependency files (include .python-version for uv)
COPY .python-version pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy application code
COPY . .

# Create directories (non-root user will handle these)
RUN mkdir -p /app/data /app/logs

# Create non-root user (recommended for prod)
RUN useradd -m -u 1000 executive_assistant && \
    chown -R executive_assistant:executive_assistant /app
USER executive_assistant

EXPOSE 8000

# Use installed Python directly (faster than uv run)
CMD [".venv/bin/python", "-m", "executive_assistant"]
```

## docker-compose.yml Updates (Planned)
```yaml
services:
  executive_assistant:
    build: .
    volumes:
      - ./data:/app/data
    environment:
      - EXECUTIVE_ASSISTANT_CHANNELS=telegram,http
      - POSTGRES_URL=postgresql://executive_assistant:password@postgres:5432/executive_assistant_db
      - TZ=UTC
      # SeekDB uses default ONNX embeddings (no extra config needed)
      # Shell tools (optional)
      - MW_SHELL_ENABLED=false
    depends_on:
      - postgres

  postgres:
    image: postgres:16
    environment:
      - POSTGRES_DB=executive_assistant_db
      - POSTGRES_USER=executive_assistant
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

**Note:** The `./data` bind mount needs to be writable by UID 1000 (executive_assistant user). On Linux, you may need to `sudo chown -R 1000:1000 ./data`.

## Dev Workflow
1. `docker compose up -d` (postgres + executive_assistant).
2. Use bind mounts for `data/` to persist KB.
3. For local dev on macOS/Windows, use Linux container so SeekDB embedded works.

## Testing Plan
- Verify `uv run executive_assistant` inside container starts without SeekDB errors.
- Confirm KB writes create `data/users/{thread_id}/kb/seekdb.db`.
- Smoke test a KB write and search via tool calls.

## Risks + Mitigations
- **Image size bloat**: accept larger base due to OCR deps (~300MB more).
- **SeekDB Linux-only**: enforce Linux base; document in README.
- **File permissions**: `./data` must be writable by UID 1000 (executive_assistant user). On Linux, `sudo chown -R 1000:1000 ./data`.
- **Non-root user**: included for security; may need adjustment for local dev file permissions.

## Open Decisions
- Whether to split dev/prod images (multi-stage) – not strictly necessary with current setup.

---

## Peer Review & Fixes (2025-01-16)

### Issues Fixed

| Issue | Fix |
|-------|-----|
| Missing `.python-version` copy | Added to COPY layer for uv to use correct Python |
| `SEEKDB_EMBEDDING_MODE` reference | Removed – SeekDB uses default ONNX only |
| `uv run` in CMD | Changed to `.venv/bin/python -m executive_assistant` (faster) |
| Missing shell tools | Added git, curl, jq, ripgrep, bash for ShellToolMiddleware |
| Non-root user undecided | Implemented with UID 1000 |
| Missing ONNX performance env vars | Added `OMP_NUM_THREADS=4`, `MKL_NUM_THREADS=4` |

### Dockerfile Best Practices Applied

- Multi-layer caching (deps before code)
- Single apt-get layer with cleanup
- Non-root user for security
- Deterministic builds with `--frozen`
- Health of bind mounts documented

---

## Implementation Notes (Applied)
- Added root `Dockerfile` matching the plan (python:3.13-slim, uv sync, OCR + shell deps, non-root user).
- Added `executive_assistant` service to `docker-compose.yml` with bind mount `./data:/app/data`, HTTP port mapping (`8000:8000`), and Postgres env wiring.
