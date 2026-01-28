FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OMP_NUM_THREADS=4 \
    MKL_NUM_THREADS=4

WORKDIR /app

RUN pip install --no-cache-dir uv

# System dependencies (OCR + shell tools)
RUN apt-get update && apt-get install -y \
  libgomp1 libglib2.0-0 libsm6 libxext6 libxrender-dev libgl1 \
  git curl jq ripgrep bash \
  && rm -rf /var/lib/apt/lists/*

# Create user first
RUN useradd -m -u 1000 executive_assistant

# Copy dependency files and install as the executive_assistant user
COPY README.md .python-version pyproject.toml uv.lock ./
RUN chown -R executive_assistant:executive_assistant /app
USER executive_assistant
RUN uv sync --frozen

# Switch back to root to copy application files, then back to executive_assistant
USER root
COPY . .
RUN chown -R executive_assistant:executive_assistant /app
RUN mkdir -p /app/data /app/logs && chown -R executive_assistant:executive_assistant /app/data /app/logs
USER executive_assistant

EXPOSE 8000

CMD ["uv", "run", "executive_assistant"]
